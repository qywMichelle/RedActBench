"""Read completed HTTP records and measure short-window throughput and resources."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
DIRECTORY = ROOT / 'github_test_bundle/output/ab-eval-20261119'
PERFORMANCE = ROOT / 'github_test_bundle/output/performance'
now = time.time()
state = json.loads((DIRECTORY / 'acceleration-status.json').read_text())
control = json.loads((DIRECTORY / 'acceleration-control.json').read_text())
start = state['started_at']
seconds = now - start
groups = defaultdict(Counter)
for label, name in [('legacy', 'upstream-requests.jsonl'), ('accelerated', 'upstream-requests-accelerated.jsonl')]:
    for line in (DIRECTORY / name).open():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        finished = row.get('started_at', 0) + row.get('latency_seconds', 0)
        if finished >= start and finished <= now:
            groups[row.get('model')][label + '_' + str(row.get('status'))] += 1
baseline = json.loads((PERFORMANCE / 'eta-request-rate.json').read_text())
models = {}
for model, counts in groups.items():
    total = counts['legacy_200'] + counts['accelerated_200']
    per_hour = total * 3600 / seconds
    models[model] = {'successful_requests': total, 'counts': dict(counts),
        'observed_requests_per_hour': round(per_hour, 1),
        'previous_hour_requests_per_hour': baseline[model]['requests_per_hour'],
        'observed_throughput_ratio': round(per_hour / baseline[model]['requests_per_hour'], 2)}
with urllib.request.urlopen(control['accelerated_endpoint'].split('/v1/')[0] + '/health', timeout=5) as response:
    health = json.load(response)
report = {'generated_at': now, 'sample_seconds': round(seconds, 1), 'models': models,
    'aggregate_rss_mib': round(state['aggregate_rss_bytes'] / 1024**2, 1),
    'bridge': health, 'qualification': 'Short observation of different configurations, not a controlled end-to-end speed benchmark.'}
(PERFORMANCE / 'acceleration-live-measurement.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
