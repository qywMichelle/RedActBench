"""Action parser extracted from the source runner."""
import json

def parse(text):
    decoder = json.JSONDecoder()
    try:
        value = json.loads(text)
        if isinstance(value, dict) and isinstance(value.get('action'), str):
            return value
    except json.JSONDecodeError:
        pass
    for pos, char in enumerate(text):
        if char == '{':
            try:
                value, _ = decoder.raw_decode(text[pos:])
                if isinstance(value, dict) and isinstance(value.get('action'), str):
                    return value
            except json.JSONDecodeError:
                continue
    raise ValueError('No JSON action object')
