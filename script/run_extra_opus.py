"""Use released GPT capacity for untouched Opus shards, with original locks."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import signal
import threading
import time

import run_accelerated as scheduling
import run_background

ROOT = Path(__file__).resolve().parent
DIRECTORY = ROOT / 'github_test_bundle/output/ab-eval-20261119'


class ExtraManager(scheduling.Manager):
    def save(self):
        with self.lock:
            self.state['updated_at'] = time.time()
            self.state['aggregate_rss_bytes'] = scheduling.tree_rss({self.legacy_pid, os.getpid()})
            run_background.atomic(self.directory / 'extra-opus-status.json', self.state)


def main():
    lifetime_lock = (DIRECTORY / '.extra-opus.lock').open('a+')
    fcntl.flock(lifetime_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    controller_pid = 423132
    legacy_pid = 400158
    original_rss = scheduling.tree_rss
    scheduling.tree_rss = lambda roots: original_rss(set(roots) | {controller_pid})
    control = json.loads((DIRECTORY / 'acceleration-control.json').read_text())
    port = int(control['accelerated_endpoint'].split(':')[2].split('/')[0])
    manager = ExtraManager(DIRECTORY, legacy_pid, port, workers=2)
    binding = json.loads((DIRECTORY / 'transport-binding.json').read_text())
    model = 'claude-opus-5-5-science'
    jobs = [job for job in reversed(binding['jobs'])
        if job['name'] in {'paired-020', 'paired-021'} and
        str(DIRECTORY / model / 'runs' / job['name']) in control['owned_runs'] and
        not (DIRECTORY / model / 'runs' / job['name']).exists()]
    # The shared frozen CLI and previously-installed locks serialize any natural
    # original worker arriving later. No source, case or budget changes here.
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (DIRECTORY / 'transport-revisions' / ('source-' + source_sha + '.py')).write_bytes(Path(__file__).read_bytes())
    run_background.atomic(DIRECTORY / 'extra-opus-binding.json', {
        'activated_at': datetime.now(timezone.utc).isoformat(), 'source_sha256': source_sha,
        'jobs': jobs, 'additional_workers': len(jobs), 'existing_bridge_reused': True,
        'legacy_workers_stopped': False, 'max_output_tokens': 16384,
        'per_process_address_space_limit_bytes': 536870912,
        'rss_admission_budget_bytes': manager.rss_budget})
    manager.save()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: scheduling.STOP.set())
    def monitor():
        while not scheduling.STOP.wait(10): manager.save()
    threading.Thread(target=monitor, daemon=True).start()
    pending = queue.Queue()
    for job in jobs: pending.put(job)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(manager.worker, model, index, pending) for index in range(min(2, len(jobs)))]
        for future in futures: future.result()
    with manager.lock:
        manager.state['status'] = 'stopped' if scheduling.STOP.is_set() else 'complete'
    manager.save()


if __name__ == '__main__': main()
