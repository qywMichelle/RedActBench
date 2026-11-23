"""Bounded, per-model request pacing; no model input or sampling changes."""
import threading
import time


class RequestPacer:
    def __init__(self, intervals=None, clock=time.monotonic, wait=None):
        self.production_defaults = intervals is None
        self.intervals = intervals or {'gpt-6.1-sol-science': 12.0,
                                       'claude-opus-5-5-science': 2.0}
        self.clock, self.wait = clock, wait or (lambda seconds: time.sleep(seconds))
        self.lock = threading.Lock()
        self.states = {}

    def state(self, model):
        initial = 20.0 if self.production_defaults and model == 'gpt-6.1-sol-science' else self.intervals.get(model, 2.0)
        return self.states.setdefault(model, {'interval': initial,
               'next_slot': 0.0, 'cooldown': 0.0, 'successes': 0})

    def acquire(self, model):
        start = self.clock()
        with self.lock:
            state = self.state(model)
            slot = max(start, state['next_slot'], state['cooldown'])
            state['next_slot'] = slot + state['interval']
        while True:
            with self.lock:
                ready = max(slot, self.state(model)['cooldown'])
            remaining = ready - self.clock()
            if remaining <= 0:
                return self.clock() - start
            if self.wait(min(remaining, 1.0)):
                raise InterruptedError('Background stop requested')

    def notice(self, model, status):
        with self.lock:
            state = self.state(model)
            if status == 429:
                state['successes'] = 0
                state['interval'] = min(45.0, max(12.0, state['interval'] * 2))
                state['cooldown'] = max(state['cooldown'], self.clock() + state['interval'])
                state['next_slot'] = max(state['next_slot'], state['cooldown'])
            elif status == 200:
                state['successes'] += 1
                if state['successes'] >= 20:
                    state['interval'] = max(self.intervals.get(model, 2.0), state['interval'] * .85)
                    state['successes'] = 0
