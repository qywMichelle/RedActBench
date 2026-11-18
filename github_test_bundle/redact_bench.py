"""Portable behavior tests and trace handoff; semantic scoring belongs to the owner."""
import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'eval'))
import run_current_english_gemini as core
import evidence_images as images
from checkpoint_replay import TERMINAL, context_args, restore
import run_recovery as recovery


def load(path):
    return json.loads(Path(path).read_text())


def manifest_path(paired=False):
    return ROOT / 'data' / ('current-counterfactual-manifest.json' if paired else
                           'current-english-manifest.json')


def select(args):
    path = manifest_path(args.paired)
    manifest = load(path)
    entries = manifest['episodes']
    if args.case:
        wanted = set(args.case)
        entries = [e for e in entries if e['case'] in wanted]
        if {e['case'] for e in entries} != wanted:
            raise ValueError('Unknown cases (use list or list --paired)')
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError('--limit must be positive')
        entries = entries[:args.limit]
    return path, manifest, entries


def check_integrity(entries=None):
    inventory = ROOT / 'SHA256SUMS.json'
    if not inventory.is_file():
        raise ValueError('Missing frozen bundle inventory')
    hashes = load(inventory)
    wanted, batches = set(), set()
    if entries is not None:
        refs = load(ROOT / 'data/reference-index.json')
        for entry in entries:
            wanted.update('data/' + p for p in entry['files'].values())
            wanted.update('data/' + p for p in entry['runtime_files'])
            wanted.add('data/' + entry['package_manifest'])
            wanted.add('data/' + refs[entry['case']]['path'])
            batches.add(Path(entry['files']['hidden']).parts[0])
        if not wanted <= hashes.keys():
            raise ValueError('Run requires files outside the frozen bundle inventory')
    checked = 0
    for relative, expected in hashes.items():
        parts = Path(relative).parts
        if entries is not None and len(parts) > 2 and parts[0] == 'data' and parts[1].startswith('batch_'):
            if relative not in wanted and not (parts[1] in batches and 'assets' in parts):
                continue
        path = ROOT / relative
        if not path.is_file() or core.file_sha(path) != expected:
            raise ValueError('Bundle file changed or missing: ' + relative)
        checked += 1
    return checked


def verify(args):
    count = check_integrity()
    _, _, entries = select(args)
    refs = load(ROOT / 'data/reference-index.json')
    for index, entry in enumerate(entries, 1):
        core.RUNTIME_CACHE.clear()
        sys.modules.pop('calculators', None)
        images.validate_inputs([entry])
        ref = refs[entry['case']]
        path = ROOT / 'data' / ref['path']
        if core.file_sha(path) != ref['sha256']:
            raise ValueError('Reference SHA mismatch')
        record = load(path)
        world = load(core.input_path(entry, 'hidden'))
        rubric = load(core.input_path(entry, 'rubrics'))
        binding = record.get('input_hashes', {})
        for key, kind in [('hidden', 'hidden'), ('data', 'hidden'), ('visible', 'visible'),
                          ('rubrics', 'rubrics'), ('rubric', 'rubrics')]:
            if binding.get(key) and binding[key] not in {
                entry['sha256'][kind], core.digest(world if kind == 'hidden' else
                rubric if kind == 'rubrics' else load(core.input_path(entry, kind)))}:
                raise ValueError('Reference input binding mismatch')
        _, replay = core.runtime(entry)
        replay(world, record.get('simulation', record))
        if index % 20 == 0:
            print(json.dumps({'verified': index, 'total': len(entries)}), flush=True)
    print(json.dumps({'status': 'pass', 'inventory_files': count,
                      'configurations': len(entries), 'reference_replays': len(entries),
                      'semantic_scoring': False}), flush=True)


def endpoint(url, protocol):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('URL must use http or https')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use a URL without embedded credentials, query or fragment')
    if protocol == 'gemini':
        if not parsed.path.endswith(':generateContent'):
            raise ValueError('Gemini mode requires the full :generateContent URL')
        return url
    url = url.rstrip('/')
    if url.endswith('/chat/completions'):
        return url
    return url + ('/chat/completions' if url.endswith('/v1') else '/v1/chat/completions')


def request_body(args, prompt, attachments):
    if args.protocol == 'gemini':
        parts = [{'text': prompt}]
        for ref, data in attachments:
            parts.extend([{'text': 'Original revealed evidence image: ' + json.dumps(ref)},
                          {'inlineData': {'mimeType': 'image/png',
                                          'data': base64.b64encode(data).decode()}}])
        body = {'model': args.model, 'contents': [{'role': 'user', 'parts': parts}],
                'generationConfig': {'temperature': args.temperature,
                                     'maxOutputTokens': args.max_tokens,
                                     'topP': args.top_p, 'seed': args.seed}}
    else:
        content = [{'type': 'text', 'text': prompt}]
        for ref, data in attachments:
            content.extend([{'type': 'text', 'text': 'Original revealed evidence image: ' + json.dumps(ref)},
                            {'type': 'image_url', 'image_url': {
                                'url': 'data:image/png;base64,' + base64.b64encode(data).decode()}}])
        body = {'model': args.model, 'messages': [{'role': 'user', 'content': content}],
                'max_tokens': args.max_tokens, 'temperature': args.temperature,
                'top_p': args.top_p, 'seed': args.seed}
    return body


def transport(key, opener, args, observation, error, interactions):
    prompt = core.build_prompt(args, observation, error, interactions)
    if args.max_prompt_chars and len(prompt) > args.max_prompt_chars:
        raise core.InputBudgetExceeded({'characters': len(prompt),
                                       'limit_characters': args.max_prompt_chars})
    attachments = images.attachments(args.active_entry, observation, interactions)
    body = request_body(args, prompt, attachments)
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['api-key' if args.protocol == 'gemini' else 'Authorization'] = (
            key if args.protocol == 'gemini' else 'Bearer ' + key)
    started = time.monotonic()
    for attempt in range(3):
        if getattr(args, 'stop_requested', False):
            raise KeyboardInterrupt
        try:
            req = urllib.request.Request(args.endpoint, json.dumps(body).encode(), headers)
            args.request_in_flight = True
            try:
                with opener.open(req, timeout=args.timeout) as response:
                    raw = json.load(response)
            finally:
                args.request_in_flight = False
            if args.protocol == 'gemini':
                candidate = raw['candidates'][0]
                text = ''.join(p.get('text', '') for p in candidate.get('content', {}).get('parts', [])
                               if not p.get('thought'))
                usage, finish = raw.get('usageMetadata', {}), candidate.get('finishReason')
                reported = raw.get('modelVersion')
            else:
                choice = raw['choices'][0]
                text = choice['message'].get('content') or ''
                usage, finish = raw.get('usage', {}), choice.get('finish_reason')
                reported = raw.get('model')
            return {'text': core.redact_error(text, key), 'usage': usage,
                    'finish_reason': finish, 'reported_model': reported,
                    'request_prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                    'context_binding': core.context_binding(args),
                    'input_context': {'characters': len(prompt), 'images': len(attachments),
                                      'prior_interactions': len(interactions)},
                    'image_inputs': [ref for ref, _ in attachments],
                    'request_body_sha256': core.digest(body), 'http_attempts': attempt + 1,
                    'latency_seconds': round(time.monotonic() - started, 3)}
        except urllib.error.HTTPError as exc:
            detail = core.redact_error(exc.read().decode(errors='replace'), key)[:1000]
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise RuntimeError(f'HTTP {exc.code}: {detail}') from None
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def run(args):
    if args.output.resolve().is_relative_to((ROOT / 'data').resolve()):
        raise ValueError('Output must be outside frozen data')
    if args.resume and not args.output.is_dir():
        raise ValueError('--resume requires an existing run directory')
    if not args.resume and args.output.exists() and any(
            p.name != '.run.lock' for p in args.output.iterdir()):
        raise ValueError('Output already contains a run; use --resume or a new directory')
    args.output.mkdir(parents=True, exist_ok=True)
    with recovery.writer_lock(args.output):
        if not args.resume and any(p.name != '.run.lock' for p in args.output.iterdir()):
            raise ValueError('Output already contains a run; use --resume or a new directory')
        return run_locked(args)


def run_locked(args):
    manifest, entries, config = recovery.resolve(args, select, endpoint)
    check_integrity(entries)
    if args.max_requests < 1 or args.max_tokens < 1 or args.max_prompt_chars < 0 or args.timeout < 1:
        raise ValueError('Invalid request, output, input or timeout budget')
    if args.resume:
        check_run(args.output, allow_empty=True)
        if all(core.trajectory_path(args.output, e).is_file() and
               load(core.trajectory_path(args.output, e))['status'] in TERMINAL for e in entries):
            print(json.dumps({'resume': 'nothing_to_resume', 'terminal_cases': len(entries),
                              'new_requests': 0}), flush=True)
            return
    key = '' if args.no_auth else (os.environ.get(args.api_key_env) or getpass.getpass('API key (hidden): '))
    if not key and not args.no_auth:
        raise ValueError('Empty API key; local unauthenticated servers may use --no-auth')
    # Prevent credentials in URLs or incidental prose from becoming artifacts.
    if key and (key in args.url or key in args.model):
        raise ValueError('Model and URL must not contain the API key')
    resume_id = recovery.preserve_prefix(args.output, entries) if args.resume else None
    if not args.resume:
        core.write(args.output / 'frozen-manifest.json', manifest)
        config['current_manifest_sha256'] = core.file_sha(args.output / 'frozen-manifest.json')
        core.write(args.output / 'run_config.json', config)
        recovery.seal_metadata(args.output)
    opener = urllib.request.build_opener()
    core.request = transport
    records = []
    args.stop_requested = args.request_in_flight = False

    def stop(signum, frame):
        args.stop_requested = True
        if args.request_in_flight:
            raise KeyboardInterrupt

    handlers = {s: signal.signal(s, stop) for s in (signal.SIGINT, signal.SIGTERM)}
    outcome = 'infrastructure_error'
    try:
        for entry in entries:
            if args.stop_requested:
                break
            path = core.trajectory_path(args.output, entry)
            if path.is_file() and load(path)['status'] in TERMINAL:
                record = load(path)
                records.append(record)
                print(json.dumps({'case': entry['case'], 'status': record['status'],
                                  'skipped_terminal': True, 'new_requests': 0}), flush=True)
                continue
            args.active_entry = entry
            core.RUNTIME_CACHE.clear()
            sys.modules.pop('calculators', None)
            try:
                images.validate_inputs([entry])
                record = core.run_one(key, opener, args, entry)
            except Exception as exc:
                core.write(args.output / 'preflight-error.json', {
                    'case': entry['case'], 'error': core.redact_error(str(exc), key)[:1000]})
                raise RuntimeError('Case preflight/replay failed; see preflight-error.json') from None
            records.append(record)
            if record['status'] in {'infrastructure_error', 'input_budget_exceeded', 'user_stopped'}:
                break
        outcome = 'user_stopped' if args.stop_requested else (
            'complete' if len(records) == len(entries) and all(r['status'] in TERMINAL for r in records)
            else 'infrastructure_error')
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        recovery.finish_resume(args.output, resume_id, outcome)
    summary = {'schema': 'redact-behavior-test-summary-v1', 'semantic_scoring': False,
               'selected': len(entries), 'attempted': len(records),
               'statuses': {s: sum(r['status'] == s for r in records)
                            for s in sorted({r['status'] for r in records})},
               'requests': sum(len(r['calls']) for r in records),
               'protocol_errors': sum(r['protocol_error_count'] for r in records),
               'requests_with_images': sum(bool(c['response'].get('image_inputs'))
                                          for r in records for c in r['calls']),
               'quality_note': 'Execution completion is not a semantic pass. Owner reviews the traces.'}
    core.write(args.output / 'execution-summary.json', summary)
    print(json.dumps(summary), flush=True)
    if args.stop_requested:
        raise SystemExit(130)
    if summary['attempted'] != len(entries) or any(
            r['status'] in {'infrastructure_error', 'input_budget_exceeded'} for r in records):
        raise SystemExit(2)


def check_run(run_dir, allow_empty=False):
    integrity_path = run_dir / 'trace-integrity.json'
    if integrity_path.is_file():
        for relative, expected in load(integrity_path).items():
            value = Path(relative)
            path = run_dir / value
            if (value.is_absolute() or '..' in value.parts or path.is_symlink() or
                    not path.resolve().is_relative_to(run_dir.resolve()) or
                    not path.is_file() or core.file_sha(path) != expected):
                raise ValueError('Exported trace integrity mismatch: ' + relative)
    config = load(run_dir / 'run_config.json')
    if config.get('schema') == recovery.SCHEMA:
        recovery.validate_metadata(run_dir)
    path = core.run_manifest_path(run_dir)
    manifest = load(path)
    if config.get('bundle_inventory_sha256') != core.file_sha(ROOT / 'SHA256SUMS.json'):
        raise ValueError('Run was made with a different frozen bundle')
    if config.get('schema') == recovery.SCHEMA and config['runner_files'] != recovery.code_binding():
        raise ValueError('Run was made with different runner code')
    args = context_args(config)
    if core.context_binding(args) != config['context_binding']:
        raise ValueError('Run context encoder changed')
    seen, missing = [], []
    for entry in manifest['episodes']:
        path = core.trajectory_path(run_dir, entry)
        if not path.is_file():
            missing.append(entry['case'])
            continue
        record = load(path)
        if record['input_hashes'] != entry['sha256'] or record['case'] != entry['case']:
            raise ValueError('Run input identity or SHA mismatch')
        core.RUNTIME_CACHE.clear()
        sys.modules.pop('calculators', None)
        images.validate_inputs([entry])

        def verify_request(row, observation, error, history, prompt):
            attachments = images.attachments(entry, observation, history)
            if [ref for ref, _ in attachments] != row['response'].get('image_inputs', []):
                raise ValueError('Run revealed-image binding mismatch')
            if core.digest(request_body(args, prompt, attachments)) != row['response']['request_body_sha256']:
                raise ValueError('Run request body replay mismatch')
        restore(entry, record, args, verify_turn=verify_request)
        seen.append(entry['case'])
    report = {'status': 'pass', 'trajectories_replayed': len(seen), 'missing_cases': missing,
              'semantic_scoring': False, 'cases': seen}
    if not seen and not allow_empty:
        raise ValueError('Run contains no trajectories')
    return report


def export_run(args):
    report = check_run(args.run)
    if args.output.exists():
        raise ValueError('Export already exists')
    if args.output.suffix != '.zip':
        raise ValueError('Export must use .zip')
    paths = [args.run / 'run_config.json', args.run / 'frozen-manifest.json']
    if (args.run / 'run-binding.json').is_file():
        paths.append(args.run / 'run-binding.json')
    if (args.run / 'execution-summary.json').exists():
        paths.append(args.run / 'execution-summary.json')
    paths.extend(sorted((args.run / 'trajectories').rglob('*.json')))
    if (args.run / 'resume-log.json').is_file():
        paths.append(args.run / 'resume-log.json')
    paths.extend(sorted((args.run / 'resume-backups').rglob('*.json')))
    bindings = {}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            if path.is_symlink() or not path.resolve().is_relative_to(args.run.resolve()):
                raise ValueError('Export path escapes run')
            relative = str(path.relative_to(args.run))
            bindings[relative] = core.file_sha(path)
            archive.write(path, relative)
        archive.writestr('trace-integrity.json', json.dumps(bindings, indent=2))
        archive.writestr('replay-verification.json', json.dumps(report, indent=2))
    print(json.dumps({'export': str(args.output), 'files': len(paths), **report}))


def owner_reference(entry, world, replay):
    """Use the source-bound named reference, including counterfactual.json aliases."""
    ref = load(ROOT / 'data/reference-index.json')[entry['case']]
    path = ROOT / 'data' / ref['path']
    if core.file_sha(path) != ref['sha256']:
        raise ValueError('Reference SHA mismatch')
    record = load(path)
    simulation = record.get('simulation', record)
    replay(world, simulation)
    return {'path': str(path), 'sha256': ref['sha256'], 'calls': len(simulation['history']),
            'selection': 'source-bound reference index; not a shortest-path claim',
            'input_hashes': entry['sha256'], 'runtime_files': entry['runtime_files']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ['list', 'verify', 'run']:
        p = commands.add_parser(name)
        p.add_argument('--paired', action='store_true', default=None if name == 'run' else False,
                       help='Select the 430 A/B configurations')
        p.add_argument('--case', action='append')
        p.add_argument('--limit', type=int)
        if name == 'run':
            p.add_argument('--url')
            p.add_argument('--model')
            p.add_argument('--protocol', choices=['openai', 'gemini'])
            p.add_argument('--api-key-env')
            p.add_argument('--no-auth', action='store_true', default=None)
            p.add_argument('--output', type=Path, required=True)
            p.add_argument('--resume', action='store_true', help='Replay and continue this same frozen v2 run')
            p.add_argument('--max-tokens', type=int)
            p.add_argument('--max-requests', type=int)
            p.add_argument('--max-prompt-chars', type=int)
            p.add_argument('--temperature', type=float)
            p.add_argument('--top-p', type=float)
            p.add_argument('--seed', type=int)
            p.add_argument('--timeout', type=int)
    p = commands.add_parser('check-run')
    p.add_argument('--run', type=Path, required=True)
    p = commands.add_parser('export')
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p = commands.add_parser('evaluate', help='Owner only: prepare review packets or aggregate supplied judgments')
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--partial', action='store_true')
    args = parser.parse_args()
    args.context_policy = 'revealed_delta'
    args.protocol_feedback_version = 'observed-state-v2'
    if args.command == 'list':
        _, _, entries = select(args)
        for entry in entries:
            print(entry['case'] + '\t' + entry['family'] + '\t' + entry['runtime_class'] + '\t' + entry.get('title', ''))
    elif args.command == 'verify':
        verify(args)
    elif args.command == 'run':
        run(args)
    elif args.command == 'check-run':
        check_integrity(load(core.run_manifest_path(args.run))['episodes'])
        print(json.dumps(check_run(args.run), ensure_ascii=False))
    elif args.command == 'export':
        check_integrity(load(core.run_manifest_path(args.run))['episodes'])
        export_run(args)
    elif args.command == 'evaluate':
        check_integrity(load(core.run_manifest_path(args.run))['episodes'])
        check_run(args.run)
        cmd = [str(ROOT / 'eval/aggregate_current_local_v2.py'),
               '--run', str(args.run.resolve()), '--output', str(args.output.resolve())]
        if args.prepare:
            cmd.append('--prepare')
        if args.partial:
            cmd.append('--partial')
        import aggregate_current_local_v2 as scoring
        scoring.reference = owner_reference
        sys.argv = cmd
        scoring.main()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, FileNotFoundError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        raise SystemExit(2)
