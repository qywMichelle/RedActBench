"""Real subprocess interruptions and HTTP failures; no model services are called."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile

from test_handoff import ROOT


class ScriptedHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with self.server.guard:
            index = len(self.server.received)
            self.server.received.append(body)
            step = self.server.plan[index] if index < len(self.server.plan) else 'FINISH'
        gemini = self.path.endswith(':generateContent')
        prompt = body['contents'][0]['parts'][0]['text'] if gemini else body['messages'][0]['content'][0]['text']
        observation = json.loads(prompt.split('\nCURRENT OBSERVATION:\n')[1].split('\nPROTOCOL REMINDER:\n')[0])
        if step == 'BLOCK':
            self.server.blocked.set()
            self.server.release.wait(10)
            step = 'FINISH'
        if step == 'FAIL':
            self.send_response(402)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"error":"mock budget exhausted"}')
            return
        if step == 'INVALID':
            text = 'invalid JSON'
        elif step == 'REJECT':
            text = json.dumps({'action': 'READ', 'ids': ['not-a-visible-id']})
        elif step == 'IMAGE':
            text = json.dumps({'action': 'LOOKUP', 'target': 'card', 'entry': 'tray'})
        elif step == 'READ':
            resource = (observation['resources'][0]['id'] if 'resources' in observation else
                        next(iter(observation['own_content'])))
            text = json.dumps({'action': 'READ', 'ids': [resource]})
        elif 'operations' in observation:
            text = json.dumps({'action': 'WAIT', 'time': observation['deadline']})
        else:
            text = json.dumps({'action': 'FINISH', 'text': 'Mock finish marker ' + str(index)})
        raw = ({'candidates': [{'content': {'parts': [{'text': text}]}, 'finishReason': 'STOP'}]}
               if gemini else {'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}]})
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(raw).encode())
        except (BrokenPipeError, ConnectionResetError):
            pass


class ResumeTest(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), ScriptedHandler)
        self.server.plan, self.server.received = [], []
        self.server.guard = threading.Lock()
        self.server.blocked, self.server.release = threading.Event(), threading.Event()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.children = []

    def tearDown(self):
        self.server.release.set()
        for child in self.children:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=5)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def command(self, *args):
        return [sys.executable, str(ROOT / 'redact_bench.py'), *map(str, args)]

    def env(self):
        return dict(os.environ, REDACT_TEST_KEY='dummy-test-key', PYTHONDONTWRITEBYTECODE='1')

    def cli(self, *args, success=True):
        result = subprocess.run(self.command(*args), cwd=self.directory, env=self.env(),
                                text=True, capture_output=True, timeout=30)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def new_args(self, run, protocol='openai', case='batch_020/t1-01'):
        return ['run', '--protocol', protocol, '--url', self.url +
                ('/v1:generateContent' if protocol == 'gemini' else '/v1'),
                '--model', 'mock', '--api-key-env', 'REDACT_TEST_KEY', '--case', case,
                '--max-requests', '12', '--output', run]

    def trajectory(self, run, case='batch_020/t1-01'):
        return run / 'trajectories' / (case + '.json')

    def snapshot(self, run):
        return {str(p.relative_to(run)): p.read_bytes() for p in run.rglob('*.json')}

    def test_resume_after_failure_keeps_errors_and_exact_request(self):
        for protocol in ['openai', 'gemini']:
            with self.subTest(protocol=protocol):
                self.server.received = []
                self.server.plan = ['INVALID', 'REJECT', 'READ', 'FAIL', 'FINISH']
                run = self.directory / protocol
                self.cli(*self.new_args(run, protocol), success=False)
                path = self.trajectory(run)
                prefix_bytes = path.read_bytes()
                prefix = json.loads(prefix_bytes)
                self.assertEqual(prefix['status'], 'infrastructure_error')
                self.assertEqual(len(prefix['calls']), 3)
                self.cli('run', '--resume', '--output', run)
                restored = json.loads(path.read_text())
                self.assertEqual(restored['status'], 'complete')
                self.assertEqual(restored['calls'][:3], prefix['calls'])
                self.assertEqual(self.server.received[3], self.server.received[4])
                self.assertEqual(restored['protocol_error_count'], 2)
                backup = next((run / 'resume-backups').iterdir())
                self.assertEqual((backup / path.relative_to(run)).read_bytes(), prefix_bytes)
                self.cli('check-run', '--run', run)
                before = self.snapshot(run)
                count = len(self.server.received)
                self.cli('run', '--resume', '--output', run)
                self.assertEqual(before, self.snapshot(run))
                self.assertEqual(count, len(self.server.received))

    def test_paired_export_resume_skips_completed_A_and_isolates_B(self):
        self.server.plan = ['FINISH', 'READ', 'FAIL', 'FINISH']
        run = self.directory / 'paired'
        self.cli('run', '--paired', '--limit', '2', '--url', self.url, '--model', 'mock',
                 '--api-key-env', 'REDACT_TEST_KEY', '--output', run, success=False)
        manifest = json.loads((run / 'frozen-manifest.json').read_text())
        case_a, case_b = [e['case'] for e in manifest['episodes']]
        a_bytes = self.trajectory(run, case_a).read_bytes()
        b_bytes = self.trajectory(run, case_b).read_bytes()
        self.assertNotIn('Mock finish marker 0', json.dumps(self.server.received[1]))
        archive = self.directory / 'prefix.zip'
        self.cli('export', '--run', run, '--output', archive)
        received = self.directory / 'received'
        with zipfile.ZipFile(archive) as z:
            z.extractall(received)
        self.cli('run', '--resume', '--output', received)
        self.assertEqual(self.trajectory(received, case_a).read_bytes(), a_bytes)
        self.assertEqual(self.trajectory(run, case_b).read_bytes(), b_bytes)
        self.assertEqual(self.server.received[2], self.server.received[3])
        self.assertEqual(len(self.server.received), 4)
        self.assertFalse((received / 'trace-integrity.json').exists())
        self.assertTrue(list((received / 'resume-backups').glob('*/trace-integrity.json')))
        self.cli('check-run', '--run', received)
        self.cli('export', '--run', received, '--output', self.directory / 'finished.zip')
        self.cli('evaluate', '--run', received, '--output', self.directory / 'review', '--prepare')

    def test_resume_preserves_revealed_images(self):
        self.server.plan = ['IMAGE', 'FAIL', 'FINISH']
        run = self.directory / 'images'
        self.cli(*self.new_args(run, protocol='gemini', case='batch_020/t1-02'), success=False)
        self.cli('run', '--resume', '--output', run)
        self.assertEqual(self.server.received[1], self.server.received[2])
        self.assertTrue(any('inlineData' in p for p in self.server.received[2]['contents'][0]['parts']))
        self.cli('check-run', '--run', run)

    def test_resume_legacy_workflow_runtime(self):
        self.server.plan = ['READ', 'FAIL']
        run = self.directory / 'legacy-world'
        case = 'batch_001_en/t1-01'
        self.cli(*self.new_args(run, case=case), success=False)
        old = json.loads(self.trajectory(run, case).read_text())['calls']
        self.cli('run', '--resume', '--output', run)
        self.assertEqual(json.loads(self.trajectory(run, case).read_text())['calls'][:1], old)
        self.assertEqual(self.server.received[1], self.server.received[2])
        self.cli('check-run', '--run', run)

    def test_config_changes_and_legacy_checkpoint_rejected_before_network(self):
        self.server.plan = ['READ', 'FAIL']
        run = self.directory / 'bound'
        self.cli(*self.new_args(run), success=False)
        before = self.snapshot(run)
        changes = [('--model', 'different'), ('--url', 'http://127.0.0.1:1'),
                   ('--protocol', 'gemini'), ('--temperature', '0'), ('--max-requests', '13'),
                   ('--max-tokens', '1024'), ('--max-prompt-chars', '10'), ('--top-p', '.5'),
                   ('--seed', '1'), ('--timeout', '1'), ('--no-auth',), ('--paired',),
                   ('--case', 'batch_020/t1-02')]
        for flags in changes:
            with self.subTest(flags=flags):
                self.cli('run', '--resume', '--output', run, *flags, success=False)
                self.assertEqual(before, self.snapshot(run))
                self.assertEqual(len(self.server.received), 2)
        path = run / 'run_config.json'
        config = json.loads(path.read_text())
        for key, value in [('schema', 'redact-collaborator-behavior-test-v1'),
                           ('runner_files', {}), ('bundle_inventory_sha256', '0' * 64)]:
            changed = dict(config, **{key: value})
            path.write_text(json.dumps(changed))
            self.cli('run', '--resume', '--output', run, success=False)
            self.assertEqual(len(self.server.received), 2)
        path.write_bytes(before['run_config.json'])

    def test_request_budget_is_not_reset(self):
        self.server.plan = ['READ']
        run = self.directory / 'budget'
        args = self.new_args(run)
        args[args.index('--max-requests') + 1] = '1'
        self.cli(*args)
        before = self.snapshot(run)
        self.cli('run', '--resume', '--output', run)
        self.assertEqual(before, self.snapshot(run))
        self.assertEqual(len(self.server.received), 1)
        self.cli('run', '--resume', '--output', run, '--max-requests', '2', success=False)

    def test_damaged_checkpoint_rejected_without_network_or_rewrite(self):
        self.server.plan = ['READ', 'FAIL']
        run = self.directory / 'damaged'
        self.cli(*self.new_args(run), success=False)
        path = self.trajectory(run)
        original = json.loads(path.read_text())
        for field in ['request_prompt_sha256', 'request_body_sha256', 'simulation']:
            changed = json.loads(json.dumps(original))
            if field == 'simulation':
                changed['simulation']['time'] = 999
            else:
                changed['calls'][0]['response'][field] = '0' * 64
            data = json.dumps(changed).encode()
            path.write_bytes(data)
            self.cli('run', '--resume', '--output', run, success=False)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(len(self.server.received), 2)
            self.assertFalse((run / 'resume-backups').exists())

    def test_resume_before_first_response_was_saved(self):
        self.server.plan = ['BLOCK', 'FINISH']
        run = self.directory / 'no-response'
        child = subprocess.Popen(self.command(*self.new_args(run)), cwd=self.directory,
                                 env=self.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.children.append(child)
        self.assertTrue(self.server.blocked.wait(10))
        self.assertFalse(self.trajectory(run).exists())
        child.kill()
        child.communicate(timeout=10)
        self.server.release.set()
        self.cli('run', '--resume', '--output', run)
        self.assertEqual(self.server.received[0], self.server.received[1])
        self.assertEqual(len(json.loads(self.trajectory(run).read_text())['calls']), 1)
        self.cli('check-run', '--run', run)

    def test_signals_and_writer_lock(self):
        for sig in [signal.SIGINT, signal.SIGTERM, signal.SIGKILL]:
            with self.subTest(signal=sig):
                self.server.plan, self.server.received = ['READ', 'BLOCK', 'FINISH'], []
                self.server.blocked.clear()
                self.server.release.clear()
                run = self.directory / ('signal-' + str(sig))
                child = subprocess.Popen(self.command(*self.new_args(run)), cwd=self.directory,
                                         env=self.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.children.append(child)
                self.assertTrue(self.server.blocked.wait(10), 'Child did not reach the blocked second request')
                path = self.trajectory(run)
                prefix = json.loads(path.read_text())['calls']
                result = self.cli('run', '--resume', '--output', run, success=False)
                self.assertIn('Another process', result.stderr)
                self.assertEqual(len(self.server.received), 2)
                child.send_signal(sig)
                child.communicate(timeout=10)
                self.server.release.set()
                stopped = json.loads(path.read_text())
                self.assertEqual(stopped['status'], 'running' if sig == signal.SIGKILL else 'user_stopped')
                self.cli('run', '--resume', '--output', run)
                self.assertEqual(json.loads(path.read_text())['calls'][:1], prefix)
                self.assertEqual(self.server.received[1], self.server.received[2])
                self.cli('check-run', '--run', run)


if __name__ == '__main__':
    unittest.main()
