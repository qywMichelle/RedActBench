"""Read provider model IDs without saving credentials."""
import getpass
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

key = os.environ.get('REDACT_API_KEY') or getpass.getpass('API key (hidden): ')
hosts = ['https://models-proxy.stepfun-inc.com', 'https://mp.z01.normandyfunc.com']
results = []
for host in hosts:
    req = urllib.request.Request(host + '/v1/models', headers={'Authorization': 'Bearer ' + key})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = json.load(response)
        ids = [item['id'] for item in raw.get('data', [])]
        result = {'host': host, 'model_ids': ids}
    except urllib.error.HTTPError as exc:
        result = {'host': host, 'http_status': exc.code,
                  'error': exc.read(1200).decode(errors='replace').replace(key, '[REDACTED]')}
    except Exception as exc:
        result = {'host': host, 'error': str(exc).replace(key, '[REDACTED]')}
    results.append(result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
Path('github_test_bundle/output/api-preflight/model-discovery.json').write_text(
    json.dumps(results, ensure_ascii=False, indent=2).replace(key, '[REDACTED]') + '\n')
