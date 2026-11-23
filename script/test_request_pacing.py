import unittest

from request_pacing import RequestPacer
from resume_with_rate_control import retryable_error
import resume_with_rate_control as controller


class FakeClock:
    def __init__(self):self.now = 0.0
    def clock(self):return self.now
    def wait(self, seconds):self.now += seconds;return False


class PacingTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.pacer = RequestPacer(intervals={'gpt-6.1-sol-science': 12.0,
            'claude-opus-5-5-science': 2.0}, clock=self.clock.clock, wait=self.clock.wait)

    def test_model_intervals_are_independent(self):
        self.assertEqual(self.pacer.acquire('gpt-6.1-sol-science'), 0)
        self.assertEqual(self.pacer.acquire('claude-opus-5-5-science'), 0)
        self.assertEqual(self.pacer.acquire('gpt-6.1-sol-science'), 12)

    def test_rate_limit_backoff_is_bounded_and_decays_slowly(self):
        model = 'gpt-6.1-sol-science'
        self.pacer.acquire(model)
        self.pacer.notice(model, 429)
        self.assertEqual(self.pacer.acquire(model), 24)
        self.pacer.notice(model, 429)
        self.assertEqual(self.pacer.acquire(model), 45)
        for _ in range(20):self.pacer.notice(model, 200)
        self.assertAlmostEqual(self.pacer.states[model]['interval'], 38.25)

    def test_stop_interrupts_wait(self):
        pacer = RequestPacer(clock=lambda: 0, wait=lambda _: True)
        pacer.acquire('gpt-6.1-sol-science')
        with self.assertRaises(InterruptedError):pacer.acquire('gpt-6.1-sol-science')

    def test_production_interval_preserves_the_full_output_budget(self):
        pacer = RequestPacer(clock=self.clock.clock, wait=self.clock.wait)
        pacer.acquire('gpt-6.1-sol-science')
        self.assertEqual(pacer.acquire('gpt-6.1-sol-science'), 20)
        for _ in range(20):pacer.notice('gpt-6.1-sol-science', 200)
        self.assertAlmostEqual(pacer.states['gpt-6.1-sol-science']['interval'], 17)

    def test_only_provider_outages_are_eligible_for_recovery(self):
        self.assertTrue(retryable_error('HTTP 400: upstream invalid_grant'))
        self.assertTrue(retryable_error('HTTP 429: rate limit'))
        self.assertFalse(retryable_error('HTTP 400: unsupported field'))
        self.assertFalse(retryable_error('HTTP 401: invalid API key'))

    def test_pacing_keeps_the_native_prompt_and_output_limit(self):
        original = controller.PACER
        controller.PACER = RequestPacer(clock=self.clock.clock, wait=self.clock.wait)
        body = {'model': 'gpt-6.1-sol-science', 'max_tokens': 16384,
                'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': 'Visible fixture text.'}]}]}
        try:
            protocol, emitted = controller.translate(body)
            self.assertEqual(protocol, 'responses')
            self.assertEqual(emitted['max_output_tokens'], 16384)
            self.assertEqual(emitted['input'][0]['content'][0]['text'], 'Visible fixture text.')
            controller.translate(body)
            self.assertEqual(controller.images.LOCAL.pacing_wait, 20)
        finally:
            controller.PACER = original


if __name__ == '__main__':unittest.main()
