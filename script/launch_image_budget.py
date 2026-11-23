"""Launch a disclosed transport revision without writing the credential."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--directory', type=Path, required=True)
parser.add_argument('--unit', required=True)
args = parser.parse_args()
directory = args.directory.resolve()
key = os.environ.get('REDACT_API_KEY') or getpass.getpass('API key (hidden): ')
env = dict(os.environ, REDACT_API_KEY=key, PYTHONUNBUFFERED='1',
           PYTHONDONTWRITEBYTECODE='1', MALLOC_ARENA_MAX='1')
command = ['prlimit', '--as=536870912', '--core=0', '--',
           'systemd-run', '--user', '--scope', '--unit', args.unit,
           '--property=MemoryMax=1536M', '--property=MemorySwapMax=0', '--property=CPUWeight=20',
           str(root / 'github_test_bundle/.venv/bin/python'), str(root / 'resume_with_image_budget.py'),
           '--directory', str(directory), '--scope', 'all']
with (directory / 'supervisor.log').open('a') as log:
    proc = subprocess.Popen(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
print(json.dumps({'launcher_pid': proc.pid, 'systemd_unit': args.unit + '.scope',
                  'directory': str(directory), 'transport_revision': 'full-canvas-image-patches-v2-strip-resize-hc-route'}))
