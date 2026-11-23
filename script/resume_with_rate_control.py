"""Disclosed pacing and provider-outage recovery over the unchanged frozen runner."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import provider_bridge
import run_background
import resume_with_image_budget as images
from request_pacing import RequestPacer

REVISION = 'full-canvas-image-patches-v6-equivalent-tile-cache-adaptive-pacing'
PACER = RequestPacer(wait=run_background.STOP.wait)
MAX_PROVIDER_RECOVERY_SECONDS = 72 * 3600


def translate(body):
    images.LOCAL.pacing_wait = PACER.acquire(body['model'])
    return images.translate(body)


def record(server, row):
    model = row.get('model') or getattr(images.LOCAL, 'model', None)
    row['rate_wait_seconds'] = round(getattr(images.LOCAL, 'pacing_wait', 0), 3)
    row['latency_excluding_rate_wait_seconds'] = round(max(0, row['latency_seconds'] - row['rate_wait_seconds']), 3)
    if model:
        PACER.notice(model, row.get('status'))
    images.record(server, row)


def retryable_error(error):
    return any(marker in error for marker in [
        'HTTP 429', 'HTTP 500', 'HTTP 502', 'HTTP 503', 'HTTP 504',
        'invalid_grant', 'timed out', 'URLError', 'ConnectionResetError'])


def worker(model, directory, jobs, port, env):
    state_path = directory / model / 'status.json'
    started = time.monotonic()
    attempt = 0
    while not run_background.STOP.is_set():
        finished, remaining = [], []
        for job in jobs:
            run = directory / model / 'runs' / job['name']
            archive = directory / model / 'exports' / (job['name'] + '.zip')
            if images.exported_run_unchanged(run, archive, job['cases']):
                finished.append(job['name'])
            else:
                remaining.append(job)
        images.ORIGINAL_WORKER(model, directory, remaining, port, env)
        state = json.loads(state_path.read_text())
        state['planned_configurations'] = sum(len(job['cases']) for job in jobs)
        state['completed_shards'] = list(dict.fromkeys(finished + state['completed_shards']))
        state['transport_revision'], state['recovery_attempt'] = REVISION, attempt
        if run_background.STOP.is_set():
            state['status'] = 'stopped'
        run_background.atomic(state_path, state)
        if state['status'] != 'needs_attention':
            return
        retryable = False
        for path in (Path(state['current_run']) / 'trajectories').rglob('*.json'):
            trace = json.loads(path.read_text())
            if trace['status'] == 'infrastructure_error':
                retryable = retryable_error(trace.get('error', ''))
        if not retryable or time.monotonic() - started >= MAX_PROVIDER_RECOVERY_SECONDS:
            return
        delay = min(900, 300 * (2 ** min(attempt, 2)))
        state.update(status='recovery_wait', recovery_delay_seconds=delay,
                     updated_at=time.time(), retry_not_before=time.time() + delay)
        run_background.atomic(state_path, state)
        if run_background.STOP.wait(delay):
            state['status'] = 'stopped'
            run_background.atomic(state_path, state)
            return
        attempt += 1


def main():
    directory = Path(sys.argv[sys.argv.index('--directory') + 1]).resolve()
    root = Path(__file__).resolve().parent
    route = os.environ.get('REDACT_OPUS_ROUTE', 'claude-opus-5-5-hc')
    if route not in {'claude-opus-5-5-hc', 'claude-opus-5-5-science', 'claude-opus-5-5:mindracode-azure'}:
        raise ValueError('Unapproved Opus 5.5 route')
    images.MODEL_ROUTES['claude-opus-5-5-science'] = route
    images.REVISION = REVISION
    baseline = json.loads((directory / 'transport-binding.json').read_text())
    for name, expected in baseline['adapter_files'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Original adapter changed: ' + name)
    # This main is entered only on a normal future launch; the running v5
    # supervisor keeps its loaded code and both current model workers.
    import native_tile_cache
    tile_cache = native_tile_cache.install(images)
    history = directory / 'transport-revisions'
    history.mkdir(exist_ok=True)
    sources = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in
               ['request_pacing.py', 'resume_with_rate_control.py', 'resume_with_image_budget.py',
                'native_tile_cache.py']}
    for name, sha in sources.items():
        target = history / ('source-' + sha + '.py')
        if not target.exists():
            target.write_bytes((root / name).read_bytes())
    revision = {'revision': REVISION, 'activated_at': datetime.now(timezone.utc).isoformat(),
                'source_sha256': sources, 'requested_to_provider_model_routes': images.MODEL_ROUTES,
                'minimum_request_interval_seconds': PACER.intervals,
                'initial_gpt_request_interval_seconds': 20,
                'rate_limit_backoff_max_seconds': 45, 'backoff_decay_after_successes': 20,
                'provider_recovery_policy': 'Wait 5/10/15 minutes and retry original checkpoints for up to 72 hours on transient HTTP errors or upstream invalid_grant.',
                'latency_note': 'Rate wait is included in client round-trip latency and separately recorded in upstream ledger.',
                'sampling_changes': False, 'inherits_native_image_policy': 'full canvas, 29900 patches, 128-row LANCZOS strips',
                'maximum_base64_image_bytes': images.MAX_ENCODED_IMAGE_BYTES,
                'maximum_message_image_side': images.MAX_MESSAGE_IMAGE_SIDE,
                'equivalent_tile_cache_bytes_limit': tile_cache.max_bytes,
                'equivalent_tile_cache_policy': 'Bounded reuse of byte-identical PNG/base64 tiles and coordinates; no change to visible inputs or provider request bodies.',
                'long_message_image_policy': 'Lossless contiguous tiles with 16-pixel overlap; full canvas preserved and source/tile SHA recorded.',
                'frozen_runner_and_case_files_changed': False, 'prior_trajectories_resampled': False}
    path = history / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-paced-recovery.json')
    path.write_text(json.dumps(revision, indent=2) + '\n')
    provider_bridge.translate, provider_bridge.Server.record = translate, record
    run_background.worker = worker
    run_background.main()


if __name__ == '__main__':
    main()
