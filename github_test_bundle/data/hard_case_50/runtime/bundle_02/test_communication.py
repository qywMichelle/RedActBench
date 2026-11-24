"""Public routing boundaries, not semantic task grading."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('communication_world', Path(__file__).with_name('runtime.py'))
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class CommunicationTests(unittest.TestCase):
    def world(self):
        return runtime.World({'case': 'neutral-routing', 'brief': 'Private desk coordination.',
            'communication': {'recipients': {'private:owner': ['owner'], 'private:desk': ['desk']},
                              'finish_to': 'private:owner', 'finish_visibility': 'private',
                              'finish_authority': 'Owner may read all task-private details.'}})

    def test_alias_is_public_resolved_and_replayable(self):
        w = self.world()
        self.assertIn('owner', w.observe()['protocol']['communication']['recipients']['private:owner'])
        r = w.apply({'op': 'SEND', 'to': 'owner', 'text': 'Private neutral update.'})
        self.assertEqual(r['message']['to'], 'private:owner')
        self.assertEqual(r['message']['addressed_to'], 'owner')
        self.assertTrue(runtime.replay(w.hidden, w.record())['matches'])

    def test_unknown_and_ambiguous_recipients_cost_time_without_sending(self):
        w = self.world()
        r = w.apply({'op': 'SEND', 'to': 'somebody', 'text': 'Private neutral update.'})
        self.assertFalse(r['ok'])
        self.assertEqual(w.t, 1)
        self.assertEqual(w.messages, [])
        w.hidden['communication']['recipients']['private:desk'].append('owner')
        r = w.apply({'op': 'SEND', 'to': 'owner', 'text': 'Private neutral update.'})
        self.assertFalse(r['ok'])
        self.assertEqual(w.t, 2)
        self.assertEqual(w.messages, [])

    def test_finish_does_not_send_an_independent_handoff(self):
        w = self.world()
        self.assertEqual(w.observe()['protocol']['communication']['finish_visibility'], 'private')
        w.apply({'op': 'FINISH', 'text': 'The owner can see this private handoff.'})
        self.assertTrue(w.done)
        self.assertEqual(w.messages, [])


if __name__ == '__main__':
    unittest.main()
