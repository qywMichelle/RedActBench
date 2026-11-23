"""Run disjoint future frozen shards in parallel; existing workers keep running."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import fcntl
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time

import accelerated_bridge
import run_background
import resume_with_image_budget as images

ROOT = Path(__file__).resolve().parent
STOP = threading.Event()


def tree_rss(roots):
    entries = {}
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():
            continue
        try:
            values = {}
            for line in (directory / 'status').read_text().splitlines():
                if line.startswith(('PPid:', 'VmRSS:')):
                    key, value = line.split(':', 1)
                    values[key] = int(value.split()[0])
            entries[int(directory.name)] = (values['PPid'], values.get('VmRSS', 0) * 1024)
        except (OSError, KeyError, ValueError):
            continue
    chosen = set(roots)
    while True:
        added = {pid for pid, (parent, _) in entries.items() if parent in chosen} - chosen
        if not added:
            break
        chosen.update(added)
    return sum(entries.get(pid, (0, 0))[1] for pid in chosen)


class Manager:
    def __init__(self, directory, legacy_pid, port, workers=2, rss_budget=1400 * 1024 * 1024):
        self.directory, self.legacy_pid, self.port = directory, legacy_pid, port
        self.workers, self.rss_budget = workers, rss_budget
        self.lock = threading.Lock()
        self.children = set()
        self.state = {'status': 'running', 'started_at': time.time(), 'workers_per_model': workers,
            'legacy_supervisor_pid': legacy_pid, 'rss_admission_budget_bytes': rss_budget,
            'workers': {}, 'completed': [], 'errors': []}
        self.jobs = {}

    def save(self):
        with self.lock:
            self.state['updated_at'] = time.time()
            self.state['aggregate_rss_bytes'] = tree_rss({self.legacy_pid, os.getpid()})
            run_background.atomic(self.directory / 'acceleration-status.json', self.state)

    def prepare(self):
        binding = json.loads((self.directory / 'transport-binding.json').read_text())
        previous_control = self.directory / 'acceleration-control.json'
        previously_owned = set(json.loads(previous_control.read_text())['owned_runs']) if previous_control.exists() else set()
        for model in binding['models']:
            current = json.loads((self.directory / model / 'status.json').read_text())['current_shard']
            jobs = binding['jobs']
            current_index = next(i for i, job in enumerate(jobs) if job['name'] == current)
            # Reserve only untouched jobs well ahead of each existing worker.
            self.jobs[model] = []
            for index in reversed(range(current_index + 1, len(jobs))):
                job = jobs[index]
                run = self.directory / model / 'runs' / job['name']
                if (str(run) in previously_owned or (index >= current_index + 3 and not run.exists())):
                    archive = self.directory / model / 'exports' / (job['name'] + '.zip')
                    if not images.exported_run_unchanged(run, archive, job['cases']):
                        self.jobs[model].append(job)
        owned = [self.directory / model / 'runs' / job['name']
            for model, jobs in self.jobs.items() for job in jobs]
        config = {'enabled': True,
            'redirect_legacy': False,
            'legacy_endpoint': f'http://127.0.0.1:{binding["port"]}/v1/chat/completions',
            'accelerated_endpoint': f'http://127.0.0.1:{self.port}/v1/chat/completions',
            'owned_runs': [str(p) for p in owned],
            'owned_exports': {str(p): str(p.parent.parent / 'exports' / (p.name + '.zip')) for p in owned}}
        run_background.atomic(self.directory / 'acceleration-control.json', config)
        source_names = ['run_accelerated.py', 'accelerated_bridge.py', 'throughput_overlay.py',
            'native_tile_cache.py', 'redact_performance_startup.py', 'performance_overlay.py',
            'resume_with_image_budget.py']
        sources = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_names}
        for name, sha in sources.items():
            target = self.directory / 'transport-revisions' / ('source-' + sha + '.py')
            if not target.exists():
                target.write_bytes((ROOT / name).read_bytes())
        binding_path = self.directory / 'acceleration-binding.json'
        if binding_path.exists():
            previous = binding_path.read_bytes()
            sha = hashlib.sha256(previous).hexdigest()
            (self.directory / 'transport-revisions' / ('acceleration-binding-' + sha + '.json')).write_bytes(previous)
        run_background.atomic(binding_path, {
            'transport_revision': accelerated_bridge.REVISION,
            'activated_at': datetime.now(timezone.utc).isoformat(), 'source_sha256': sources,
            'jobs': self.jobs, 'model_routes': {'claude-opus-5-5-science': 'claude-opus-5-5-hc',
                'gpt-6.1-sol-science': 'gpt-6.1-sol-science'},
            'initial_intervals': {'gpt-6.1-sol-science': 12., 'claude-opus-5-5-science': 1.5},
            'minimum_intervals': {'gpt-6.1-sol-science': 2., 'claude-opus-5-5-science': .5},
            'sampling_changed': False, 'model_visible_request_changed': False,
            'frozen_bundle_changed': False, 'max_output_tokens': 16384,
            'additional_workers_per_model': self.workers, 'per_process_address_space_limit': 536870912,
            'rss_admission_budget_bytes': self.rss_budget, 'tile_cache_limit_bytes': 16777216,
            'bridge_upload_memory_budget_bytes': 67108864, 'thread_stack_bytes': 1048576,
            'legacy_workers_stopped_or_restarted': False})
        # Enable routing only after the bridge is listening and config exists.
        path = ROOT / 'performance-overlay-config.json'
        startup = json.loads(path.read_text())
        startup['extra'] = {'source': str(ROOT / 'throughput_overlay.py'),
            'sha256': sources['throughput_overlay.py'],
            'config': str(self.directory / 'acceleration-control.json')}
        run_background.atomic(path, startup)
        self.save()

    def execute(self, command, log):
        # Keep credentials inherited in environment; never put them into argv.
        with log.open('a') as stream:
            child = subprocess.Popen(['prlimit', '--as=536870912', '--core=0', '--'] + command,
                cwd=ROOT / 'github_test_bundle', env=os.environ,
                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
            with self.lock:
                self.children.add(child)
            try:
                while child.poll() is None:
                    if STOP.wait(1):
                        child.terminate()
                        try:
                            child.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            child.kill()
                        break
                return child.wait()
            finally:
                with self.lock:
                    self.children.discard(child)

    def worker(self, model, index, jobs):
        worker_id = model + '/' + str(index)
        python = str(ROOT / 'github_test_bundle/.venv/bin/python')
        entrypoint = str(ROOT / 'github_test_bundle/redact_bench.py')
        while not STOP.is_set():
            try:
                job = jobs.get_nowait()
            except queue.Empty:
                break
            run = self.directory / model / 'runs' / job['name']
            log = self.directory / model / 'logs' / (job['name'] + '-accelerated.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            while tree_rss({self.legacy_pid, os.getpid()}) + 96 * 1024 * 1024 > self.rss_budget:
                with self.lock:
                    self.state['workers'][worker_id] = {'job': job['name'], 'status': 'memory_wait'}
                self.save()
                if STOP.wait(5):
                    return
            attempt = 0
            while not STOP.is_set():
                command = [python, entrypoint, 'run', '--output', str(run)]
                if (run / 'run_config.json').exists():
                    command += ['--resume']
                else:
                    command += ['--protocol', 'openai', '--url', f'http://127.0.0.1:{self.port}/v1',
                        '--model', model, '--max-tokens', '16384', '--max-requests', '200',
                        '--max-prompt-chars', '200000', '--timeout', '300']
                    if job['paired']:
                        command += ['--paired']
                    for case in job['cases']:
                        command += ['--case', case]
                with self.lock:
                    self.state['workers'][worker_id] = {'job': job['name'], 'status': 'running',
                        'attempt': attempt, 'pid_started_at': time.time()}
                self.save()
                code = self.execute(command, log)
                if code == 0 or STOP.is_set():
                    break
                # Retry the original prefix; do not change case budgets or drop errors.
                texts = []
                for path in (run / 'trajectories').rglob('*.json'):
                    record = json.loads(path.read_text())
                    if record['status'] == 'infrastructure_error':
                        texts.append(record.get('error', ''))
                retryable = any(any(term in text for term in
                    ['HTTP 429', 'HTTP 500', 'HTTP 502', 'HTTP 503', 'HTTP 504',
                     'timed out', 'URLError', 'invalid_grant', 'ConnectionResetError']) for text in texts)
                if not retryable:
                    break
                with self.lock:
                    self.state['workers'][worker_id].update(status='recovery_wait', exit_code=code)
                self.save()
                if STOP.wait(min(900, 30 * 2 ** min(attempt, 5))):
                    return
                attempt += 1
            if STOP.is_set():
                return
            if code:
                with self.lock:
                    self.state['errors'].append({'model': model, 'job': job['name'], 'exit_code': code})
                self.save()
                # The legacy worker can still restore this preserved original prefix.
                continue
            check = self.execute([python, entrypoint, 'check-run', '--run', str(run)], log)
            archive = self.directory / model / 'exports' / (job['name'] + '.zip')
            exported = check
            if not check and not archive.exists():
                exported = self.execute([python, entrypoint, 'export', '--run', str(run),
                    '--output', str(archive)], log)
            with self.lock:
                if not exported:
                    self.state['completed'].append({'model': model, 'job': job['name']})
                else:
                    self.state['errors'].append({'model': model, 'job': job['name'],
                        'verification_exit_code': exported})
            self.save()
        with self.lock:
            self.state['workers'][worker_id] = {'status': 'finished'}
        self.save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--legacy-pid', type=int, required=True)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--workers-per-model', type=int, default=2)
    args = parser.parse_args()
    directory = args.directory.resolve()
    lifetime_lock = (directory / '.acceleration.lock').open('a+')
    fcntl.flock(lifetime_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    key = os.environ['REDACT_API_KEY']
    manager = Manager(directory, args.legacy_pid, args.port, args.workers_per_model)
    server = accelerated_bridge.Server(('127.0.0.1', args.port), key,
        directory / 'upstream-requests-accelerated.jsonl')
    manager.port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: STOP.set())
    manager.prepare()
    def monitor():
        while not STOP.wait(10):
            manager.save()
    threading.Thread(target=monitor, daemon=True).start()
    observer = threading.Thread(target=server.observe_legacy_limits,
        args=(directory / 'upstream-requests.jsonl', STOP), daemon=True)
    observer.start()
    with ThreadPoolExecutor(max_workers=len(manager.jobs) * args.workers_per_model) as pool:
        futures = []
        for model, jobs in manager.jobs.items():
            pending = queue.Queue()
            for job in jobs:
                pending.put(job)
            for index in range(args.workers_per_model):
                futures.append(pool.submit(manager.worker, model, index, pending))
        for future in futures:
            future.result()
    with manager.lock:
        manager.state['status'] = 'auxiliary_batches_finished_bridge_active'
    manager.save()
    while not STOP.wait(15):
        manager.save()
        states = [json.loads((directory / model / 'status.json').read_text())['status'] for model in manager.jobs]
        if all(status == 'behavior_complete' for status in states):
            break
    server.shutdown()
    server.server_close()
    control_path = directory / 'acceleration-control.json'
    control = json.loads(control_path.read_text())
    control['enabled'] = False
    run_background.atomic(control_path, control)
    with manager.lock:
        manager.state['status'] = 'stopped' if STOP.is_set() else 'complete'
    manager.save()


if __name__ == '__main__':
    main()
