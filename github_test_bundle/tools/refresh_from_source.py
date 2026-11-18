"""Export the current synthetic inputs and required runtime closure, without archives."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil

DEST = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    args = p.parse_args()
    source = args.source.resolve()
    if (DEST / 'release.json').exists():
        p.error('Export destination already frozen; use a fresh copy of this scaffold')
    copied = {}

    def copy(relative):
        if relative in copied:
            return
        path = source / relative
        target = DEST / relative
        if target.exists() and sha(path) != sha(target):
            raise ValueError('Existing destination differs: ' + relative)
        if relative not in copied:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            copied[relative] = sha(target)

    primary = json.loads((source / 'data/current-english-manifest.json').read_text())
    paired = json.loads((source / 'data/current-counterfactual-manifest.json').read_text())
    entries = primary['episodes'] + [e for e in paired['episodes'] if e['configuration'] == 'B']
    references = {}
    package_entries = {}
    original_packages = {}
    pairs_by_b = {pair['B_case']: pair for pair in paired['pairs']}
    images = set()

    def image_paths(value):
        if isinstance(value, dict):
            if value.get('image_path'):
                yield value['image_path']
            for child in value.values():
                yield from image_paths(child)
        elif isinstance(value, list):
            for child in value:
                yield from image_paths(child)

    for entry in entries:
        base = Path(entry['files']['visible']).parts[0]
        for kind, relative in entry['files'].items():
            copy('data/' + relative)
            if copied['data/' + relative] != entry['sha256'][kind]:
                raise ValueError('Input SHA mismatch')
        for relative, expected in entry['runtime_files'].items():
            copy('data/' + relative)
            if copied['data/' + relative] != expected:
                raise ValueError('Runtime SHA mismatch')
        world = json.loads((source / 'data' / entry['files']['hidden']).read_text())
        for relative in image_paths(world):
            image = Path(relative)
            if image.is_absolute() or '..' in image.parts or image.parts[0] != 'assets':
                raise ValueError('Unsafe image path')
            image = 'data/' + base + '/' + str(image)
            copy(image)
            images.add(image)
        batch = source / 'data' / base
        if base not in original_packages:
            original_packages[base] = json.loads((batch / 'manifest.json').read_text())
        original = original_packages[base]
        main_entry = next(e for e in original['episodes'] if e['short_id'] == entry['short_id'])
        group = main_entry
        if entry.get('configuration') == 'B':
            # Some retained variants have scenario-specific names or a sidecar
            # manifest. The adopted paired index explicitly names their source.
            relative = pairs_by_b[entry['case']]['B_reference']
            ref = {'sha256': sha(source / 'data' / relative)}
        else:
            ref = next(e for e in group['trajectories'] if e['strategy'] == 'reference')
            relative = base + '/' + ref['path']
        copy('data/' + relative)
        if copied['data/' + relative] != ref['sha256']:
            raise ValueError('Reference SHA mismatch')
        references[entry['case']] = {'path': relative, 'sha256': ref['sha256']}
        # Rebuild distribution metadata from an allowlist. Original source maps,
        # source posts, construction records and review pages are not exported.
        clean = {k: entry[k] for k in ('episode_id', 'short_id', 'family',
                 'structural_difficulty', 'version', 'title', 'files', 'sha256',
                 'runtime_root', 'runtime_class', 'runtime_files') if k in entry}
        clean['reference'] = references[entry['case']]
        clean['case'] = entry['case']
        package_entries.setdefault(base, []).append(clean)

    for base, rows in package_entries.items():
        write(DEST / 'data' / base / 'manifest.json', {
            'schema': 'redact-portable-package-v1', 'configurations': rows,
            'source_manifest_sha256': sha(source / 'data' / base / 'manifest.json'),
            'scope': 'Synthetic test inputs and frozen runtime only; distribution metadata is derived.'})
    for package in primary['packages']:
        package['manifest_sha256'] = sha(DEST / 'data' / package['manifest'])
        package['role'] = 'portable distribution metadata; scenario bytes unchanged'
    primary['selection_policy'] = 'Portable snapshot of adopted inputs; no archives or source mappings.'
    primary.pop('review_overview', None)
    for entry in primary['episodes']:
        entry.pop('review_page', None)
    write(DEST / 'data/current-english-manifest.json', primary)
    primary_sha = sha(DEST / 'data/current-english-manifest.json')
    paired['source_primary_manifest_sha256'] = primary_sha
    for pair in paired['pairs']:
        pair['source_manifest_sha256'] = sha(DEST / 'data' / pair['source_manifest'])
    for entry in paired['episodes']:
        entry.pop('review_page', None)
    write(DEST / 'data/current-counterfactual-manifest.json', paired)
    for pair in paired['pairs']:
        references[pair['A_case']] = references[pair['case']]
    write(DEST / 'data/reference-index.json', references)
    copy('eval/rubric.json')
    for name in ['data_paths.py', 'revealed_context.py', 'review_current_local.py',
                 'scoring_v2.py', 'aggregate_current_local_v2.py']:
        copy('eval/' + name)

    core = (source / 'eval/run_current_english_gemini.py').read_text()
    tree = ast.parse(core)
    # Keep the tested orchestration implementation, remove the old internal
    # transport/CLI. New network requests live only in the portable entrypoint.
    remove = {'ENDPOINT', 'REQUESTED_MODEL', 'request', 'main'}
    lines = core.splitlines(keepends=True)
    ranges = []
    for node in tree.body:
        name = getattr(node, 'name', None)
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in remove or isinstance(node, ast.If):
            ranges.append((node.lineno - 1, node.end_lineno))
    for start, end in sorted(ranges, reverse=True):
        lines[start:end] = []
    (DEST / 'eval/run_current_english_gemini.py').write_text(''.join(lines))
    parser_source = (source / 'eval/run_local_construction_models.py').read_text()
    parser_node = next(n for n in ast.parse(parser_source).body if getattr(n, 'name', '') == 'parse')
    (DEST / 'eval/run_local_construction_models.py').write_text(
        '"""Action parser extracted from the source runner."""\nimport json\n\n' +
        ast.get_source_segment(parser_source, parser_node) + '\n')
    image_source = (source / 'eval/run_current_local_multimodal.py').read_text()
    keep = {'image_bytes', 'image_references', 'attachments', 'image_relative_paths',
            'resolve_image_path', 'validate_inputs'}
    parts = []
    for node in ast.parse(image_source).body:
        if getattr(node, 'name', '') in keep:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
            parts.append(''.join(image_source.splitlines(keepends=True)[start:node.end_lineno]))
    (DEST / 'eval/evidence_images.py').write_text(
        '"""Revealed-image projection from the source multimodal adapter."""\n'
        'import functools\nimport hashlib\nimport json\nfrom pathlib import Path\n'
        'import run_current_english_gemini as core\n'
        'from data_paths import data_roots, resolve_data_path\nIMAGE_BINDINGS = {}\n\n' +
        '\n\n'.join(parts) + '\n')
    upstream = ['eval/run_current_english_gemini.py', 'eval/run_current_local_multimodal.py',
                'eval/run_local_construction_models.py', 'data/current-english-manifest.json',
                'data/current-counterfactual-manifest.json']
    write(DEST / 'release.json', {
        'schema': 'redact-collaborator-test-bundle-v1', 'independent_cases': 400,
        'paired_cases': 215, 'executable_configurations': len(entries),
        'image_sources': len(images), 'formal_evaluation_ready': False,
        'source_sha256': {p: sha(source / p) for p in upstream},
        'distribution_changes': 'Transport and metadata adapted; visible/hidden/rubrics/runtime/reference/image bytes preserved.',
        'semantic_evaluation_owner': 'Project owner; collaborators submit traces only.'})
    print(json.dumps({'exported_configurations': len(entries), 'copied_files': len(copied),
                      'images': len(images)}))


if __name__ == '__main__':
    main()
