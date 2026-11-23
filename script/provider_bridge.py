"""Translate the frozen bench HTTP transport without changing its prompts or data."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request

UPSTREAM = 'https://mp.z01.normandyfunc.com/v1'
MODELS = {'claude-opus-5-5-science': 'messages',
          'gpt-6.1-sol-science': 'responses'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def translate(body):
    model = body['model']
    protocol = MODELS[model]
    messages = []
    for message in body['messages']:
        parts = []
        content = message['content']
        if isinstance(content, str):
            content = [{'type': 'text', 'text': content}]
        for part in content:
            if part['type'] == 'text':
                parts.append({'type': 'text' if protocol == 'messages' else 'input_text',
                              'text': part['text']})
            elif part['type'] == 'image_url':
                url = part['image_url']['url']
                if protocol == 'responses':
                    parts.append({'type': 'input_image', 'image_url': url})
                else:
                    prefix, encoded = url.split(',', 1)
                    if prefix != 'data:image/png;base64':
                        raise ValueError('Expected PNG data URL')
                    parts.append({'type': 'image', 'source': {'type': 'base64',
                                  'media_type': 'image/png', 'data': encoded}})
            else:
                raise ValueError('Unsupported content part')
        messages.append({'role': message['role'], 'content': parts})
    if protocol == 'messages':
        upstream = {'model': model, 'messages': messages, 'max_tokens': body['max_tokens'],
                    'temperature': 1.0}
    else:
        upstream = {'model': model, 'input': messages,
                    'max_output_tokens': body['max_tokens'], 'store': False}
    return protocol, upstream


def normalize(raw, protocol):
    usage = raw.get('usage') or {}
    if protocol == 'messages':
        text = ''.join(p.get('text', '') for p in raw.get('content', []) if p.get('type') == 'text')
        finish = raw.get('stop_reason')
        # Claude cache tokens are additional to its uncached input count.
        prompt_tokens = sum(usage.get(k, 0) or 0 for k in
                           ['input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'])
    else:
        text = ''.join(p.get('text', '') for item in raw.get('output', [])
                       if item.get('type') == 'message'
                       for p in item.get('content', []) if p.get('type') == 'output_text')
        finish = raw.get('status')
        prompt_tokens = usage.get('input_tokens', 0)
    if not text:
        raise ValueError('Provider returned no visible action text; status=' + str(finish))
    completion = usage.get('output_tokens', 0)
    return {'id': raw.get('id'), 'model': raw.get('model'), 'object': 'chat.completion',
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': text},
                         'finish_reason': finish}],
            'usage': {'prompt_tokens': prompt_tokens, 'completion_tokens': completion,
                      'total_tokens': prompt_tokens + completion}}


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, key, ledger, upstream=UPSTREAM):
        super().__init__(address, Handler)
        self.key, self.ledger, self.upstream = key, Path(ledger), upstream
        self.guard = threading.Lock()

    def record(self, row):
        value = json.dumps(row, ensure_ascii=False).replace(self.key, '[REDACTED]')
        with self.guard, self.ledger.open('a') as stream:
            stream.write(value + '\n')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, status, body):
        data = json.dumps(body, ensure_ascii=False).replace(self.server.key, '[REDACTED]').encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if self.path != '/v1/chat/completions':
            self.respond(404, {'error': 'Unknown endpoint'})
            return
        if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + self.server.key):
            self.respond(401, {'error': 'Invalid local authorization'})
            return
        row = {'started_at': time.time()}
        started = time.monotonic()
        try:
            length = int(self.headers['Content-Length'])
            if not 0 < length <= 16 * 1024 * 1024:
                raise ValueError('Request exceeds bridge byte budget')
            body = json.loads(self.rfile.read(length))
            protocol, upstream = translate(body)
            row.update(model=body['model'], protocol=protocol,
                       local_request_sha256=digest(body), upstream_request_sha256=digest(upstream),
                       max_output_tokens=body['max_tokens'])
            headers = {'Authorization': 'Bearer ' + self.server.key, 'Content-Type': 'application/json'}
            if protocol == 'messages':
                headers.update({'x-api-key': self.server.key, 'anthropic-version': '2023-06-01'})
            req = urllib.request.Request(self.server.upstream + '/' + protocol,
                                         json.dumps(upstream).encode(), headers)
            with urllib.request.urlopen(req, timeout=240) as response:
                raw = json.load(response)
            converted = normalize(raw, protocol)
            row.update(status=200, upstream_id=raw.get('id'), reported_model=raw.get('model'),
                       upstream_usage=raw.get('usage'), finish_reason=converted['choices'][0]['finish_reason'],
                       response_sha256=digest(converted))
            self.respond(200, converted)
        except urllib.error.HTTPError as exc:
            detail = exc.read(2000).decode(errors='replace').replace(self.server.key, '[REDACTED]')
            row.update(status=exc.code, error=detail)
            self.respond(exc.code, {'error': detail})
        except (ValueError, KeyError, TypeError) as exc:
            row.update(status=400, error=str(exc))
            self.respond(400, {'error': str(exc)})
        except Exception as exc:
            row.update(status=502, error=str(exc))
            self.respond(502, {'error': str(exc)})
        finally:
            row['latency_seconds'] = round(time.monotonic() - started, 3)
            self.server.record(row)
