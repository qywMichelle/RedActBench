"""Equivalent caches/serialization over the unchanged frozen benchmark files."""
import base64
from collections import OrderedDict
import copy
import hashlib
import json
from pathlib import Path
import threading
import time

VERSION = 'redact-performance-overlay-v1'
PNG = b'\x89PNG\r\n\x1a\n'
ORIGINAL_DEEPCOPY = copy.deepcopy
ATOMIC = {type(None), bool, int, float, str, bytes}
NIL = ORIGINAL_DEEPCOPY.__defaults__[1]


def fast_deepcopy(value, memo=None, _nil=NIL):
    if type(value) in ATOMIC:
        if memo is not None:
            result = memo.get(id(value), _nil)
            if result is not _nil:
                return result
        return value
    return ORIGINAL_DEEPCOPY(value, memo)


def install_fast_copy():
    copy.deepcopy = fast_deepcopy
    # The standard helpers captured deepcopy as a default argument. Preserve
    # their original implementation, memo, cycles, aliases and custom hooks.
    for name in ['_deepcopy_dict', '_deepcopy_list', '_deepcopy_tuple']:
        function = getattr(copy, name)
        function.__defaults__ = (fast_deepcopy,)
    if 'deepcopy' in (copy._reconstruct.__kwdefaults__ or {}):
        copy._reconstruct.__kwdefaults__['deepcopy'] = fast_deepcopy


class EncodedPNG(bytes):
    def __new__(cls, value):
        result = bytes.__new__(cls, value)
        result.text = bytes.decode(result)
        return result

    def decode(self, encoding='utf-8', errors='strict'):
        if encoding.lower().replace('_', '-') in {'utf-8', 'utf8', 'ascii', 'us-ascii'}:
            return self.text
        return bytes.decode(self, encoding, errors)


class Base64Cache:
    def __init__(self, original=base64, max_bytes=16 * 1024 * 1024):
        self.original = original
        self.cache = OrderedDict()
        self.max_bytes, self.size = max_bytes, 0
        self.lock = threading.Lock()
        self.hits = self.misses = 0

    def __getattr__(self, name):
        return getattr(self.original, name)

    def b64encode(self, data, altchars=None):
        if type(data) is not bytes or not data.startswith(PNG) or altchars is not None:
            return self.original.b64encode(data, altchars)
        with self.lock:
            if data in self.cache:
                value, weight = self.cache.pop(data)
                self.cache[data] = (value, weight)
                self.hits += 1
                return value
            value = EncodedPNG(self.original.b64encode(data))
            weight = len(data) + len(value) + len(value.text)
            self.misses += 1
            if weight <= self.max_bytes:
                while self.cache and self.size + weight > self.max_bytes:
                    _, (_, old_size) = self.cache.popitem(last=False)
                    self.size -= old_size
                self.cache[data] = (value, weight)
                self.size += weight
            return value


def compact_trajectory_writer(original):
    def write(path, value):
        if not (isinstance(value, dict) and {'case', 'calls', 'simulation', 'status'} <= value.keys()):
            return original(path, value)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
        temporary.replace(path)
    return write


def fingerprint(bench, run):
    manifest_path = bench.core.run_manifest_path(run)
    manifest = bench.load(manifest_path)
    paths = [run / 'run_config.json', manifest_path, run / 'run-binding.json']
    integrity = run / 'trace-integrity.json'
    if integrity.exists():
        paths.append(integrity)
        for relative in bench.load(integrity):
            relative = Path(relative)
            if relative.is_absolute() or '..' in relative.parts:
                return None
            paths.append(run / relative)
    paths.extend(bench.core.trajectory_path(run, entry) for entry in manifest['episodes'])
    hashes = []
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(run.resolve()):
            return None
        hashes.append((str(path.relative_to(run)), bench.core.file_sha(path) if path.is_file() else None))
    return bench.core.digest({'version': VERSION, 'files': hashes,
        'inventory': bench.core.file_sha(bench.ROOT / 'SHA256SUMS.json'),
        'source': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})


class ReplayCache:
    def __init__(self, bench, directory):
        self.bench, self.directory = bench, Path(directory)
        self.original = bench.check_run
        self.hits = self.misses = 0

    def event(self, run, report, hit, started):
        try:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            with (self.directory / 'events.jsonl').open('a') as stream:
                stream.write(json.dumps({'time': time.time(), 'run': str(run), 'cache_hit': hit,
                    'seconds': round(time.monotonic() - started, 6),
                    'trajectories': report['trajectories_replayed']}, separators=(',', ':')) + '\n')
        except OSError:
            pass

    def __call__(self, run, allow_empty=False):
        started = time.monotonic()
        run = Path(run).resolve()
        manifest = self.bench.load(self.bench.core.run_manifest_path(run))
        # Never trust metadata-only caches: validate frozen data/code bytes,
        # config, binding, every current trace and imported integrity members.
        self.bench.check_integrity(manifest['episodes'])
        key = fingerprint(self.bench, run)
        path = self.directory / (hashlib.sha256(str(run).encode()).hexdigest() + '.json')
        if key is not None and path.is_file():
            try:
                stored = json.loads(path.read_text())
                if (stored['fingerprint'] == key and
                        stored['report_sha256'] == self.bench.core.digest(stored['report'])):
                    report = stored['report']
                    if report['trajectories_replayed'] or allow_empty:
                        self.hits += 1
                        self.event(run, report, True, started)
                        return ORIGINAL_DEEPCOPY(report)
            except (OSError, KeyError, ValueError):
                pass
        self.misses += 1
        report = self.original(run, allow_empty=allow_empty)
        if key is not None and key == fingerprint(self.bench, run):
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'fingerprint': key, 'report': report,
                'report_sha256': self.bench.core.digest(report)}, separators=(',', ':')))
            temporary.chmod(0o600)
            temporary.replace(path)
        self.event(run, report, False, started)
        return report


def install(bench, cache_directory):
    install_fast_copy()
    bench.base64 = Base64Cache(bench.base64)
    bench.core.write = compact_trajectory_writer(bench.core.write)
    replay = ReplayCache(bench, cache_directory)
    bench.check_run = replay
    return replay
