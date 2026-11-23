"""Run small frozen shards with bounded memory, durable logs and trace exports."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from provider_bridge import MODELS, Server, UPSTREAM

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / 'github_test_bundle'
PYTHON = BUNDLE / '.venv/bin/python'
STOP = threading.Event()
CHILDREN = set()
GUARD = threading.Lock()
TERMINAL = {'complete', 'request_limit', 'action_budget_exhausted', 'input_budget_exceeded'}


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def plan(scope):
    main = json.loads((BUNDLE / 'data/current-english-manifest.json').read_text())['episodes']
    paired = json.loads((BUNDLE / 'data/current-counterfactual-manifest.json').read_text())['episodes']
    jobs = []
    for start in range(0, len(paired), 20):
        jobs.append({'name': f'paired-{start // 20:03d}', 'paired': True,
                     'cases': [e['case'] for e in paired[start:start + 20]]})
    if scope == 'all':
        paired_bases = {e['base_case'] for e in paired}
        remaining = [e['case'] for e in main if e['case'] not in paired_bases]
        for start in range(0, len(remaining), 20):
            jobs.append({'name': f'unpaired-{start // 20:03d}', 'paired': False,
                         'cases': remaining[start:start + 20]})
    return jobs


def execute(command, log, env):
    # prlimit applies before Python starts; no preexec_fn in this threaded parent.
    command = ['prlimit', '--as=536870912', '--core=0', '--'] + command
    with log.open('a') as stream:
        proc = subprocess.Popen(command, cwd=BUNDLE, env=env,
                                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
        with GUARD:
            CHILDREN.add(proc)
        try:
            while proc.poll() is None:
                if STOP.wait(1):
                    proc.terminate()
                    try:
                        proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    break
            return proc.wait()
        finally:
            with GUARD:
                CHILDREN.discard(proc)


def worker(model, directory, jobs, port, env):
    state_path = directory / model / 'status.json'
    state = {'model': model, 'planned_configurations': sum(len(j['cases']) for j in jobs),
             'completed_shards': [], 'status': 'running', 'started_at': time.time()}
    atomic(state_path, state)
    for job in jobs:
        if STOP.is_set():
            state['status'] = 'stopped'
            break
        run = directory / model / 'runs' / job['name']
        log = directory / model / 'logs' / (job['name'] + '.log')
        log.parent.mkdir(parents=True, exist_ok=True)
        state.update(current_shard=job['name'], current_run=str(run), updated_at=time.time())
        atomic(state_path, state)
        command = [str(PYTHON), str(BUNDLE / 'redact_bench.py'), 'run', '--output', str(run)]
        if (run / 'run_config.json').exists():
            command += ['--resume']
        else:
            command += ['--protocol', 'openai', '--url', f'http://127.0.0.1:{port}/v1',
                        '--model', model, '--max-tokens', '16384', '--max-requests', '200',
                        '--max-prompt-chars', '200000', '--timeout', '300']
            if job['paired']:
                command += ['--paired']
            for case in job['cases']:
                command += ['--case', case]
        code = execute(command, log, env)
        # Resume only transient infrastructure failures, with the original bindings.
        for retry in range(3):
            if not code or STOP.is_set():
                break
            retryable = False
            for trace in (run / 'trajectories').rglob('*.json'):
                record = json.loads(trace.read_text())
                if record['status'] == 'infrastructure_error':
                    error = record.get('error', '')
                    retryable = any(marker in error for marker in [
                        'HTTP 429', 'HTTP 500', 'HTTP 502', 'HTTP 503', 'HTTP 504',
                        'timed out', 'URLError', 'ConnectionResetError'])
            if not retryable:
                break
            state.update(retry=retry + 1, status='retry_wait', updated_at=time.time())
            atomic(state_path, state)
            if STOP.wait(30 * (retry + 1)):
                break
            state['status'] = 'running'
            atomic(state_path, state)
            code = execute([str(PYTHON), str(BUNDLE / 'redact_bench.py'), 'run',
                            '--resume', '--output', str(run)], log, env)
        state['last_exit_code'] = code
        if code:
            state['status'] = 'stopped' if STOP.is_set() else 'needs_attention'
            break
        check = [str(PYTHON), str(BUNDLE / 'redact_bench.py'), 'check-run', '--run', str(run)]
        if execute(check, log, env):
            state['status'] = 'check_failed'
            break
        archive = directory / model / 'exports' / (job['name'] + '.zip')
        if not archive.exists():
            export = [str(PYTHON), str(BUNDLE / 'redact_bench.py'), 'export',
                      '--run', str(run), '--output', str(archive)]
            if execute(export, log, env):
                state['status'] = 'export_failed'
                break
        state['completed_shards'].append(job['name'])
        atomic(state_path, state)
    else:
        state['status'] = 'behavior_complete'
    state['updated_at'] = time.time()
    atomic(state_path, state)
    print(json.dumps({'model': model, 'status': state['status'],
                      'completed_shards': len(state['completed_shards'])}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--scope', choices=['paired', 'all'], default='all')
    parser.add_argument('--port', type=int, default=18765)
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    key = os.environ['REDACT_API_KEY']
    jobs = plan(args.scope)
    binding = {'scope': args.scope, 'jobs': jobs, 'models': MODELS, 'upstream': UPSTREAM,
               'port': args.port, 'max_output_tokens': 16384,
               'simultaneous_model_workers': 2, 'per_child_address_space_bytes': 536870912,
               'systemd_memory_max_bytes': 1610612736,
               'provider_sampling': {'messages': {'temperature': 1.0},
                                     'responses': 'provider defaults; unsupported temperature/top_p/seed omitted'},
               'frozen_inventory_sha256': hashlib.sha256((BUNDLE / 'SHA256SUMS.json').read_bytes()).hexdigest(),
               'adapter_files': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                 for name in ['provider_bridge.py', 'run_background.py']}}
    binding_path = directory / 'transport-binding.json'
    if binding_path.exists():
        if json.loads(binding_path.read_text()) != binding:
            raise RuntimeError('Session code/config changed; use original files or a new session directory')
    else:
        atomic(binding_path, binding)
    server = Server(('127.0.0.1', args.port), key, directory / 'upstream-requests.jsonl')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def stop(*_):
        STOP.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    atomic(directory / 'supervisor.json', {'pid': os.getpid(), 'port': args.port,
           'status': 'running', 'scope': args.scope,
           'configurations_per_model': sum(len(j['cases']) for j in jobs),
           'models': list(MODELS), 'sonnet_status': 'provider reports model offline',
           'started_at': time.time()})
    env = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1')
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, model, directory, jobs, args.port, env) for model in MODELS]
            for future in futures:
                future.result()
    finally:
        server.shutdown()
        server.server_close()
    atomic(directory / 'supervisor.json', {'pid': os.getpid(), 'port': args.port,
           'status': 'stopped' if STOP.is_set() else 'workers_finished', 'scope': args.scope,
           'configurations_per_model': sum(len(j['cases']) for j in jobs), 'models': list(MODELS),
           'sonnet_status': 'provider reports model offline', 'updated_at': time.time()})


if __name__ == '__main__':
    main()
