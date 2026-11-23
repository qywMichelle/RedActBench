"""Finish original Opus checkpoints through the live equivalent bridge."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parent
BASE=ROOT/'github_test_bundle/output/ab-eval-20261119'
MODEL='claude-opus-5-5-science'
RUN=BASE/MODEL/'runs/paired-019'
PYTHON=ROOT/'github_test_bundle/.venv/bin/python'
ENTRY=ROOT/'github_test_bundle/redact_bench.py'
TERMINAL={'complete','request_limit','action_budget_exhausted','input_budget_exceeded'}


def write(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');temp.replace(path)


def execute(args):
    with (BASE/MODEL/'logs/paired-019-bridge-recovery.log').open('a') as log:
        return subprocess.run(['prlimit','--as=536870912','--core=0','--',str(PYTHON),str(ENTRY),*args],
            cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT).returncode


def main():
    binding=json.loads((BASE/'transport-binding.json').read_text())
    status=BASE/'opus-finish-recovery-status.json'
    attempts=0
    while True:
        write(status,{'status':'resuming','run':str(RUN),'pid':os.getpid(),'attempt':attempts,'updated_at':time.time()})
        code=execute(['run','--output',str(RUN),'--resume'])
        selected=json.loads((RUN/'run_config.json').read_text())['cases'];remaining=[];errors=[]
        for case in selected:
            p=RUN/'trajectories'/(case+'.json');record=json.loads(p.read_text()) if p.exists() else {}
            if record.get('status') not in TERMINAL:remaining.append(case)
            if record.get('status')=='infrastructure_error':errors.append(record.get('error',''))
        if not remaining:break
        if errors and not any(any(s in error for s in ['URLError','HTTP 429','HTTP 500','HTTP 502','HTTP 503','HTTP 504','invalid_grant','timed out']) for error in errors):
            raise RuntimeError('Nonretryable infrastructure error; original checkpoints preserved')
        attempts+=1
        if attempts>72:raise RuntimeError('Recovery attempts exhausted; original checkpoints preserved')
        if errors:
            write(status,{'status':'recovery_wait','remaining_cases':remaining,'last_exit_code':code,'updated_at':time.time()})
            time.sleep(min(300,30*attempts))
    if execute(['check-run','--run',str(RUN)]):raise RuntimeError('Official replay check failed')
    archive=BASE/MODEL/'exports/paired-019.zip'
    if execute(['export','--run',str(RUN),'--output',str(archive)]):raise RuntimeError('Official export failed')
    import resume_with_image_budget as images
    verified=[]
    for job in binding['jobs']:
        run=BASE/MODEL/'runs'/job['name'];zip_path=BASE/MODEL/'exports'/(job['name']+'.zip')
        if not images.exported_run_unchanged(run,zip_path,job['cases']):raise RuntimeError('Export verification failed: '+job['name'])
        verified.append(job['name'])
    state_path=BASE/MODEL/'status.json';state=json.loads(state_path.read_text())
    state.update(status='behavior_complete',completed_shards=verified,planned_configurations=615,
        updated_at=time.time(),last_exit_code=0,completion_note='All original configurations ended and exports verified; terminal request/input budget outcomes retained. No semantic pass claim.')
    write(state_path,state)
    write(status,{'status':'behavior_complete','verified_shards':len(verified),'planned_configurations':615,
        'input_and_request_budget_outcomes_preserved':True,'updated_at':time.time()})


if __name__=='__main__':
    try:main()
    except Exception as exc:
        key=os.environ.get('REDACT_API_KEY','');error=str(exc).replace(key,'[REDACTED]') if key else str(exc)
        write(BASE/'opus-finish-recovery-status.json',{'status':'needs_attention','error':error,'updated_at':time.time()})
        raise SystemExit(2)
