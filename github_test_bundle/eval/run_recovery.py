"""Bound configuration, exclusive writers and preserved checkpoint prefixes."""
from argparse import Namespace
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import shutil
import uuid

import run_current_english_gemini as core
from checkpoint_replay import TERMINAL

SCHEMA = 'redact-collaborator-behavior-test-v2'
DEFAULTS = dict(protocol='openai', max_tokens=4096, max_requests=200,
                max_prompt_chars=200000, temperature=1.0, top_p=.95, seed=0,
                timeout=180, no_auth=False, api_key_env='REDACT_API_KEY')
BOUND_OPTIONS = ('protocol', 'model', 'max_tokens', 'max_requests', 'max_prompt_chars',
                 'temperature', 'top_p', 'seed', 'timeout', 'no_auth')
SOURCES = ('redact_bench.py', 'eval/run_current_english_gemini.py',
           'eval/run_local_construction_models.py', 'eval/revealed_context.py',
           'eval/evidence_images.py', 'eval/data_paths.py',
           'eval/checkpoint_replay.py', 'eval/run_recovery.py')


def load(path):
    return json.loads(path.read_text())


def code_binding():
    return {name: core.file_sha(core.ROOT / name) for name in SOURCES}


def resolve(args, select, normalize_endpoint):
    """Resume uses the saved selection and fills omitted options from its config."""
    if not args.resume:
        for name, default in DEFAULTS.items():
            if getattr(args, name) is None:
                setattr(args, name, default)
        if not args.url or not args.model:
            raise ValueError('New runs require --url and --model')
        args.paired = bool(args.paired)
        args.endpoint = normalize_endpoint(args.url, args.protocol)
        path, manifest, entries = select(args)
        manifest = dict(manifest, episodes=entries, test_selection_count=len(entries))
        config = dict(schema=SCHEMA, source_manifest_sha256=core.file_sha(path),
                      bundle_inventory_sha256=core.file_sha(core.ROOT / 'SHA256SUMS.json'),
                      runner_files=code_binding(), cases=[e['case'] for e in entries],
                      selection=dict(paired=args.paired, case=args.case, limit=args.limit),
                      context_binding=core.context_binding(args), url=args.endpoint,
                      api_key_env=args.api_key_env, formal_evaluation_ready=False,
                      semantic_scoring=False,
                      **{name: getattr(args, name) for name in BOUND_OPTIONS})
        return manifest, entries, config

    config_path = args.output / 'run_config.json'
    if not config_path.is_file():
        raise ValueError('--resume requires an existing run_config.json')
    config = load(config_path)
    if config.get('schema') != SCHEMA:
        raise ValueError('Legacy checkpoint: use its original frozen runner; this version cannot resume v1 runs')
    if config['runner_files'] != code_binding():
        raise ValueError('Runner changed; resume requires the original frozen code')
    if config['bundle_inventory_sha256'] != core.file_sha(core.ROOT / 'SHA256SUMS.json'):
        raise ValueError('Bundle changed; resume requires the original frozen bundle')
    manifest = load(core.run_manifest_path(args.output))
    if [e['case'] for e in manifest['episodes']] != config['cases']:
        raise ValueError('Saved case selection does not match run configuration')
    for name in BOUND_OPTIONS:
        value = getattr(args, name)
        if value is not None and value != config[name]:
            raise ValueError('Resume option changed: --' + name.replace('_', '-'))
        setattr(args, name, config[name])
    args.endpoint = config['url']
    if args.url is not None and normalize_endpoint(args.url, args.protocol) != args.endpoint:
        raise ValueError('Resume API URL changed')
    args.url = args.endpoint
    if args.api_key_env is None:
        args.api_key_env = config['api_key_env']
    selection = config['selection']
    selector = Namespace(paired=selection['paired'] if args.paired is None else args.paired,
                         case=selection['case'] if args.case is None else args.case,
                         limit=selection['limit'] if args.limit is None else args.limit)
    path, current, entries = select(selector)
    current = dict(current, episodes=entries, test_selection_count=len(entries))
    if core.file_sha(path) != config['source_manifest_sha256'] or current != manifest:
        raise ValueError('Resume selection or frozen manifest changed')
    if core.context_binding(args) != config['context_binding']:
        raise ValueError('Resume context encoder changed')
    return manifest, entries, config


@contextmanager
def writer_lock(output):
    """Keep the lock file; flock is released by the OS even after SIGKILL."""
    with (output / '.run.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another process is writing this run directory') from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def preserve_prefix(output, entries):
    identifier = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
    backup = output / 'resume-backups' / identifier
    backup.mkdir(parents=True)
    names = ['run_config.json', 'frozen-manifest.json', 'execution-summary.json',
             'preflight-error.json', 'trace-integrity.json', 'replay-verification.json', 'resume-log.json']
    checkpoints = {}
    for entry in entries:
        path = core.trajectory_path(output, entry)
        if path.is_file():
            relative = str(path.relative_to(output))
            checkpoints[relative] = core.file_sha(path)
            if load(path)['status'] not in TERMINAL:
                names.append(relative)
    copied = {}
    for name in names:
        path = output / name
        if path.is_file():
            target = backup / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            copied[name] = core.file_sha(target)
    core.write(backup / 'snapshot.json', dict(files=copied, checkpoint_hashes=checkpoints))
    # Imported exports remain immutable evidence inside this backup. The current
    # run now evolves and will receive a new integrity ledger at its next export.
    for name in ('trace-integrity.json', 'replay-verification.json'):
        if (output / name).is_file():
            (output / name).unlink()
    path = output / 'resume-log.json'
    history = load(path) if path.is_file() else []
    history.append(dict(id=identifier, status='started', backup=str(backup.relative_to(output))))
    core.write(path, history)
    return identifier


def finish_resume(output, identifier, status):
    if identifier is None:
        return
    path = output / 'resume-log.json'
    history = load(path)
    next(item for item in history if item['id'] == identifier)['status'] = status
    core.write(path, history)
