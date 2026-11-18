"""Exercise real HTTP adapters, rejected calls, image input and trace handoff."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('portable_bench', ROOT / 'redact_bench.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.received.append((self.path, dict(self.headers), body))
        index = len(self.server.received)
        texts = ['invalid JSON', json.dumps({'action': 'READ', 'ids': ['does-not-exist']}),
                 json.dumps({'action': 'FINISH', 'text': 'Mock integration test only; obligations not performed.'})]
        text = texts[min(index - 1, 2)]
        if self.path.endswith(':generateContent'):
            result = {'candidates': [{'content': {'parts': [
                {'text': 'private reasoning is not an action', 'thought': True}, {'text': text}]},
                                      'finishReason': 'STOP'}],
                      'usageMetadata': {'promptTokenCount': 10, 'candidatesTokenCount': 5}}
        else:
            result = {'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}],
                      'usage': {'prompt_tokens': 10, 'completion_tokens': 5}, 'model': 'mock'}
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.received = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def cli(self, *args, success=True):
        env = dict(os.environ, REDACT_TEST_KEY='dummy-test-key', PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run([sys.executable, str(ROOT / 'redact_bench.py'), *map(str, args)],
                                cwd=self.directory, env=env, text=True, capture_output=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def exercise(self, protocol):
        run = self.directory / protocol
        url = self.url + ('/v1:generateContent' if protocol == 'gemini' else '/v1')
        args = ['run', '--protocol', protocol, '--url', url, '--model', 'mock',
                '--api-key-env', 'REDACT_TEST_KEY', '--case', 'batch_020/t1-01',
                '--max-requests', '3', '--output', run]
        self.cli(*args)
        summary = json.loads((run / 'execution-summary.json').read_text())
        self.assertEqual(summary['requests'], 3)
        self.assertEqual(summary['protocol_errors'], 2)
        self.assertFalse(summary['semantic_scoring'])
        self.cli('check-run', '--run', run)
        archive = self.directory / (protocol + '.zip')
        self.cli('export', '--run', run, '--output', archive)
        received = self.directory / ('received-' + protocol)
        with zipfile.ZipFile(archive) as z:
            z.extractall(received)
        self.cli('check-run', '--run', received)
        # Owner preparation must work directly on the received portable trace.
        output = self.directory / ('review-' + protocol)
        self.cli('evaluate', '--run', received, '--output', output, '--prepare')
        self.assertTrue((output / 'judge-inputs/batch_020/t1-01.json').is_file())
        template = json.loads((output / 'templates/batch_020/t1-01.json').read_text())
        self.assertTrue(all(g['status'] == 'undetermined' for g in template['goals']))
        received_trajectory = received / 'trajectories/batch_020/t1-01.json'
        received_record = json.loads(received_trajectory.read_text())
        received_record['calls'][0]['response']['latency_seconds'] = -1
        received_trajectory.write_text(json.dumps(received_record))
        self.cli('check-run', '--run', received, success=False)
        for path in run.rglob('*.json'):
            self.assertNotIn('dummy-test-key', path.read_text())
        headers = self.server.received[0][1]
        self.assertEqual(headers.get('Api-Key') if protocol == 'gemini' else headers.get('Authorization'),
                         'dummy-test-key' if protocol == 'gemini' else 'Bearer dummy-test-key')
        self.cli(*args, success=False)  # No accidental overwrite / repeated API calls.
        self.assertEqual(len(self.server.received), 3)
        # A tampered response must not pass transport/replay verification.
        trajectory = run / 'trajectories/batch_020/t1-01.json'
        record = json.loads(trajectory.read_text())
        record['calls'][2]['response']['text'] = '{"action":"WAIT","until":5}'
        trajectory.write_text(json.dumps(record))
        self.cli('check-run', '--run', run, success=False)

    def test_openai_handoff(self):
        self.exercise('openai')

    def test_gemini_handoff(self):
        self.exercise('gemini')

    def test_revealed_image_transport_both_protocols(self):
        entry = next(e for e in bench.load(bench.manifest_path())['episodes']
                     if e['case'] == 'batch_020/t1-02')
        bench.images.validate_inputs([entry])
        world = bench.load(bench.core.input_path(entry, 'hidden'))
        ref = next(iter(bench.images.image_references(world).values()))
        observation = {'time': 0, 'resources': [dict(id='visible-photo', image_path=ref['path'],
                                                    image_sha256=ref['sha256'])]}
        args = argparse.Namespace(context_policy='revealed_delta', max_prompt_chars=200000,
                                  protocol_feedback_version='observed-state-v2', active_entry=entry,
                                  model='mock', temperature=1, max_tokens=1024, top_p=.95, seed=0, timeout=5)
        opener = bench.urllib.request.build_opener()
        for protocol in ['openai', 'gemini']:
            args.protocol = protocol
            args.endpoint = self.url + ('/v1:generateContent' if protocol == 'gemini' else '/v1/chat/completions')
            result = bench.transport('dummy-test-key', opener, args, observation, '', [])
            self.assertEqual(len(result['image_inputs']), 1)
            body = self.server.received[-1][2]
            encoded = (body['contents'][0]['parts'][-1]['inlineData']['data'] if protocol == 'gemini'
                       else body['messages'][0]['content'][-1]['image_url']['url'].split(',', 1)[1])
            self.assertTrue(bench.base64.b64decode(encoded).startswith(b'\x89PNG\r\n\x1a\n'))
        # Merely existing in hidden state does not send images to the model.
        self.assertEqual(bench.images.attachments(entry, {'time': 0}, []), [])

    def test_named_counterfactual_reference(self):
        refs = bench.load(ROOT / 'data/reference-index.json')
        entry = next(e for e in bench.load(bench.manifest_path(True))['episodes']
                     if e['configuration'] == 'B' and
                     refs[e['case']]['path'].endswith('counterfactual.json'))
        bench.core.RUNTIME_CACHE.clear()
        _, replay = bench.core.runtime(entry)
        result = bench.owner_reference(entry, bench.load(bench.core.input_path(entry, 'hidden')), replay)
        self.assertGreater(result['calls'], 0)
        self.assertTrue(result['path'].endswith('counterfactual.json'))


if __name__ == '__main__':
    unittest.main()
