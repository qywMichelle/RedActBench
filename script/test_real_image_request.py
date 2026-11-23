"""Exercise the exact blocked HTTP body under the production memory limit."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import resource
import struct
import tempfile
import threading
import unittest
import urllib.request

import provider_bridge
import resume_with_image_budget as revision


class NativeFixture(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.received = body
        raw = {'id': 'offline-real-body', 'model': body['model'], 'status': 'completed',
               'output': [{'type': 'message', 'content': [{'type': 'output_text',
                           'text': '{"action":"FINISH","text":"Offline fixture only."}'}]}],
               'usage': {'input_tokens': 10, 'output_tokens': 5}}
        if self.path.endswith('/messages'):
            raw.update(stop_reason='end_turn', content=[{'type': 'text',
                'text': '{"action":"FINISH","text":"Offline fixture only."}'}])
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(raw).encode())


class RealRequestTest(unittest.TestCase):
    def test_opus_route_preserves_requested_identity_and_reports_actual_model(self):
        body = {'model': 'claude-opus-5-5-science', 'max_tokens': 16384,
                'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': 'visible fixture'}]}]}
        protocol, emitted = revision.translate(body)
        self.assertEqual(body['model'], 'claude-opus-5-5-science')
        self.assertEqual(protocol, 'messages')
        self.assertEqual(emitted['model'], 'claude-opus-5-5-hc')
        normalized = provider_bridge.normalize({'model': emitted['model'], 'stop_reason': 'end_turn',
            'content': [{'type': 'text', 'text': '{"action":"FINISH"}'}], 'usage': {}}, protocol)
        self.assertEqual(normalized['model'], 'claude-opus-5-5-hc')

    def exercise_full_request(self, messages=False):
        fixture = Path('github_test_bundle/output/api-preflight/blocked-request-fixture.json')
        self.assertTrue(fixture.exists())
        with tempfile.TemporaryDirectory() as tmp:
            native = ThreadingHTTPServer(('127.0.0.1', 0), NativeFixture)
            native.received = None
            original_translate, original_record = provider_bridge.translate, provider_bridge.Server.record
            provider_bridge.translate, provider_bridge.Server.record = revision.translate, revision.record
            bridge = provider_bridge.Server(('127.0.0.1', 0), 'offline-test', Path(tmp) / 'ledger.jsonl',
                     upstream=f'http://127.0.0.1:{native.server_port}/v1')
            threads = []
            for server in [native, bridge]:
                t = threading.Thread(target=server.serve_forever, daemon=True)
                t.start();threads.append(t)
            try:
                payload = fixture.read_bytes()
                if messages:
                    payload = payload.replace(b'"model": "gpt-6.1-sol-science"',
                                              b'"model": "claude-opus-5-5-science"', 1)
                request = urllib.request.Request(f'http://127.0.0.1:{bridge.server_port}/v1/chat/completions',
                     payload, {'Authorization': 'Bearer offline-test', 'Content-Type': 'application/json'})
                with urllib.request.urlopen(request, timeout=90) as response:
                    result = json.load(response)
                self.assertIn('FINISH', result['choices'][0]['message']['content'])
                emitted = native.received
                self.assertEqual(emitted['model'], 'claude-opus-5-5-hc' if messages else 'gpt-6.1-sol-science')
                parts = emitted['messages' if messages else 'input'][0]['content']
                images = [p for p in parts if p['type'] == ('image' if messages else 'input_image')]
                self.assertEqual(len(images), 4 if messages else 3)
                sizes = []
                for part in images:
                    encoded = part['source']['data'] if messages else part['image_url'].split(',', 1)[1]
                    data = base64.b64decode(encoded)
                    width, height = struct.unpack('>II', data[16:24])
                    self.assertLessEqual(revision.patches(width, height), revision.MAX_PATCHES)
                    self.assertLessEqual(len(encoded), revision.MAX_ENCODED_IMAGE_BYTES)
                    if messages:self.assertLessEqual(max(width, height), 8000)
                    sizes.append([width, height])
                ledger = [json.loads(line) for line in (Path(tmp) / 'ledger.jsonl').read_text().splitlines()]
                self.assertEqual(ledger[-1]['status'], 200)
                self.assertEqual(len(ledger[-1]['image_resizes']), 1)
                if messages:
                    tiled = ledger[-1]['image_tiles'][0]
                    self.assertTrue(tiled['full_canvas_covered'])
                    self.assertEqual(tiled['tiles'][0]['rectangle'][1], 0)
                    self.assertEqual(tiled['tiles'][-1]['rectangle'][3], tiled['full_canvas_size'][1])
                    self.assertLessEqual(tiled['tiles'][1]['rectangle'][1], tiled['tiles'][0]['rectangle'][3])
                print(json.dumps({'real_blocked_body_bytes': fixture.stat().st_size,
                                  'transmitted_image_sizes': sizes,
                                  'peak_rss_mib': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}))
            finally:
                for server in [bridge, native]:server.shutdown();server.server_close()
                for t in threads:t.join()
                provider_bridge.translate, provider_bridge.Server.record = original_translate, original_record

    def test_full_blocked_request_pipeline(self):
        self.exercise_full_request()

    def test_claude_byte_and_dimension_limits_preserve_all_tiles(self):
        self.exercise_full_request(messages=True)


if __name__ == '__main__':
    unittest.main()
