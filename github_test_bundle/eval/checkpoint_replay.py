"""Rebuild a checkpoint using only its frozen inputs and recorded dispatches."""
from argparse import Namespace
import hashlib
import json

import run_current_english_gemini as core

TERMINAL = {'complete', 'request_limit', 'action_budget_exhausted', 'input_budget_exceeded'}
RECOVERABLE = {'running', 'infrastructure_error', 'user_stopped'}


def context_args(config):
    context = config['context_binding']
    return Namespace(context_policy=context['name'],
                     max_prompt_chars=context['max_prompt_characters'],
                     protocol_feedback_version=context.get('protocol_feedback_version', 'legacy-v1'),
                     protocol=config['protocol'], model=config['model'],
                     temperature=config['temperature'], max_tokens=config['max_tokens'],
                     top_p=config['top_p'], seed=config['seed'])


def restore(entry, record, args, verify_turn=None):
    """Return the exact environment, visible history and last error; no network."""
    if record['case'] != entry['case'] or record['input_hashes'] != entry['sha256']:
        raise ValueError('Checkpoint input identity or SHA mismatch')
    if record['status'] not in TERMINAL | RECOVERABLE:
        raise ValueError('Unknown checkpoint status: ' + record['status'])
    binding = core.context_binding(args)
    core.validate_checkpoint_context(record, binding)
    world = json.loads(core.input_path(entry, 'hidden').read_text())
    cls, replay = core.runtime(entry)
    env, interactions, error = cls(world), [], ''
    for index, row in enumerate(record['calls'], 1):
        observation = env.observe()
        if row['request_index'] != index or row['time_before'] != observation['time']:
            raise ValueError('Checkpoint request order/time mismatch')
        if core.digest(observation) != row['observation_sha256']:
            raise ValueError('Checkpoint observation replay mismatch')
        prompt = core.build_prompt(args, observation, error, interactions)
        if hashlib.sha256(prompt.encode()).hexdigest() != row['response']['request_prompt_sha256']:
            raise ValueError('Checkpoint prompt replay mismatch')
        if row['response']['context_binding'] != binding:
            raise ValueError('Checkpoint response context mismatch')
        if verify_turn is not None:
            verify_turn(row, observation, error, interactions, prompt)
        error = ''
        try:
            action = core.parse(row['response']['text'])
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            if 'action' in row or 'result' in row:
                raise ValueError('Checkpoint format error has a recorded dispatch')
            error = f'{type(exc).__name__}: {exc}'
        else:
            if action != row.get('action'):
                raise ValueError('Checkpoint action does not match response')
            try:
                result = env.apply(action)
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                if 'result' in row:
                    raise ValueError('Checkpoint records a result for a rejected dispatch') from exc
                error = f'{type(exc).__name__}: {exc}'
            else:
                if 'result' not in row or result != row['result']:
                    raise ValueError('Checkpoint tool result replay mismatch')
                if isinstance(result, dict) and 'error' in result:
                    error = str(result['error'])
        expected_error = error if 'result' in row else error[:500]
        if row.get('protocol_error', '') != expected_error:
            raise ValueError('Checkpoint protocol error replay mismatch')
        interactions.append(core.interaction(observation, row))
    if env.record() != record['simulation']:
        raise ValueError('Checkpoint final state replay mismatch')
    if record['status'] == 'complete' and not env.done:
        raise ValueError('Complete checkpoint has a live environment')
    replay(world, record['simulation'])
    return env, interactions, error
