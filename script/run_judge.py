"""Resumable judge lane; each lane is serial and shares heavy-work memory locks."""
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from judge_case import write
from judge_packet_codec import compact
import judge_protocol

ROOT=Path(__file__).resolve().parent
PYTHON=ROOT/'github_test_bundle/.venv/bin/python'
ENTRY=ROOT/'github_test_bundle/redact_bench.py'
STOP=False
OUTPUT=None


def aggregate_rss():
    scripts={str(ROOT/name).encode() for name in ['resume_with_rate_control.py','run_accelerated.py',
        'run_extra_opus.py','run_judge.py','run_judge_supervisor.py','judge_case.py']} | {str(ENTRY).encode()}
    total=0
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            if not scripts.intersection((path/'cmdline').read_bytes().split(b'\0')):continue
            for line in (path/'status').read_text().splitlines():
                if line.startswith('VmRSS:'):total+=int(line.split()[1])*1024;break
        except (OSError,ValueError):continue
    return total


def main():
    global OUTPUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--model',default='gpt-6.1-sol-science')
    parser.add_argument('--partition-index',type=int,default=0)
    parser.add_argument('--partition-count',type=int,default=1)
    parser.add_argument('--resource-root',type=Path)
    args=parser.parse_args();directory=args.directory.resolve();output=args.output.resolve()
    OUTPUT=output
    output.mkdir(parents=True,exist_ok=True)
    resource_root=(args.resource_root or output).resolve();resource_root.mkdir(parents=True,exist_ok=True)
    if not 0<=args.partition_index<args.partition_count:raise ValueError('Invalid lane partition')
    lock=(output/'.judge.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    binding=json.loads((directory/'transport-binding.json').read_text())
    jobs=[job for index,job in enumerate(binding['jobs']) if index%args.partition_count==args.partition_index]
    planned=sum(len(job['cases']) for job in jobs)
    sources={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ['run_judge.py','judge_case.py','judge_protocol.py','judge_packet_codec.py']}
    frozen={name:hashlib.sha256((ROOT/'github_test_bundle'/name).read_bytes()).hexdigest() for name in
        ['SHA256SUMS.json','eval/scoring_v2.py','eval/rubric.json','eval/review_current_local.py']}
    manifest_hashes={job['name']:hashlib.sha256((directory/'gpt-6.1-sol-science/runs'/job['name']/'frozen-manifest.json').read_bytes()).hexdigest() for job in binding['jobs']}
    judge_binding={'schema':'redact-api-judge-v1','judge_model':args.model,'source_sha256':sources,
        'frozen_sha256':frozen,'source_manifests':manifest_hashes,'scoring_version':'redact-scoring-v2',
        'prompt_sha256':hashlib.sha256(judge_protocol.SYSTEM.encode()).hexdigest(),
        'max_output_tokens':16384,'api_base':'https://mp.z01.normandyfunc.com/v1',
        'simultaneous_judge_workers':1,'per_process_address_space_limit_bytes':536870912,
        'partition_index':args.partition_index,'partition_count':args.partition_count,
        'provisional_automated_scores':True,'self_evaluation':args.model=='gpt-6.1-sol-science',
        'cq':'not_scorable: no calibrated CQ anchors supplied','reference_trajectories_in_judge_prompt':False}
    path=output/'judge-binding.json'
    if path.exists() and json.loads(path.read_text())!=judge_binding:
        raise ValueError('Judge binding changed; use the original program/model or a new output directory')
    if not path.exists():write(path,judge_binding)
    source_dir=output/'source-snapshots';source_dir.mkdir(exist_ok=True)
    for name in sources:
        p=source_dir/name
        if not p.exists():p.write_bytes((ROOT/name).read_bytes())
    state={'status':'preparing','judge_model':args.model,'planned_cases':planned,'completed_cases':0,
        'needs_review':[],'failed_cases':[],'completed_shards':[],'started_at':time.time()}
    write(output/'status.json',state)
    def execute(command,log):
        with log.open('a') as stream:
            child=subprocess.Popen(['prlimit','--as=536870912','--core=0','--']+list(map(str,command)),
                cwd=ROOT,env=os.environ,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
            while child.poll() is None:
                if int(time.monotonic())%5==0:
                    state['aggregate_rss_bytes']=aggregate_rss();write(output/'status.json',state)
                if STOP:
                    child.terminate()
                    try:child.wait(timeout=15)
                    except subprocess.TimeoutExpired:child.kill()
                    break
                time.sleep(.5)
            return child.wait()
    resized={}
    for name in ['upstream-requests.jsonl','upstream-requests-accelerated.jsonl']:
        for line in (directory/name).open():
            try:row=json.loads(line)
            except ValueError:continue
            if row.get('model')=='gpt-6.1-sol-science' and row.get('status')==200 and row.get('image_resizes'):
                resized[row['local_request_sha256']]=row['image_resizes']
    for job in jobs:
        if STOP:break
        shard=job['name'];run=directory/'gpt-6.1-sol-science/runs'/shard;review=output/'reviews'/shard
        log=output/(shard+'.log');state.update(status='preparing',current_shard=shard,updated_at=time.time());write(output/'status.json',state)
        packets=list((review/'judge-inputs').rglob('*.json')) if review.exists() else []
        if len(packets)!=len(job['cases']):
            with (resource_root/'.judge-heavy.lock').open('a+') as heavy:
                fcntl.flock(heavy,fcntl.LOCK_EX)
                while aggregate_rss()+402653184>1468006400 and not STOP:time.sleep(5)
                code=execute([PYTHON,ENTRY,'evaluate','--run',run,'--output',review,'--prepare'],log)
            if code:raise RuntimeError('Frozen review preparation failed: '+shard)
        for case in job['cases']:
            if STOP:break
            packet=review/'judge-inputs'/(case+'.json');template=review/'templates'/(case+'.json')
            trajectory=run/'trajectories'/(case+'.json')
            raw=json.loads(trajectory.read_text())
            if raw['status']!='complete':raise ValueError('GPT trajectory no longer complete: '+case)
            prepared=json.loads(packet.read_text())
            if prepared['trajectory_sha256']!=hashlib.sha256(trajectory.read_bytes()).hexdigest():raise ValueError('Prepared packet is stale')
            delivery={str(row['request_index']):resized[row['response']['request_body_sha256']]
                for row in raw['calls'] if row['response']['request_body_sha256'] in resized}
            delivery_path=review/'delivery'/(case+'.json');write(delivery_path,delivery)
            del raw,prepared,delivery
            trial_path=output/'initial-trial.json'
            if trial_path.exists():
                trial=json.loads(trial_path.read_text())
                if trial.get('case')==case:
                    proc=Path('/proc')/str(trial['pid'])
                    while proc.exists() and not STOP:
                        try:
                            if b'judge_case.py' not in (proc/'cmdline').read_bytes():break
                            if any(line.startswith('State:') and '\tZ' in line for line in (proc/'status').read_text().splitlines()):break
                        except OSError:break
                        state.update(status='judging',current_case=case,trial_pid=trial['pid'],
                            aggregate_rss_bytes=aggregate_rss(),updated_at=time.time());write(output/'status.json',state)
                        time.sleep(1)
            while aggregate_rss()+100663296>1468006400 and not STOP:
                state.update(status='memory_wait',current_case=case,aggregate_rss_bytes=aggregate_rss(),updated_at=time.time())
                write(output/'status.json',state);time.sleep(5)
            if STOP:break
            state.update(status='judging',current_case=case,updated_at=time.time());write(output/'status.json',state)
            command=[PYTHON,ROOT/'judge_case.py','--packet',packet,'--template',template,
                '--delivery',delivery_path,'--output',review,'--model',args.model,'--resource-root',resource_root]
            code=execute(command,log)
            for recovery in range(3):
                if not code or STOP:break
                errors=list((review/'raw-responses'/case).rglob('http-error-*.json'))
                latest=json.loads(max(errors,key=lambda p:p.stat().st_mtime).read_text()) if errors else {}
                if not latest or latest.get('status') not in {None,429,500,502,503,504}:break
                state.update(status='recovery_wait',current_case=case,recovery_attempt=recovery+1,
                    updated_at=time.time());write(output/'status.json',state)
                delay=60*(recovery+1)
                for _ in range(delay):
                    if STOP:break
                    time.sleep(1)
                if STOP:break
                code=execute(command,log)
            result_path=review/'case-status'/(case+'.json')
            result=json.loads(result_path.read_text()) if result_path.exists() else {}
            if not code and result.get('status')=='complete':
                state['completed_cases']+=1
                if result.get('needs_primary_review'):state['needs_review'].append(case)
            elif result.get('status')=='needs_review':state['needs_review'].append(case)
            else:state['failed_cases'].append({'case':case,'exit_code':code})
            write(output/'status.json',state)
        if STOP:break
        state.update(status='aggregating',updated_at=time.time());write(output/'status.json',state)
        with (resource_root/'.judge-heavy.lock').open('a+') as heavy:
            fcntl.flock(heavy,fcntl.LOCK_EX)
            while aggregate_rss()+402653184>1468006400 and not STOP:time.sleep(5)
            code=execute([PYTHON,ENTRY,'evaluate','--run',run,'--output',review,'--partial'],log)
        if code:state['failed_cases'].append({'shard':shard,'aggregation_exit_code':code})
        else:state['completed_shards'].append(shard)
        write(output/'status.json',state)
        reports=[]
        for path in (output/'reviews').glob('*/metrics-v2.json'):
            r=json.loads(path.read_text())
            if r['overall']['scored_episodes']:reports.append(r)
        rows=[row for report in reports for row in report['rows']]
        from scoring_v2 import aggregate
        write(output/'summary.json',{'scoring_version':'redact-scoring-v2','status':'partial',
            'judge_model':args.model,'provisional_automated_scores':True,'self_evaluation':judge_binding['self_evaluation'],
            'planned_cases':planned,'aggregated_shards':len(reports),'overall':aggregate(rows),
            'needs_primary_review':state['needs_review'],'failed_cases':state['failed_cases'],
            'interpretation':'Automatic LLM judgments; not human-confirmed benchmark scores. Unreviewed cases are not assigned zero.'})
    state.update(status='stopped' if STOP else ('complete' if state['completed_cases']==planned and not state['needs_review'] and not state['failed_cases'] else 'partial'),updated_at=time.time())
    write(output/'status.json',state)
    if (output/'summary.json').exists():
        summary=json.loads((output/'summary.json').read_text());summary['status']=state['status'];write(output/'summary.json',summary)


def stop(*_):
    global STOP
    STOP=True


if __name__=='__main__':
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
    try:main()
    except Exception as exc:
        key=os.environ.get('REDACT_API_KEY','');message=str(exc).replace(key,'[REDACTED]') if key else str(exc)
        if OUTPUT is not None:
            path=OUTPUT/'status.json'
            state=json.loads(path.read_text()) if path.exists() else {}
            state.update(status='needs_attention',error=type(exc).__name__+': '+message,updated_at=time.time())
            write(path,state)
        print(type(exc).__name__+': '+message,file=sys.stderr);raise SystemExit(2)
