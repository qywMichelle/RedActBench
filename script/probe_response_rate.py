"""Check current GPT availability and non-sensitive rate-limit headers."""
import getpass
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

key = os.environ.get('REDACT_API_KEY') or getpass.getpass('API key (hidden): ')
results = []
for limit in [128, 16384]:
    body = {'model': 'gpt-6.1-sol-science', 'input': 'Reply with exactly {"ready":true}.',
            'max_output_tokens': limit, 'store': False}
    request = urllib.request.Request('https://mp.z01.normandyfunc.com/v1/responses',
        json.dumps(body).encode(), {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = json.load(response)
            headers = dict(response.headers)
        result = {'max_output_tokens': limit, 'status': 200, 'reported_model': raw.get('model'),
                  'usage': raw.get('usage')}
    except urllib.error.HTTPError as exc:
        headers = dict(exc.headers)
        result = {'max_output_tokens': limit, 'status': exc.code,
                  'error': exc.read(1200).decode(errors='replace').replace(key, '[REDACTED]')}
    except Exception as exc:
        headers = {}
        result = {'max_output_tokens': limit, 'error': str(exc).replace(key, '[REDACTED]')}
    result['rate_headers'] = {k: v for k, v in headers.items()
                             if any(term in k.lower() for term in ['ratelimit', 'retry-after'])}
    results.append(result)
    print(json.dumps(result).replace(key, '[REDACTED]'), flush=True)
Path('github_test_bundle/output/api-preflight/response-rate-probe.json').write_text(
    json.dumps(results, indent=2).replace(key, '[REDACTED]') + '\n')
