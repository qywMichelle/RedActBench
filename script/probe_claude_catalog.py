"""Discover Claude-labelled proxy IDs and test their supported text interface."""
from concurrent.futures import ThreadPoolExecutor
import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

BASE = 'https://mp.z01.normandyfunc.com/v1'
parser = argparse.ArgumentParser()
parser.add_argument('--model', action='append')
args = parser.parse_args()
key = os.environ.get('REDACT_API_KEY') or getpass.getpass('API key (hidden): ')
headers = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}
req = urllib.request.Request(BASE + '/models', headers=headers)
with urllib.request.urlopen(req, timeout=20) as response:
    catalog = json.load(response)
models = [m['id'] for m in catalog.get('data', []) if m['id'].startswith('claude-')]
if args.model:
    models = [model for model in models if model in args.model]
print(json.dumps({'claude_model_ids': models}), flush=True)


def probe(model):
    attempts = []
    for protocol in ['messages', 'chat/completions', 'responses']:
        prompt = 'Reply with exactly this JSON and nothing else: {"ready":true}'
        request_headers = dict(headers)
        if protocol == 'messages':
            body = {'model': model, 'max_tokens': 128,
                    'messages': [{'role': 'user', 'content': prompt}]}
            request_headers.update({'x-api-key': key, 'anthropic-version': '2023-06-01'})
        elif protocol == 'chat/completions':
            body = {'model': model, 'max_tokens': 128,
                    'messages': [{'role': 'user', 'content': prompt}]}
        else:
            body = {'model': model, 'max_output_tokens': 128, 'input': prompt, 'store': False}
        request = urllib.request.Request(BASE + '/' + protocol,
                                        json.dumps(body).encode(), request_headers)
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                raw = json.load(response)
            if protocol == 'messages':
                text = ''.join(p.get('text', '') for p in raw.get('content', []) if p.get('type') == 'text')
            elif protocol == 'chat/completions':
                text = raw.get('choices', [{}])[0].get('message', {}).get('content', '')
            else:
                text = ''.join(p.get('text', '') for i in raw.get('output', [])
                               if i.get('type') == 'message' for p in i.get('content', [])
                               if p.get('type') == 'output_text')
            return {'model': model, 'status': 'available' if text else 'responded_without_text',
                    'protocol': protocol, 'reported_model': raw.get('model'),
                    'text': (text or '')[:200], 'usage': raw.get('usage'), 'attempts': attempts}
        except urllib.error.HTTPError as exc:
            detail = exc.read(1200).decode(errors='replace').replace(key, '[REDACTED]')
            attempts.append({'protocol': protocol, 'http_status': exc.code, 'error': detail})
            if 'does not support' not in detail:
                break
        except Exception as exc:
            attempts.append({'protocol': protocol, 'error': str(exc).replace(key, '[REDACTED]')})
            break
    return {'model': model, 'status': 'unavailable_at_probe', 'attempts': attempts}


results = []
with ThreadPoolExecutor(max_workers=2) as pool:
    for result in pool.map(probe, models):
        results.append(result)
        print(json.dumps(result, ensure_ascii=False).replace(key, '[REDACTED]'), flush=True)
report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'base_url': BASE, 'models': results}
Path('github_test_bundle/output/api-preflight/' + ('claude-selected-probe.json' if args.model else 'claude-catalog-probe.json')).write_text(
    json.dumps(report, ensure_ascii=False, indent=2).replace(key, '[REDACTED]') + '\n')
