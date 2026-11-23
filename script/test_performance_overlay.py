"""Offline equivalence, checkpoint and cache validation; never calls model APIs."""
import argparse
import base64
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest

import performance_overlay as overlay

ROOT = Path(__file__).resolve().parent
LAB = ROOT / 'github_test_bundle/output/performance/lab/github_test_bundle'
COPY_DEFAULTS = {name: getattr(copy, name).__defaults__ for name in
                 ['_deepcopy_dict', '_deepcopy_list', '_deepcopy_tuple']}
RECONSTRUCT_DEFAULTS = dict(copy._reconstruct.__kwdefaults__)


def reset_copy():
    copy.deepcopy = overlay.ORIGINAL_DEEPCOPY
    for name, defaults in COPY_DEFAULTS.items():
        getattr(copy, name).__defaults__ = defaults
    copy._reconstruct.__kwdefaults__.update(RECONSTRUCT_DEFAULTS)


class OverlayTest(unittest.TestCase):
    def setUp(self):
        reset_copy()
        self.addCleanup(reset_copy)

    def test_copy_aliases_cycles_custom_and_memo(self):
        class Custom:
            def __deepcopy__(self, memo):
                return ('custom', copy.deepcopy(self.value, memo))
        class Reduced:
            def __reduce__(self):
                return (dict, ([('reduced', 3)],))
        custom = Custom()
        custom.value = [1, '你好', None]
        shared = [1, {'a': 2}]
        cyclic = [shared, shared, custom, Reduced(), (shared, 'abc')]
        cyclic.append(cyclic)
        baseline = copy.deepcopy(cyclic)
        overlay.install_fast_copy()
        actual = copy.deepcopy(cyclic)
        self.assertEqual(actual[:-1], baseline[:-1])
        self.assertIs(actual[0], actual[1])
        self.assertIs(actual[-1], actual)
        self.assertIs(actual[4][0], actual[0])
        actual[0][1]['a'] = 9
        self.assertEqual(shared[1]['a'], 2)
        for value in [None, True, 12, 1.5, 's', b'bytes']:
            replacement = object()
            self.assertIs(copy.deepcopy(value, {id(value): replacement}), replacement)
        tup = (1, 'two')
        self.assertIs(copy.deepcopy(tup), tup)
        self.assertEqual(copy.deepcopy({(1, 2): {3, 4}}), {(1, 2): {3, 4}})

    def test_png_cache_bounded_exact_and_delegation(self):
        cache = overlay.Base64Cache(max_bytes=2048)
        for n in range(1, 100):
            data = overlay.PNG + bytes([n]) * 150
            expected = base64.b64encode(data)
            self.assertEqual(cache.b64encode(data), expected)
            self.assertEqual(cache.b64encode(data).decode(), expected.decode())
            self.assertLessEqual(cache.size, cache.max_bytes)
        for data in [b'ordinary', bytearray(overlay.PNG), memoryview(overlay.PNG)]:
            self.assertEqual(cache.b64encode(data), base64.b64encode(data))
        self.assertEqual(cache.b64encode(overlay.PNG, b'-_'), base64.b64encode(overlay.PNG, b'-_'))
        self.assertGreater(cache.hits, 0)
        self.assertLess(len(cache.cache), 10)

    def test_compact_writer_preserves_values_and_metadata(self):
        def original(path, value):
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        write = overlay.compact_trajectory_writer(original)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'trace.json'
            record = dict(case='a', calls=[{'你好': 'x\ny'}], simulation={'number': 1.5}, status='running')
            original(path, record)
            pretty = path.read_bytes()
            write(path, record)
            self.assertEqual(json.loads(path.read_text()), json.loads(pretty))
            self.assertLess(len(path.read_bytes()), len(pretty))
            self.assertFalse(path.with_suffix('.json.tmp').exists())
            metadata = {'url': 'mock', 'max_tokens': 16384}
            original(path, metadata)
            expected = path.read_bytes()
            write(path, metadata)
            self.assertEqual(path.read_bytes(), expected)

    def test_real_replay_cache_and_mutation_rejection(self):
        spec = importlib.util.spec_from_file_location('test_lab_bench', LAB / 'redact_bench.py')
        bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bench)
        source = ROOT / 'github_test_bundle/output/ab-eval-20261119/claude-opus-5-5-science/runs/paired-000'
        with tempfile.TemporaryDirectory(dir=ROOT / 'github_test_bundle/output/performance') as temp:
            temp = Path(temp)
            run = temp / 'run'
            shutil.copytree(source, run)
            before = time.perf_counter()
            baseline = bench.check_run(run)
            baseline_seconds = time.perf_counter() - before
            replay = overlay.install(bench, temp / 'cache')
            before = time.perf_counter()
            self.assertEqual(bench.check_run(run), baseline)
            optimized_seconds = time.perf_counter() - before
            before = time.perf_counter()
            cached = bench.check_run(run)
            cache_seconds = time.perf_counter() - before
            self.assertEqual(cached, baseline)
            self.assertEqual(replay.hits, 1)
            cached['cases'].clear()
            self.assertEqual(bench.check_run(run), baseline)
            # Full content hashes detect a change even with identical mtime.
            trace = next((run / 'trajectories').rglob('*.json'))
            original = trace.read_bytes()
            record = json.loads(original)
            record['calls'][0]['response']['request_body_sha256'] = '0' * 64
            trace.write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                bench.check_run(run)
            trace.write_bytes(original)
            config = run / 'run_config.json'
            original_config = config.read_bytes()
            config.write_text('{}')
            with self.assertRaises((ValueError, KeyError)):
                bench.check_run(run)
            config.write_bytes(original_config)
            # Frozen input integrity is checked even on a cache hit.
            entry = bench.load(run / 'frozen-manifest.json')['episodes'][0]
            hidden = LAB / 'data' / entry['files']['hidden']
            hidden_bytes = hidden.read_bytes()
            try:
                hidden.write_bytes(hidden_bytes + b' ')
                with self.assertRaises(ValueError):
                    bench.check_run(run)
            finally:
                hidden.write_bytes(hidden_bytes)
            # The original checker must accept compact trajectory bytes too.
            for path in (run / 'trajectories').rglob('*.json'):
                bench.core.write(path, bench.load(path))
            self.assertEqual(replay.original(run), baseline)
            report = {'trajectories': baseline['trajectories_replayed'],
                      'baseline_seconds': baseline_seconds,
                      'optimized_seconds': optimized_seconds, 'cache_seconds': cache_seconds}
            (ROOT / 'github_test_bundle/output/performance/overlay-replay-benchmark.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    unittest.main(verbosity=2)
