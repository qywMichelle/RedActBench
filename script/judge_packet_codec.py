"""Lossless JSON-pointer deduplication for repeated observations in judge packets."""
import hashlib
import json

TAG = '__redact_judge_reference__'
FORMAT = 'lossless-json-pointer-v1'


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def pointer(value, path):
    if path == '': return value
    if not isinstance(path, str) or not path.startswith('/'):
        raise ValueError('Evidence path must be an RFC6901 JSON pointer')
    for part in path[1:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def encode(packet, minimum=192):
    seen = {}
    def walk(value, path):
        if isinstance(value, dict):
            if TAG in value: raise ValueError('Reserved reference tag in packet')
            result = {}; children = []; size = 2
            for key, child in value.items():
                encoded, digest, length = walk(child, path + '/' + key.replace('~','~0').replace('/','~1'))
                result[key] = encoded; children.append([key, digest]); size += len(compact(key)) + length + 2
            digest = hashlib.sha256(('dict:' + compact(children)).encode()).hexdigest()
        elif isinstance(value, list):
            result = []; children = []; size = 2
            for index, child in enumerate(value):
                encoded, digest, length = walk(child, path + '/' + str(index))
                result.append(encoded); children.append(digest); size += length + 1
            digest = hashlib.sha256(('list:' + compact(children)).encode()).hexdigest()
        else:
            result = value; text = compact(value); size = len(text)
            digest = hashlib.sha256((type(value).__name__ + ':' + text).encode()).hexdigest()
        if size >= minimum:
            if digest in seen: result = {TAG: seen[digest]}
            else: seen[digest] = path
        return result, digest, size
    encoded, _, _ = walk(packet, '')
    result = {'format': FORMAT, 'packet': encoded}
    if compact(decode(result)) != compact(packet):
        raise ValueError('Lossless packet roundtrip failed')
    return result


def decode(encoded):
    if encoded.get('format') != FORMAT: raise ValueError('Unknown packet codec')
    root = encoded['packet']; memo = {}; active = set()
    def expand(value):
        if isinstance(value, dict) and set(value) == {TAG}:
            path = value[TAG]
            if path in active: raise ValueError('Cyclic reference')
            if path not in memo:
                active.add(path); memo[path] = expand(pointer(root, path)); active.remove(path)
            return memo[path]
        if isinstance(value, dict): return {key:expand(child) for key,child in value.items()}
        if isinstance(value, list): return [expand(child) for child in value]
        return value
    return expand(root)
