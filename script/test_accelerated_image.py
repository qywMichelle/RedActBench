"""Exact blocked HTTP request through v7, under the production memory limit."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import resource
import tempfile
import threading
import urllib.request

import accelerated_bridge


class Native(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_POST(self):
        raw = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        sha = hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True,
                                       separators=(',', ':')).encode()).hexdigest()
        del raw
        self.server.sha = sha
        payload = json.dumps({'model': 'claude-opus-5-5-hc', 'content': [{'type': 'text',
            'text': '{"action":"FINISH","text":"Offline full-image fixture."}'}],
            'stop_reason': 'end_turn', 'usage': {'input_tokens': 10, 'output_tokens': 5}}).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(payload))); self.end_headers()
        self.wfile.write(payload)


root = Path(__file__).resolve().parent
fixture = root / 'github_test_bundle/output/api-preflight/blocked-request-fixture.json'
expected = json.loads((root / 'github_test_bundle/output/performance/tile-cache-benchmark.json').read_text())['request_sha256']
with tempfile.TemporaryDirectory() as temp:
    native = ThreadingHTTPServer(('127.0.0.1', 0), Native)
    pacer = accelerated_bridge.AdaptivePacer(initial={'claude-opus-5-5-science': .01},
                                             floors={'claude-opus-5-5-science': .01})
    bridge = accelerated_bridge.Server(('127.0.0.1', 0), 'dummy-image-key', Path(temp) / 'ledger',
        upstream=f'http://127.0.0.1:{native.server_port}/v1', pacer=pacer)
    threads = []
    for server in [native, bridge]:
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start(); threads.append(thread)
    try:
        payload = fixture.read_bytes().replace(b'"model": "gpt-6.1-sol-science"',
                                               b'"model": "claude-opus-5-5-science"', 1)
        for _ in range(2):
            request = urllib.request.Request(f'http://127.0.0.1:{bridge.server_port}/v1/chat/completions',
                data=payload, headers={'Authorization': 'Bearer dummy-image-key', 'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.load(response)
            assert result['model'] == 'claude-opus-5-5-hc'
            assert native.sha == expected, 'Full native request SHA changed'
        rows = [json.loads(line) for line in (Path(temp) / 'ledger').read_text().splitlines()]
        assert all(row['status'] == 200 for row in rows)
        assert rows[0]['image_tiles'] == rows[1]['image_tiles']
        assert bridge.tile_cache.hits > 0
        report = {'native_request_sha256': native.sha, 'payload_bytes': len(payload),
            'first_translation_seconds': rows[0]['translation_seconds'],
            'cached_translation_seconds': rows[1]['translation_seconds'],
            'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            'full_request_and_tile_metadata_equivalent': True}
        (root / 'github_test_bundle/output/performance/accelerated-image-test.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    finally:
        for server in [bridge, native]: server.shutdown(); server.server_close()
        for thread in threads: thread.join()
