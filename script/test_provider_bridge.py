"""Offline protocol and frozen-run replay checks for the external adapter."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import urllib.request

from provider_bridge import MODELS, Server
from run_background import BUNDLE, PYTHON, plan


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.received.append((self.path, body))
        text = '{"action":"FINISH","text":"Offline adapter integration fixture."}'
        if self.path.endswith('/messages'):
            raw = {'id': 'fixture', 'model': body['model'], 'stop_reason': 'end_turn',
                   'content': [{'type': 'thinking', 'thinking': 'excluded'}, {'type': 'text', 'text': text}],
                   'usage': {'input_tokens': 7, 'output_tokens': 4, 'cache_read_input_tokens': 3}}
        else:
            raw = {'id': 'fixture', 'model': body['model'], 'status': 'completed',
                   'output': [{'type': 'reasoning', 'summary': []}, {'type': 'message',
                              'content': [{'type': 'output_text', 'text': text}]}],
                   'usage': {'input_tokens': 10, 'output_tokens': 4}}
        data = json.dumps(raw).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(data)


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.remote = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        self.remote.received = []
        self.bridge = Server(('127.0.0.1', 0), 'test-only-key', self.root / 'ledger.jsonl',
                             upstream=f'http://127.0.0.1:{self.remote.server_port}/v1')
        self.threads = []
        for server in [self.remote, self.bridge]:
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            self.threads.append(t)

    def tearDown(self):
        for server in [self.bridge, self.remote]:
            server.shutdown()
            server.server_close()
        for t in self.threads:
            t.join()
        self.temp.cleanup()

    def exercise_run(self, model):
        run = self.root / 'run'
        env = dict(os.environ, REDACT_API_KEY='test-only-key', PYTHONDONTWRITEBYTECODE='1')
        commands = [
            ['run', '--protocol', 'openai', '--url', f'http://127.0.0.1:{self.bridge.server_port}/v1',
             '--model', model, '--max-tokens', '16384', '--max-requests', '2',
             '--case', 'batch_020/t1-01', '--output', str(run)],
            ['check-run', '--run', str(run)],
            ['export', '--run', str(run), '--output', str(self.root / 'export.zip')]]
        for command in commands:
            result = subprocess.run(['prlimit', '--as=536870912', '--core=0', '--', str(PYTHON),
                str(BUNDLE / 'redact_bench.py'), *command], cwd=BUNDLE, env=env,
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = json.loads((run / 'trajectories/batch_020/t1-01.json').read_text())
        self.assertEqual(record['status'], 'complete')
        self.assertEqual(record['calls'][0]['response']['usage']['prompt_tokens'], 10)
        for p in self.root.rglob('*.json'):
            self.assertNotIn('test-only-key', p.read_text())

    def test_messages_trace_replays_and_exports(self):
        self.exercise_run('claude-opus-5-5-science')

    def test_responses_trace_replays_and_exports(self):
        self.exercise_run('gpt-6.1-sol-science')

    def test_images_and_text_preserved_over_http(self):
        for model, protocol in MODELS.items():
            body = {'model': model, 'max_tokens': 16384, 'messages': [{'role': 'user', 'content': [
                {'type': 'text', 'text': 'Visible prompt unchanged.'},
                {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,cG5n'}}]}]}
            req = urllib.request.Request(f'http://127.0.0.1:{self.bridge.server_port}/v1/chat/completions',
                json.dumps(body).encode(), {'Authorization': 'Bearer test-only-key',
                                          'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as response:
                result = json.load(response)
            self.assertIn('FINISH', result['choices'][0]['message']['content'])
            path, emitted = self.remote.received[-1]
            self.assertEqual(path, '/v1/' + protocol)
            parts = emitted['messages' if protocol == 'messages' else 'input'][0]['content']
            self.assertEqual(parts[0]['text'], 'Visible prompt unchanged.')
            if protocol == 'messages':
                self.assertEqual(parts[1]['source']['data'], 'cG5n')
            else:
                self.assertEqual(parts[1]['image_url'], 'data:image/png;base64,cG5n')

    def test_plan_covers_all_configurations_without_duplicates(self):
        self.assertEqual(sum(len(j['cases']) for j in plan('paired')), 430)
        jobs = plan('all')
        self.assertEqual(sum(len(j['cases']) for j in jobs), 615)
        self.assertTrue(all(len(j['cases']) <= 20 for j in jobs))
        main = json.loads((BUNDLE / 'data/current-english-manifest.json').read_text())['episodes']
        paired = json.loads((BUNDLE / 'data/current-counterfactual-manifest.json').read_text())['episodes']
        entries = {True: {e['case']: e for e in paired}, False: {e['case']: e for e in main}}
        configs = [tuple(entries[j['paired']][case]['files'][key] for key in ['hidden', 'visible', 'rubrics'])
                   for j in jobs for case in j['cases']]
        self.assertEqual(len(set(configs)), 615)


if __name__ == '__main__':
    unittest.main()
