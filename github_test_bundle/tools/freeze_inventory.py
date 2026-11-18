"""Freeze distribution files; never include generated runs, credentials or scores."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {'runs', 'output', 'exports', '.venv', '__pycache__', '.git', '.env'}


def main():
    hashes = {}
    for path in sorted(ROOT.rglob('*')):
        relative = path.relative_to(ROOT)
        if set(relative.parts) & EXCLUDE or path.name == 'SHA256SUMS.json':
            continue
        if path.is_symlink():
            raise ValueError('Symlink in distribution: ' + str(relative))
        if path.is_file():
            hashes[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    (ROOT / 'SHA256SUMS.json').write_text(json.dumps(hashes, indent=2) + '\n')
    print(json.dumps({'frozen_files': len(hashes)}))


if __name__ == '__main__':
    main()
