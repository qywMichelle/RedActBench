"""Check public artifacts for CJK text; semantic English review remains manual."""
import json
from pathlib import Path
import re
import sys
root = Path(sys.argv[1]).resolve()
findings = []
checked = 0
for p in sorted(root.rglob('*')):
    if not p.is_file() or any(x in p.relative_to(root).parts for x in ('private', '__pycache__')):
        continue
    if p.suffix not in ('.json', '.html', '.md', '.py', '.txt', '.log', '.cjs'):
        continue
    checked += 1
    for n, line in enumerate(p.read_text().splitlines(), 1):
        if re.search(r'[\u3400-\u4dbf\u4e00-\u9fff]', line):
            findings.append({'path': str(p.relative_to(root)), 'line': n})
result = {'status': 'pass' if not findings else 'fail', 'files_checked': checked,
          'cjk_findings': findings, 'scope': 'Public package CJK scan; does not prove idiomatic English.'}
print(json.dumps(result, indent=2))
sys.exit(bool(findings))
