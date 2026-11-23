"""Equivalent native requests with bounded uploads and adaptive shared pacing."""
from collections import Counter, defaultdict, deque
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import threading
import time

import native_tile_cache
import provider_bridge
import resume_with_image_budget as images

REVISION = 'full-canvas-image-patches-v7-concurrent-equivalent-adaptive-pacing'
# Bounded concurrent HTTP requests must not reserve 8 MiB of stack each.
threading.stack_size(1024 * 1024)


class AdaptivePacer:
    def __init__(self, clock=time.monotonic, wait=None, initial=None, floors=None):
        self.clock, self.wait = clock, wait or time.sleep
        self.initial = initial or {'gpt-6.1-sol-science': 12., 'claude-opus-5-5-science': 1.5}
        self.floors = floors or {'gpt-6.1-sol-science': 2., 'claude-opus-5-5-science': .5}
        self.lock = threading.Lock()
        self.states = {}
        self.queues = defaultdict(deque)

    def state(self, model):
        return self.states.setdefault(model, {'interval': self.initial[model],
            'next_slot': 0., 'cooldown': 0., 'successes': 0, 'limited': 0})

    def acquire(self, model):
        started = self.clock()
        ticket = object()
        with self.lock:
            self.queues[model].append(ticket)
        try:
            while True:
                with self.lock:
                    now = self.clock()
                    state = self.state(model)
                    ready = max(state['next_slot'], state['cooldown'])
                    if self.queues[model][0] is ticket and ready <= now:
                        self.queues[model].popleft()
                        state['next_slot'] = now + state['interval']
                        return now - started
                self.wait(max(.01, min(ready - now, .5)))
        finally:
            with self.lock:
                if ticket in self.queues[model]:
                    self.queues[model].remove(ticket)

    def notice(self, model, status, legacy=False):
        with self.lock:
            state = self.state(model)
            if status == 429:
                state['limited'] += 1
                state['successes'] = 0
                state['interval'] = min(60., max(6. if model.startswith('gpt') else 2., state['interval'] * 2))
                # Let already-running legacy workers retain priority during an
                # account-wide limit. Future requests reserve slots only when ready.
                cooldown = max(60., state['interval']) if legacy else state['interval']
                state['cooldown'] = max(state['cooldown'], self.clock() + cooldown)
            elif status == 200 and not legacy:
                state['successes'] += 1
                if state['successes'] >= 20:
                    state['interval'] = max(self.floors[model], state['interval'] * .85)
                    state['successes'] = 0

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.states))


class UploadBudget:
    def __init__(self, maximum=64 * 1024 * 1024):
        self.maximum, self.used = maximum, 0
        self.condition = threading.Condition()

    @contextmanager
    def reserve(self, length):
        charge = min(self.maximum, max(128 * 1024, length * 6))
        with self.condition:
            self.condition.wait_for(lambda: self.used + charge <= self.maximum)
            self.used += charge
        try:
            yield
        finally:
            with self.condition:
                self.used -= charge
                self.condition.notify_all()


class Handler(provider_bridge.Handler):
    def do_GET(self):
        if self.path == '/health':
            self.respond(200, {'status': 'ready', 'revision': REVISION,
                'pacing': self.server.pacer.snapshot(), 'statuses': dict(self.server.statuses)})
        else:
            self.respond(404, {'error': 'Unknown endpoint'})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self.respond(400, {'error': 'Invalid Content-Length'})
            return
        with self.server.upload_budget.reserve(max(0, length)):
            super().do_POST()


class Server(provider_bridge.Server):
    def __init__(self, address, key, ledger, upstream=provider_bridge.UPSTREAM, pacer=None):
        super().__init__(address, key, ledger, upstream)
        self.RequestHandlerClass = Handler
        self.pacer = pacer or AdaptivePacer()
        self.upload_budget = UploadBudget()
        self.statuses = Counter()
        self.cpu_lock = threading.Lock()
        self.tile_cache = native_tile_cache.install(images)
        images.REVISION = REVISION
        provider_bridge.translate = self.translate

    def translate(self, body):
        images.LOCAL.pacing_wait = self.pacer.acquire(body['model'])
        started = time.monotonic()
        with self.cpu_lock:
            protocol, native = images.translate(body)
        images.LOCAL.translation_seconds = time.monotonic() - started
        return protocol, native

    def record(self, row):
        row.update(transport_revision=REVISION,
            rate_wait_seconds=round(getattr(images.LOCAL, 'pacing_wait', 0), 3),
            translation_seconds=round(getattr(images.LOCAL, 'translation_seconds', 0), 3),
            image_resizes=getattr(images.LOCAL, 'resizes', []),
            image_tiles=getattr(images.LOCAL, 'tiles', []),
            routed_model=getattr(images.LOCAL, 'routed_model', row.get('model')),
            model=row.get('model') or getattr(images.LOCAL, 'model', None))
        row['latency_excluding_rate_wait_seconds'] = round(max(0., row['latency_seconds'] - row['rate_wait_seconds']), 3)
        model = row.get('model')
        if model:
            self.pacer.notice(model, row.get('status'))
        with self.guard:
            self.statuses[str(row.get('status'))] += 1
        super().record(row)

    def observe_legacy_limits(self, ledger, stop):
        # Existing supervisor retains its own ledger and loaded implementation.
        # Only a new legacy 429 reduces auxiliary traffic; no legacy state changes.
        path = Path(ledger)
        with path.open() as stream:
            stream.seek(0, 2)
            while not stop.wait(1):
                position = stream.tell()
                line = stream.readline()
                if not line:
                    continue
                if not line.endswith('\n'):
                    stream.seek(position)
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get('status') == 429 and row.get('model') in self.pacer.initial:
                    self.pacer.notice(row['model'], 429, legacy=True)
