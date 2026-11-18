"""Resolve current or archived data strictly by frozen content bindings.

Archive lookup is read-only. It never repairs a manifest, follows an unbound
fallback, or combines runtime dependencies from different snapshots.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def data_roots(repository_root=ROOT):
    root = Path(repository_root).resolve()
    return [root / 'data', *sorted((root / 'archive').glob('*/data'))]


def _relative(value):
    value = Path(value)
    if value.is_absolute() or not value.parts or '..' in value.parts:
        raise ValueError(f'Expected a safe data-relative path: {value}')
    return value


def resolve_data_path(relative, expected_sha256, repository_root=ROOT):
    """Prefer current data only if its bytes match the explicit expected SHA."""
    relative = _relative(relative)
    if not expected_sha256:
        raise ValueError(f'A content SHA256 is required to resolve {relative}')
    for base in data_roots(repository_root):
        candidate = base / relative
        if candidate.is_file() and file_sha(candidate) == expected_sha256:
            return candidate.resolve()
    raise FileNotFoundError(f'No current/archive data file matches {relative} SHA256 {expected_sha256}')


def resolve_saved_path(path, expected_sha256, repository_root=ROOT):
    """Resolve a saved absolute data/image path without rewriting its metadata."""
    path = Path(path)
    if not path.is_absolute():
        return resolve_data_path(path, expected_sha256, repository_root)
    for base in data_roots(repository_root):
        try:
            relative = path.relative_to(base)
        except ValueError:
            continue
        return resolve_data_path(relative, expected_sha256, repository_root)
    raise ValueError(f'Saved path is outside current/archive data roots: {path}')


def resolve_run_manifest(run, repository_root=ROOT):
    """Use saved selection bytes, or a SHA-bound historical index; never guess."""
    run = Path(run)
    config_path = run / 'run_config.json'
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    expected = config.get('current_manifest_sha256')
    frozen = run / 'frozen-manifest.json'
    if frozen.exists():
        if expected and file_sha(frozen) != expected:
            raise ValueError('Saved frozen manifest does not match run configuration')
        return frozen
    if not expected:
        raise ValueError('Historical run has no frozen manifest or manifest SHA256 binding')
    return resolve_data_path('current-english-manifest.json', expected, repository_root)


def resolve_runtime_root(entry, repository_root=ROOT):
    """Find one complete runtime root matching every frozen Python dependency."""
    relative_root = _relative(entry['runtime_root'])
    bindings = entry.get('runtime_files')
    if not bindings:
        raise ValueError('runtime_files SHA256 bindings are required; unbound archive lookup is forbidden')
    dependencies = {}
    for relative, expected in bindings.items():
        relative = _relative(relative)
        try:
            child = relative.relative_to(relative_root)
        except ValueError as exc:
            raise ValueError(f'Runtime dependency lies outside declared root: {relative}') from exc
        if not expected:
            raise ValueError(f'Missing runtime dependency SHA256: {relative}')
        dependencies[child] = expected
    for base in data_roots(repository_root):
        candidate = base / relative_root
        if not candidate.is_dir():
            continue
        if {p.relative_to(candidate) for p in candidate.rglob('*.py')} != set(dependencies):
            continue
        if all((candidate / child).is_file() and file_sha(candidate / child) == expected
               for child, expected in dependencies.items()):
            return candidate.resolve()
    raise FileNotFoundError(f'No complete current/archive runtime matches frozen dependencies: {relative_root}')
