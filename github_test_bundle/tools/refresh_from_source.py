"""Export the current synthetic inputs and required runtime closure, without archives."""
import argparse
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
    for name in ['data_paths.py', 'revealed_context.py',
                 'scoring_v2.py', 'aggregate_current_local_v2.py']:
        copy('eval/' + name)

    adapters = ['run_current_english_gemini.py', 'run_local_construction_models.py',
                'evidence_images.py', 'checkpoint_replay.py', 'run_recovery.py',
                'review_current_local.py']
    for name in adapters:
        if not (DEST / 'eval' / name).is_file():
            raise ValueError('Start from the current client scaffold; missing eval/' + name)
    upstream = ['eval/run_current_english_gemini.py', 'eval/run_current_local_multimodal.py',
                'eval/run_local_construction_models.py', 'data/current-english-manifest.json',
                'data/current-counterfactual-manifest.json']
    write(DEST / 'release.json', {
        'schema': 'redact-collaborator-test-bundle-v1', 'independent_cases': 400,
        'paired_cases': 215, 'executable_configurations': len(entries),
        'image_sources': len(images), 'formal_evaluation_ready': False,
        'source_sha256': {p: sha(source / p) for p in upstream},
        'distribution_changes': 'Transport and metadata adapted; visible/hidden/rubrics/runtime/reference/image bytes preserved.',
        'semantic_evaluation_owner': 'Project owner; collaborators submit traces only.',
        'behavior_run_schema': 'redact-collaborator-behavior-test-v2',
        'resume_policy': 'same frozen v2 code/data/config; verify recorded requests before continuation',
        'previous_release_commit': 'aa9c58e3f078e15d77a3643304d552fb781f76cd'})
    print(json.dumps({'exported_configurations': len(entries), 'copied_files': len(copied),
                      'images': len(images)}))


if __name__ == '__main__':
    main()
