"""Revealed-image projection from the source multimodal adapter."""
import functools
import hashlib
import json
from pathlib import Path
import run_current_english_gemini as core
from data_paths import data_roots, resolve_data_path
IMAGE_BINDINGS = {}

@functools.lru_cache(maxsize=128)
def image_bytes(path, expected):
    path = Path(path)
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Image changed after input verification')
    if path.suffix.lower() == '.svg':
        import cairosvg
        # Render vector evidence, preserving its full canvas and contents.
        data = cairosvg.svg2png(bytestring=data, scale=2)
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Invalid PNG evidence')
    return data


def image_references(observation):
    found = {}

    def walk(value):
        if isinstance(value, dict):
            if value.get("image_path"):
                found[value["image_path"]] = {
                    "resource_id": value.get("id"),
                    "path": value["image_path"],
                    "sha256": value.get("image_sha256"),
                }
            for key, child in value.items():
                if key not in {"asset_catalog", "tool_protocol"}:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    # These are candidate-visible observations, never world/controller records.
    walk(observation)
    return found


def attachments(entry, observation, interactions):
    refs = {}
    for row in interactions:
        refs.update(image_references(row["observation"]))
    refs.update(image_references(observation))
    result = []
    for relative, reference in sorted(refs.items()):
        paths = image_relative_paths(entry, relative)
        expected = reference['sha256'] or next(
            (IMAGE_BINDINGS[str(core.ROOT / 'data' / p)] for p in paths
             if str(core.ROOT / 'data' / p) in IMAGE_BINDINGS), None)
        if not expected:
            raise ValueError('Image has no verified content binding: ' + relative)
        path = resolve_image_path(paths, expected)
        data = image_bytes(str(path), expected)
        result.append(({**reference, "sha256": expected,
            "transmitted_png_sha256": hashlib.sha256(data).hexdigest(),
            "conversion": 'svg-to-png-scale2' if path.suffix.lower()=='.svg' else 'original-png'}, data))
    return result


def image_relative_paths(entry, relative):
    """Keep image references package-local; never infer refs from hidden state."""
    relative = Path(relative)
    if (relative.is_absolute() or '..' in relative.parts or not relative.parts
            or relative.parts[0] != 'assets' or relative.suffix.lower() not in {'.png', '.svg'}):
        raise ValueError('Image reference must be a package-local PNG/SVG')
    packages = [Path(entry['files']['visible']).parent.parent]
    if entry.get('runtime_root'):
        packages.append(Path(entry['runtime_root']).parent)
    if entry.get('package_manifest'):
        packages.append(Path(entry['package_manifest']).parent)
    return list(dict.fromkeys(package / relative for package in packages))


def resolve_image_path(relatives, expected):
    for relative in relatives:
        try:
            path = resolve_data_path(relative, expected, core.ROOT)
        except FileNotFoundError:
            continue
        for base in data_roots(core.ROOT):
            if (base / relative).resolve() == path:
                assets = base.joinpath(*relative.parts[:relative.parts.index('assets') + 1]).resolve()
                if not path.is_relative_to(assets):
                    raise ValueError('Image path outside package assets')
                return path
    raise ValueError('No current/archive image matches its bound SHA256')


def validate_inputs(entries):
    checked = set()
    projections = []
    for entry in entries:
        for key, relative in entry["files"].items():
            path = core.input_path(entry, key)
            if core.file_sha(path) != entry["sha256"][key]:
                raise ValueError(f"Input hash mismatch: {entry['case']}/{key}")
        cls, replay = core.runtime(entry)
        checked.update(entry['runtime_files'].items())
        hidden_path = core.input_path(entry, 'hidden')
        world = json.loads(hidden_path.read_text())
        visible_path = core.input_path(entry, 'visible')
        source_base = next(base for base in data_roots(core.ROOT) if hidden_path.is_relative_to(base))
        for ref in image_references(world).values():
            relatives = image_relative_paths(entry, ref['path'])
            if ref['sha256']:
                expected = ref['sha256']
                path = resolve_image_path(relatives, expected)
            else:
                # Older worlds bind images in the preflight report rather than
                # image_sha256. Follow the bound world snapshot: an unchanged
                # visible export may still resolve to current after its images change.
                path = next((source_base / relative for relative in relatives
                             if (source_base / relative).is_file()), None)
                if path is None:
                    raise FileNotFoundError('Image unavailable in bound source snapshot: ' + ref['path'])
                expected = core.file_sha(path)
            logical = next(relative for relative in relatives
                           if any((base / relative).resolve() == path.resolve() for base in data_roots(core.ROOT)))
            IMAGE_BINDINGS[str(core.ROOT / 'data' / logical)] = expected
            image_bytes(str(path), expected)
        visible = json.loads(visible_path.read_text())
        initial = cls(world).observe()
        # The first two legacy packages serialize an auxiliary initial-resource
        # export / omit done=false. Their frozen runtime remains authoritative.
        projected = dict(visible)
        if entry['case'].startswith('batch_001_en/'):
            projected.pop('initial_resources', None)
        if entry['case'].startswith('batch_002_en/'):
            projected.setdefault('done', False)
        if initial != projected:
            raise ValueError(f"Initial projection mismatch: {entry['case']}")
        projections.append({"case": entry["case"], "initial_projection_matches": True,
            "initial_images": len(attachments(entry, initial, []))})
    return {"episodes": len(entries), "runtime_files_checked": len(checked),
        'image_sources': dict(IMAGE_BINDINGS),
        "initial_projections": projections, "status": "pass"}

