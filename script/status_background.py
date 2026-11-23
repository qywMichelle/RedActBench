"""Read on-disk trajectories one at a time; report execution progress, not scores."""
import argparse
from collections import Counter
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--directory', type=Path, required=True)
args = parser.parse_args()
directory = args.directory.resolve()
binding = json.loads((directory / 'transport-binding.json').read_text())
rows = []
for model in binding['models']:
    statuses = Counter()
    reported_models = Counter()
    calls = errors = prompt_tokens = completion_tokens = 0
    run_root = directory / model / 'runs'
    # Resume snapshots contain older copies of the same trajectories.
    # Count only each run's current trajectories directory.
    paths = (path for run in run_root.iterdir() if run.is_dir()
             for path in (run / 'trajectories').rglob('*.json')) if run_root.exists() else []
    for path in paths:
        record = json.loads(path.read_text())
        statuses[record['status']] += 1
        calls += len(record['calls'])
        errors += record['protocol_error_count'] if 'protocol_error_count' in record else sum(
            'protocol_error' in row for row in record['calls'])
        for row in record['calls']:
            if row['response'].get('reported_model'):
                reported_models[row['response']['reported_model']] += 1
            usage = row['response'].get('usage') or {}
            prompt_tokens += usage.get('prompt_tokens', 0)
            completion_tokens += usage.get('completion_tokens', 0)
    state_path = directory / model / 'status.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    rows.append({'model': model, 'worker_status': state.get('status'),
                 'planned_configurations': sum(len(j['cases']) for j in binding['jobs']),
                 'recorded_configurations': sum(statuses.values()),
                 'terminated_configurations': sum(statuses[s] for s in
                    ['complete', 'request_limit', 'action_budget_exhausted', 'input_budget_exceeded']),
                 'statuses': dict(statuses), 'requests': calls, 'protocol_errors': errors,
                 'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens,
                 'current_shard': state.get('current_shard')})
    rows[-1]['reported_model_requests'] = dict(reported_models)
print(json.dumps({'directory': str(directory), 'models': rows,
                  'acceleration': json.loads((directory / 'acceleration-status.json').read_text())
                    if (directory / 'acceleration-status.json').is_file() else None,
                  'sonnet_5_5': 'unavailable: provider reports model offline',
                  'semantic_scoring': False}, ensure_ascii=False, indent=2))
