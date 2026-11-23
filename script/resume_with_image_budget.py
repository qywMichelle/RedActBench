"""Versioned native-image adaptation; frozen bench prompts/configs remain unchanged."""
import base64
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import sys
import threading
import zipfile

from PIL import Image, __version__ as PIL_VERSION
import provider_bridge
import run_background

PATCH_SIZE = 32
MAX_PATCHES = 29900
MAX_ENCODED_IMAGE_BYTES = 9 * 1024 * 1024
MAX_MESSAGE_IMAGE_SIDE = 7900
REVISION = 'full-canvas-image-patches-v2-strip-resize-hc-route'
MODEL_ROUTES = {'claude-opus-5-5-science': 'claude-opus-5-5-hc'}
ORIGINAL_TRANSLATE = provider_bridge.translate
ORIGINAL_RECORD = provider_bridge.Server.record
ORIGINAL_WORKER = run_background.worker
LOCAL = threading.local()
IMAGE_LOCK = threading.Lock()
RESIZE_CACHE = OrderedDict()
CACHE_BYTES_LIMIT = 16 * 1024 * 1024


def patches(width, height):
    return math.ceil(width / PATCH_SIZE) * math.ceil(height / PATCH_SIZE)


def encoded_size(data):
    return 4 * ((len(data) + 2) // 3)


def resize_canvas_strips(source, size):
    """Keep full-canvas sampling alignment without a full RGBA premultiplication copy."""
    width, height = source.size
    target_width, target_height = size
    result = Image.new(source.mode, size)
    if source.mode == 'P':
        result.putpalette(source.getpalette())
    padding = math.ceil(3 * max(width / target_width, height / target_height)) + 2
    for top in range(0, target_height, 128):
        bottom = min(target_height, top + 128)
        source_top = top * height / target_height
        source_bottom = bottom * height / target_height
        crop_top = max(0, math.floor(source_top) - padding)
        crop_bottom = min(height, math.ceil(source_bottom) + padding)
        with source.crop((0, crop_top, width, crop_bottom)) as strip:
            with strip.resize((target_width, bottom - top), Image.Resampling.LANCZOS,
                              box=(0, source_top - crop_top, width, source_bottom - crop_top)) as resized:
                result.paste(resized, (0, top))
    return result


def _fit_png_uncached(data):
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Expected PNG image')
    width, height = struct.unpack('>II', data[16:24])
    if patches(width, height) <= MAX_PATCHES and encoded_size(data) <= MAX_ENCODED_IMAGE_BYTES:
        return data, None
    factor = min(1.0, math.sqrt(MAX_PATCHES / patches(width, height)))
    target_width = max(1, int(width * factor))
    target_height = max(1, int(height * factor))
    while patches(target_width, target_height) > MAX_PATCHES:
        factor *= .999
        target_width = max(1, int(width * factor))
        target_height = max(1, int(height * factor))
    for _ in range(12):
        with Image.open(io.BytesIO(data)) as original:
            resized_image = resize_canvas_strips(original, (target_width, target_height))
        # Release the decoded input before encoding; always resample the original.
        with resized_image:
            output = io.BytesIO()
            resized_image.save(output, format='PNG', optimize=True, compress_level=9)
            resized = output.getvalue()
            actual_width, actual_height = resized_image.size
        if encoded_size(resized) <= MAX_ENCODED_IMAGE_BYTES:
            break
        factor *= min(.97, math.sqrt(MAX_ENCODED_IMAGE_BYTES / encoded_size(resized)) * .97)
        target_width, target_height = max(1, int(width * factor)), max(1, int(height * factor))
    else:
        raise ValueError('Full-canvas image cannot fit the provider byte budget')
    binding = {'original_png_sha256': hashlib.sha256(data).hexdigest(),
               'transmitted_png_sha256': hashlib.sha256(resized).hexdigest(),
               'original_size': [width, height], 'transmitted_size': [actual_width, actual_height],
               'original_patches': patches(width, height),
               'transmitted_patches': patches(actual_width, actual_height),
               'original_base64_bytes': encoded_size(data),
               'transmitted_base64_bytes': encoded_size(resized),
               'conversion': 'full-canvas-proportional-lanczos', 'cropped': False}
    return resized, binding


def fit_png(data):
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Expected PNG image')
    width, height = struct.unpack('>II', data[16:24])
    if patches(width, height) <= MAX_PATCHES and encoded_size(data) <= MAX_ENCODED_IMAGE_BYTES:
        return data, None
    key = hashlib.sha256(data).hexdigest()
    # Two simultaneous RGBA decodes would exceed the supervisor's limit.
    with IMAGE_LOCK:
        if key in RESIZE_CACHE:
            value = RESIZE_CACHE.pop(key)
            RESIZE_CACHE[key] = value
            return value
        value = _fit_png_uncached(data)
        if len(value[0]) <= CACHE_BYTES_LIMIT:
            while RESIZE_CACHE and sum(len(v[0]) for v in RESIZE_CACHE.values()) + len(value[0]) > CACHE_BYTES_LIMIT:
                RESIZE_CACHE.popitem(last=False)
            RESIZE_CACHE[key] = value
        return value


def message_image_parts(data, content_index):
    width, height = struct.unpack('>II', data[16:24])
    if max(width, height) <= MAX_MESSAGE_IMAGE_SIDE:
        return [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                'data': base64.b64encode(data).decode()}}], None
    rectangles = []
    step = MAX_MESSAGE_IMAGE_SIDE - 16
    for top in range(0, height, step):
        for left in range(0, width, step):
            rectangles.append((left, top, min(width, left + MAX_MESSAGE_IMAGE_SIDE),
                               min(height, top + MAX_MESSAGE_IMAGE_SIDE)))
    parts, tiles = [], []
    with Image.open(io.BytesIO(data)) as source:
        for number, rectangle in enumerate(rectangles, 1):
            with source.crop(rectangle) as tile:
                output = io.BytesIO()
                tile.save(output, format='PNG', optimize=True, compress_level=9)
                tile_data = output.getvalue()
            encoded = base64.b64encode(tile_data).decode()
            if len(encoded) > MAX_ENCODED_IMAGE_BYTES:
                raise ValueError('Image tile exceeds encoded byte budget')
            parts.extend([{'type': 'text', 'text': (
                f'Continuous tile {number}/{len(rectangles)} of the same original revealed evidence image; '
                f'pixel rectangle {list(rectangle)} in full canvas {width}x{height}. '
                'All tiles together preserve the complete image, with overlapping boundaries.')},
                {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': encoded}}])
            tiles.append({'rectangle': list(rectangle), 'png_sha256': hashlib.sha256(tile_data).hexdigest(),
                          'base64_bytes': len(encoded)})
    return parts, {'content_index': content_index, 'source_png_sha256': hashlib.sha256(data).hexdigest(),
                   'full_canvas_size': [width, height], 'full_canvas_covered': True, 'tiles': tiles}


def translate(body):
    LOCAL.resizes = []
    LOCAL.tiles = []
    LOCAL.error_type = None
    LOCAL.model = body.get('model')
    protocol, upstream = ORIGINAL_TRANSLATE(body)
    upstream['model'] = MODEL_ROUTES.get(body['model'], body['model'])
    LOCAL.routed_model = upstream['model']
    for message in upstream['messages' if protocol == 'messages' else 'input']:
        replacement_parts = []
        for index, part in enumerate(message['content']):
            if protocol == 'responses' and part['type'] == 'input_image':
                url = part['image_url']
                prefix, encoded = url.split(',', 1)
                if prefix != 'data:image/png;base64':
                    raise ValueError('Expected PNG data URL')
            elif protocol == 'messages' and part['type'] == 'image':
                encoded = part['source']['data']
            else:
                replacement_parts.append(part)
                continue
            try:
                data, binding = fit_png(base64.b64decode(encoded, validate=True))
            except Exception as exc:
                LOCAL.error_type = type(exc).__name__
                raise
            if binding is not None:
                encoded = base64.b64encode(data).decode()
                if protocol == 'responses':
                    part['image_url'] = 'data:image/png;base64,' + encoded
                else:
                    part['source']['data'] = encoded
                LOCAL.resizes.append(dict(binding, content_index=index))
            if protocol == 'messages':
                pieces, tiled = message_image_parts(data, index)
                replacement_parts.extend(pieces)
                if tiled is not None:LOCAL.tiles.append(tiled)
            else:
                replacement_parts.append(part)
        message['content'] = replacement_parts
    return protocol, upstream


def record(server, row):
    row['transport_revision'] = REVISION
    row['image_resizes'] = getattr(LOCAL, 'resizes', [])
    row['image_tiles'] = getattr(LOCAL, 'tiles', [])
    row.setdefault('model', getattr(LOCAL, 'model', None))
    row['routed_model'] = getattr(LOCAL, 'routed_model', row.get('model'))
    if getattr(LOCAL, 'error_type', None):
        row['local_error_type'] = LOCAL.error_type
    ORIGINAL_RECORD(server, row)
    LOCAL.resizes = []


def exported_run_unchanged(run, archive, cases):
    if not archive.is_file():
        return False
    try:
        with zipfile.ZipFile(archive) as z:
            hashes = json.loads(z.read('trace-integrity.json'))
        for relative, expected in hashes.items():
            part = Path(relative)
            if part.is_absolute() or '..' in part.parts:
                return False
            path = run / part
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                return False
        config = json.loads((run / 'run_config.json').read_text())
        if config['cases'] != cases:
            return False
        for case in cases:
            path = run / 'trajectories' / (case + '.json')
            if json.loads(path.read_text())['status'] not in run_background.TERMINAL:
                return False
        return True
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return False


def worker(model, directory, jobs, port, env):
    state_path = directory / model / 'status.json'
    complete_names = []
    remaining = []
    for job in jobs:
        run = directory / model / 'runs' / job['name']
        archive = directory / model / 'exports' / (job['name'] + '.zip')
        if exported_run_unchanged(run, archive, job['cases']):
            complete_names.append(job['name'])
        else:
            remaining.append(job)
    for attempt in range(4):
        ORIGINAL_WORKER(model, directory, remaining, port, env)
        state = json.loads(state_path.read_text())
        state['planned_configurations'] = sum(len(job['cases']) for job in jobs)
        state['completed_shards'] = list(dict.fromkeys(complete_names + state['completed_shards']))
        state['transport_revision'] = REVISION
        state['recovery_attempt'] = attempt
        run_background.atomic(state_path, state)
        if state['status'] != 'needs_attention' or attempt == 3 or run_background.STOP.is_set():
            return
        retryable = False
        for path in (Path(state['current_run']) / 'trajectories').rglob('*.json'):
            record = json.loads(path.read_text())
            if record['status'] == 'infrastructure_error':
                retryable = any(marker in record.get('error', '') for marker in [
                    'HTTP 429', 'HTTP 500', 'HTTP 502', 'HTTP 503', 'HTTP 504',
                    'timed out', 'URLError', 'ConnectionResetError'])
        if not retryable:
            return
        state['status'] = 'recovery_wait'
        state['recovery_delay_seconds'] = 300 * (2 ** attempt)
        run_background.atomic(state_path, state)
        if run_background.STOP.wait(state['recovery_delay_seconds']):
            state['status'] = 'stopped'
            run_background.atomic(state_path, state)
            return


def main():
    # The baseline binding and files remain intact. The supplementary record
    # declares the new native-image preprocessing for reviewers.
    index = sys.argv.index('--directory')
    directory = Path(sys.argv[index + 1]).resolve()
    baseline = json.loads((directory / 'transport-binding.json').read_text())
    root = Path(__file__).resolve().parent
    for name, expected in baseline['adapter_files'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Original frozen adapter changed: ' + name)
    revision = {'revision': REVISION, 'activated_at': datetime.now(timezone.utc).isoformat(),
                'baseline_binding_sha256': hashlib.sha256((directory / 'transport-binding.json').read_bytes()).hexdigest(),
                'source_file': str(Path(__file__).resolve()),
                'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'pillow_version': PIL_VERSION, 'max_patches_per_image': MAX_PATCHES,
                'patch_size': PATCH_SIZE, 'applies_to_models': list(provider_bridge.MODELS),
                'full_canvas_preserved': True, 'frozen_runner_and_case_files_changed': False,
                'resampling': 'LANCZOS with 128-row output strips and filter padding; RGBA preserved',
                'image_processing_parallelism': 1, 'resize_cache_bytes_limit': CACHE_BYTES_LIMIT,
                'requested_to_provider_model_routes': MODEL_ROUTES,
                'route_change_reason': 'science consistently returns HTTP 500; hc successfully tested. Preserve earlier science results and disclose route mixture.',
                'recovery_policy': 'Verify completed export SHA before skipping; transient infrastructure failures may resume after 5/10/20 minutes, up to 3 additional recovery cycles.',
                'prior_trajectories_resampled': False,
                'scope': 'Native provider image payloads only; original bench request SHA and checkpoint bindings unchanged.',
                'limitation': 'Oversized images have lower pixel resolution after this revision; disclose in quality reports.'}
    history = directory / 'transport-revisions'
    history.mkdir(exist_ok=True)
    path = history / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-image-budget.json')
    path.write_text(json.dumps(revision, indent=2) + '\n')
    provider_bridge.translate = translate
    provider_bridge.Server.record = record
    run_background.worker = worker
    run_background.main()


if __name__ == '__main__':
    main()
