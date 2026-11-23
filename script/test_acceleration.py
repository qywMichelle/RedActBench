"""Offline concurrency, routing, lock and frozen replay verification."""
import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error

import accelerated_bridge
import throughput_overlay

ROOT = Path(__file__).resolve().parent
LAB = ROOT / 'github_test_bundle/output/performance/lab/github_test_bundle'
PYTHON = str(ROOT / 'github_test_bundle/.venv/bin/python')


class FakeClock:
    def __init__(self): self.now = 0.
    def clock(self): return self.now
    def wait(self, n): self.now += n


class NativeHandler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        with self.server.guard:
            self.server.active += 1
            self.server.maximum = max(self.server.maximum, self.server.active)
            self.server.received.append(body)
        time.sleep(.12)
        text = json.dumps({'action': 'FINISH', 'text': 'Offline concurrency test marker.'})
        if self.path.endswith('/messages'):
            raw = {'model': body['model'], 'content': [{'type': 'text', 'text': text}],
                   'stop_reason': 'end_turn', 'usage': {'input_tokens': 10, 'output_tokens': 5}}
        else:
            raw = {'model': body['model'], 'output': [{'type': 'message', 'content': [
                    {'type': 'output_text', 'text': text}]}], 'status': 'completed',
                   'usage': {'input_tokens': 10, 'output_tokens': 5}}
        data = json.dumps(raw).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers()
        self.wfile.write(data)
        with self.server.guard: self.server.active -= 1


class AccelerationTest(unittest.TestCase):
    def test_pacing_backoff_preserves_unique_slots(self):
        clock = FakeClock()
        pacer = accelerated_bridge.AdaptivePacer(clock=clock.clock, wait=clock.wait,
            initial={'m': 2.}, floors={'m': .5})
        self.assertEqual(pacer.acquire('m'), 0.)
        self.assertEqual(pacer.acquire('m'), 2.)
        for _ in range(20): pacer.notice('m', 200)
        self.assertAlmostEqual(pacer.snapshot()['m']['interval'], 1.7)
        pacer.notice('m', 429)
        self.assertEqual(pacer.snapshot()['m']['successes'], 0)
        self.assertGreaterEqual(pacer.acquire('m'), 3.4)
        first = clock.now
        pacer.acquire('m')
        self.assertGreaterEqual(clock.now - first, 3.4)
        pacer.notice('m', 429, legacy=True)
        self.assertGreaterEqual(pacer.acquire('m'), 60.)

    def test_routing_preserves_exact_payload_headers_and_method(self):
        class Capture:
            def open(self, req, **kwargs): self.req = req; self.kwargs = kwargs; return 3
        original = Capture()
        opener = throughput_overlay.RoutingOpener(original, 'http://legacy/v1/chat/completions',
                                                  'http://fast/v1/chat/completions')
        request = urllib.request.Request('http://legacy/v1/chat/completions', data=b'{"unchanged":1}',
            headers={'Authorization': 'Bearer dummy', 'Content-Type': 'application/json'})
        self.assertEqual(opener.open(request, timeout=300), 3)
        self.assertEqual(original.req.data, request.data)
        self.assertEqual(dict(original.req.header_items()), dict(request.header_items()))
        self.assertEqual(original.req.get_method(), request.get_method())
        self.assertEqual(original.req.full_url, 'http://fast/v1/chat/completions')
        self.assertEqual(original.kwargs['timeout'], 300)
        other = urllib.request.Request('http://other', data=b'a')
        opener.open(other)
        self.assertIs(original.req, other)
        opener = throughput_overlay.RoutingOpener(original, 'http://legacy/v1/chat/completions',
            'http://fast/v1/chat/completions', redirect_legacy=False)
        opener.open(request)
        self.assertIs(original.req, request)

    def test_all_concurrent_waiters_receive_fair_slots(self):
        pacer = accelerated_bridge.AdaptivePacer(initial={'m': .01}, floors={'m': .01})
        pacer.state('m')['next_slot'] = time.monotonic() + .05
        barrier = threading.Barrier(3)
        received = []
        def worker(index):
            barrier.wait()
            for _ in range(5):
                pacer.acquire('m')
                received.append(index)
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=3)
        self.assertEqual(len(received), 15)
        self.assertEqual(sorted(received[:6]), [0, 0, 1, 1, 2, 2])

    def test_upload_budget_released_after_exception(self):
        budget = accelerated_bridge.UploadBudget(128 * 1024)
        with self.assertRaises(ValueError):
            with budget.reserve(1000000):
                self.assertEqual(budget.used, budget.maximum)
                raise ValueError('mock')
        self.assertEqual(budget.used, 0)

    def test_dead_auxiliary_bridge_falls_back_without_changing_bytes(self):
        class Capture:
            def __init__(self): self.urls = []
            def open(self, request):
                self.urls.append(request.full_url)
                if request.full_url == 'http://fast':
                    raise urllib.error.URLError(ConnectionRefusedError('mock refused'))
                return request.data
        capture = Capture()
        opener = throughput_overlay.RoutingOpener(capture, 'http://legacy', 'http://fast')
        request = urllib.request.Request('http://legacy', data=b'exact-payload')
        self.assertEqual(opener.open(request), b'exact-payload')
        self.assertEqual(capture.urls, ['http://fast', 'http://legacy'])
        capture = Capture()
        opener = throughput_overlay.RoutingOpener(capture, 'http://legacy', 'http://fast', enabled=False)
        self.assertEqual(opener.open(urllib.request.Request('http://fast', data=b'exact-payload')), b'exact-payload')
        self.assertEqual(capture.urls, ['http://legacy'])

    def test_parallel_real_clis_and_original_replay_and_export(self):
        native = ThreadingHTTPServer(('127.0.0.1', 0), NativeHandler)
        native.guard = threading.Lock(); native.active = native.maximum = 0; native.received = []
        thread = threading.Thread(target=native.serve_forever, daemon=True); thread.start()
        with tempfile.TemporaryDirectory(dir=ROOT / 'github_test_bundle/output/performance') as temp:
            temp = Path(temp)
            runs = [temp / str(index) for index in range(4)]
            pacer = accelerated_bridge.AdaptivePacer(initial={'gpt-6.1-sol-science': .01,
                'claude-opus-5-5-science': .01}, floors={'gpt-6.1-sol-science': .01,
                'claude-opus-5-5-science': .01})
            server = accelerated_bridge.Server(('127.0.0.1', 0), 'dummy-test-key', temp / 'ledger.jsonl',
                upstream=f'http://127.0.0.1:{native.server_port}/v1', pacer=pacer)
            bridge = threading.Thread(target=server.serve_forever, daemon=True); bridge.start()
            control = temp / 'control.json'
            control.write_text(json.dumps({'enabled': True,
                'redirect_legacy': True,
                'legacy_endpoint': 'http://127.0.0.1:1/v1/chat/completions',
                'accelerated_endpoint': f'http://127.0.0.1:{server.server_port}/v1/chat/completions',
                'owned_runs': list(map(str, runs)),
                'owned_exports': {str(run): str(run) + '.zip' for run in runs}}))
            startup_config = temp / 'startup.json'
            startup_config.write_text(json.dumps({'enabled': True, 'entrypoints': [str(LAB / 'redact_bench.py')],
                'source': str(ROOT / 'performance_overlay.py'),
                'source_sha256': hashlib.sha256((ROOT / 'performance_overlay.py').read_bytes()).hexdigest(),
                'cache_directory': str(temp / 'replay-cache'), 'activation_log': str(temp / 'activation.jsonl'),
                'extra': {'source': str(ROOT / 'throughput_overlay.py'),
                    'sha256': hashlib.sha256((ROOT / 'throughput_overlay.py').read_bytes()).hexdigest(),
                    'config': str(control)}}))
            bootstrap = ('import sys,runpy; sys.path.insert(0,' + repr(str(ROOT)) + '); '
                'import redact_performance_startup as s; cfg=sys.argv[1]; sys.argv=sys.argv[2:]; '
                's.configure(cfg); runpy.run_path(sys.argv[0],run_name="__main__")')
            prefix = [PYTHON, '-S', '-c', bootstrap, str(startup_config), str(LAB / 'redact_bench.py')]
            children = []
            try:
                for index, model in enumerate(['claude-opus-5-5-science', 'gpt-6.1-sol-science',
                                               'claude-opus-5-5-science', 'gpt-6.1-sol-science']):
                    run = temp / str(index)
                    command = prefix + ['run', '--url',
                        'http://127.0.0.1:1/v1', '--model', model,
                        '--api-key-env', 'REDACT_TEST_KEY', '--case', f'batch_020/t1-0{index + 1}',
                        '--max-tokens', '16384', '--max-requests', '200', '--output', str(run)]
                    child = subprocess.Popen(command, env=dict(os.environ, REDACT_TEST_KEY='dummy-test-key'),
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    children.append((child, run))
                    if index == 0:
                        duplicate = subprocess.Popen(command,
                            env=dict(os.environ, REDACT_TEST_KEY='dummy-test-key'),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        children.append((duplicate, run))
                for child, run in children:
                    out, error = child.communicate(timeout=30)
                    self.assertEqual(child.returncode, 0, out + error)
                    commands = [['check-run', '--run', str(run)]]
                    if not Path(str(run) + '.zip').exists():
                        commands.append(['export', '--run', str(run), '--output', str(run) + '.zip'])
                    for command in commands:
                        result = subprocess.run([PYTHON, '-S', str(LAB / 'redact_bench.py')] + command,
                            text=True, capture_output=True, timeout=30)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    # A main worker concurrently requesting the existing official
                    # export validates and reuses it instead of failing the model.
                    result = subprocess.run(prefix + ['export', '--run', str(run),
                        '--output', str(run) + '.zip'], text=True, capture_output=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('reused_concurrent_export', result.stdout)
                    for path in run.rglob('*.json'):
                        self.assertNotIn('dummy-test-key', path.read_text())
                self.assertGreaterEqual(native.maximum, 2)
                self.assertEqual(len(native.received), 4)
                activations = [json.loads(line) for line in (temp / 'activation.jsonl').read_text().splitlines()]
                self.assertTrue(all(row.get('throughput_enabled') for row in activations))
                for body in native.received:
                    self.assertEqual(body.get('max_tokens', body.get('max_output_tokens')), 16384)
                    self.assertNotIn('Offline concurrency test marker.', json.dumps(body))
            finally:
                for child, run in children:
                    if child.poll() is None:
                        child.kill(); child.communicate()
                server.shutdown(); server.server_close(); bridge.join()
        native.shutdown(); native.server_close(); thread.join()

    def test_owned_lock_wait_and_concurrent_export(self):
        spec = importlib.util.spec_from_file_location('lock_bench', LAB / 'redact_bench.py')
        bench = importlib.util.module_from_spec(spec); spec.loader.exec_module(bench)
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp); output = run / 'export.zip'
            throughput_overlay.install(bench, {'enabled': True, 'legacy_endpoint': 'http://unused',
                'accelerated_endpoint': 'http://unused2', 'owned_runs': [str(run)],
                'owned_exports': {str(run): str(output)}})
            holder = subprocess.Popen([PYTHON, '-c',
                'import fcntl,sys,time; f=open(sys.argv[1],"a+"); fcntl.flock(f,fcntl.LOCK_EX); print("ready",flush=True); time.sleep(.7)',
                str(run / '.run.lock')], stdout=subprocess.PIPE, text=True)
            self.assertEqual(holder.stdout.readline().strip(), 'ready')
            started = time.monotonic()
            with bench.recovery.writer_lock(run): pass
            self.assertGreaterEqual(time.monotonic() - started, .65)
            holder.wait(timeout=2)
            holder.stdout.close()
            # A body exception must still release the original lock.
            with self.assertRaises(ValueError):
                with bench.recovery.writer_lock(run): raise ValueError('mock')
            with bench.recovery.writer_lock(run): pass


if __name__ == '__main__': unittest.main(verbosity=2)
