"""Detach a memory-limited scope; the key is inherited in memory, never in argv/files."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--directory', type=Path, required=True)
parser.add_argument('--scope', choices=['paired', 'all'], default='all')
parser.add_argument('--unit', required=True)
args = parser.parse_args()
directory = args.directory.resolve()
directory.mkdir(parents=True, exist_ok=True)
key = os.environ.get('REDACT_API_KEY') or getpass.getpass('API key (hidden): ')
env = dict(os.environ, REDACT_API_KEY=key, PYTHONUNBUFFERED='1')
command = ['systemd-run', '--user', '--scope', '--unit', args.unit,
           '--property=MemoryMax=1536M', '--property=MemorySwapMax=0', '--property=CPUWeight=20',
           str(ROOT / 'github_test_bundle/.venv/bin/python'), str(ROOT / 'run_background.py'),
           '--directory', str(directory), '--scope', args.scope]
command = ['prlimit', '--as=536870912', '--core=0', '--'] + command
with (directory / 'supervisor.log').open('a') as log:
    proc = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
print(json.dumps({'launcher_pid': proc.pid, 'systemd_unit': args.unit + '.scope',
                  'directory': str(directory), 'scope': args.scope}), flush=True)
