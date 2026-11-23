"""Check exact requested provider models against the unmodified bench request shape."""
import getpass
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

key = os.environ.get('REDACT_API_KEY') or getpass.getpass('API key (hidden): ')
models = ['claude-opus-5-5-science', 'claude-sonnet-5-5', 'gpt-6.1-sol-science']
results = []
for model in models:
    body = {'model': model, 'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'Reply with exactly this JSON: {"ready":true}'}]}],
        'max_tokens': 16384, 'temperature': 1.0, 'top_p': 0.95, 'seed': 0}
    req = urllib.request.Request('https://mp.z01.normandyfunc.com/v1/chat/completions',
        data=json.dumps(body).encode(), headers={'Authorization': 'Bearer ' + key,
                                                  'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = json.load(response)
        result = {'model': model, 'status': 'pass', 'reported_model': raw.get('model'),
            'text': raw.get('choices', [{}])[0].get('message', {}).get('content'),
            'usage': raw.get('usage'), 'finish_reason': raw.get('choices', [{}])[0].get('finish_reason')}
    except urllib.error.HTTPError as exc:
        result = {'model': model, 'http_status': exc.code,
                  'error': exc.read(2000).decode(errors='replace').replace(key, '[REDACTED]')}
    except Exception as exc:
        result = {'model': model, 'error': str(exc).replace(key, '[REDACTED]')}
    results.append(result)
    print(json.dumps(result, ensure_ascii=False).replace(key, '[REDACTED]'), flush=True)
    Path('github_test_bundle/output/api-preflight/generation-probe.json').write_text(
        json.dumps(results, ensure_ascii=False, indent=2).replace(key, '[REDACTED]') + '\n')
