"""Check Responses and Messages capabilities with an in-memory credential."""
import getpass
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

key = os.environ.get('REDACT_API_KEY') or getpass.getpass('API key (hidden): ')
tests = [('claude-opus-5-5-science', 'responses'),
         ('gpt-6.1-sol-science', 'responses'),
         ('claude-opus-5-5-science', 'messages')]
results = []
for model, protocol in tests:
    text = 'Reply with exactly this JSON: {"ready":true}'
    headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
    if protocol == 'responses':
        body = {'model': model, 'input': [{'role': 'user', 'content': [
            {'type': 'input_text', 'text': text}]}], 'max_output_tokens': 16384,
            'temperature': 1.0, 'top_p': 0.95, 'store': False}
    else:
        headers.update({'x-api-key': key, 'anthropic-version': '2023-06-01'})
        body = {'model': model, 'messages': [{'role': 'user', 'content': text}],
                'max_tokens': 16384, 'temperature': 1.0}
    req = urllib.request.Request('https://mp.z01.normandyfunc.com/v1/' + protocol,
        data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = json.load(response)
        result = {'model': model, 'protocol': protocol, 'status': 'pass', 'response': raw}
    except urllib.error.HTTPError as exc:
        result = {'model': model, 'protocol': protocol, 'http_status': exc.code,
                  'error': exc.read(2000).decode(errors='replace').replace(key, '[REDACTED]')}
    except Exception as exc:
        result = {'model': model, 'protocol': protocol, 'error': str(exc).replace(key, '[REDACTED]')}
    results.append(result)
    print(json.dumps(result, ensure_ascii=False).replace(key, '[REDACTED]'), flush=True)
    Path('github_test_bundle/output/api-preflight/responses-probe.json').write_text(
        json.dumps(results, ensure_ascii=False, indent=2).replace(key, '[REDACTED]') + '\n')
