"""Validate both native protocols and image inputs before starting the full run."""
import base64
import getpass
import io
import json
import os
from pathlib import Path
import threading
import urllib.error
import urllib.request

from PIL import Image
from provider_bridge import MODELS, Server

key = os.environ.get('REDACT_API_KEY') or getpass.getpass('API key (hidden): ')
buffer = io.BytesIO()
Image.new('RGB', (128, 128), (0, 0, 255)).save(buffer, format='PNG')
encoded = base64.b64encode(buffer.getvalue()).decode()
directory = Path('github_test_bundle/output/api-preflight')
server = Server(('127.0.0.1', 0), key, directory / 'live-bridge-ledger.jsonl')
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
results = []
try:
    for model in MODELS:
        body = {'model': model, 'max_tokens': 16384, 'temperature': 1.0, 'top_p': .95, 'seed': 0,
                'messages': [{'role': 'user', 'content': [
                    {'type': 'text', 'text': 'Reply with only a JSON object describing the color of this image.'},
                    {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + encoded}}]}]}
        req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/v1/chat/completions',
            json.dumps(body).encode(), {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                raw = json.load(response)
            result = {'model': model, 'status': 'pass', 'response': raw}
        except urllib.error.HTTPError as exc:
            result = {'model': model, 'status': 'failed', 'http_status': exc.code,
                      'error': exc.read(2000).decode(errors='replace').replace(key, '[REDACTED]')}
        except Exception as exc:
            result = {'model': model, 'status': 'failed', 'error': str(exc).replace(key, '[REDACTED]')}
        results.append(result)
        print(json.dumps(result, ensure_ascii=False).replace(key, '[REDACTED]'), flush=True)
        (directory / 'live-bridge-probe.json').write_text(
            json.dumps(results, ensure_ascii=False, indent=2).replace(key, '[REDACTED]') + '\n')
finally:
    server.shutdown()
    server.server_close()
    thread.join()
