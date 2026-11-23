"""Four small judge lanes, serial heavy work and combined official v2 metrics."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import judge_protocol
from judge_case import write
from judge_resources import aggregate_rss
from scoring_v2 import aggregate

ROOT=Path(__file__).resolve().parent
STOP=False


class AttachedLane:
    """Monitor an already-running lane without restarting its model requests."""
    def __init__(self,pid,lane):self.pid,self.lane=pid,lane
    def poll(self):
        proc=Path('/proc')/str(self.pid)
        try:
            argv=(proc/'cmdline').read_bytes().split(b'\0')
            alive=any(arg.endswith(b'/run_judge.py') for arg in argv) and str(self.lane).encode() in argv
            zombie=any(line.startswith('State:') and '\tZ' in line for line in (proc/'status').read_text().splitlines())
            if alive and not zombie:return None
        except OSError:pass
        path=self.lane/'status.json'
        state=json.loads(path.read_text()) if path.exists() else {}
        return 0 if state.get('status') in {'complete','partial','stopped'} else 2
    def wait(self):
        while self.poll() is None:time.sleep(1)
        return self.poll()
    def terminate(self):
        if self.poll() is None:os.kill(self.pid,signal.SIGTERM)


def collect(output,model):
    states=[];reports=[]
    for lane in sorted((output/'lanes').glob('*')):
        if (lane/'status.json').is_file():states.append(json.loads((lane/'status.json').read_text()))
        for path in (lane/'reviews').glob('*/metrics-v2.json'):
            report=json.loads(path.read_text())
            if report['overall']['scored_episodes']:reports.append(report)
    rows=[row for report in reports for row in report['rows']]
    completed={};unresolved=set()
    for path in (output/'lanes').glob('*/reviews/*/case-status/**/*.json'):
        result=json.loads(path.read_text());case=result.get('case')
        if result.get('status')=='complete':completed[case]=result
        elif result.get('status')=='needs_review':unresolved.add(case)
    pending=sorted({case for case,result in completed.items() if result.get('needs_primary_review')}|unresolved)
    failed=[item for state in states for item in state.get('failed_cases',[]) if item.get('case') not in completed]
    pairs=json.loads((judge_protocol.BUNDLE/'data/current-counterfactual-manifest.json').read_text())['episodes']
    configurations={entry['case']:entry['configuration'] for entry in pairs}
    by_variant={label:aggregate([row for row in rows if configurations.get(row['case'])==configuration])
        for label,configuration in [('paired_A','A'),('paired_B','B')]}
    by_variant['unpaired_primary']=aggregate([row for row in rows if row['case'] not in configurations])
    complete=len(completed)
    parallel_path=output/'parallel-status.json'
    parallel=json.loads(parallel_path.read_text()) if parallel_path.exists() else None
    parallel_config=output/'parallel-binding.json'
    extra_limit=json.loads(parallel_config.read_text()).get('max_extra_workers',0) if parallel_config.exists() else 0
    status={'status':'running','judge_model':model,'planned_cases':615,'completed_cases':complete,
        'needs_review':pending,'failed_cases':failed,'lanes':states,'aggregate_rss_bytes':aggregate_rss(),
        'updated_at':time.time(),'maximum_parallel_judge_calls':4+extra_limit,'memory_heavy_work_parallelism':1,
        'parallel_helpers':parallel,'serial_lane_completed_cases':sum(state.get('completed_cases',0) for state in states)}
    write(output/'status.json',status)
    write(output/'summary.json',{'scoring_version':'redact-scoring-v2','status':'partial',
        'judge_model':model,'provisional_automated_scores':True,'self_evaluation':model=='gpt-6.1-sol-science',
        'planned_cases':615,'overall':aggregate(rows),'by_variant':by_variant,'needs_primary_review':pending,
        'failed_cases':failed,'completed_cases':complete,'officially_aggregated_shards':len(reports),
        'interpretation':'Automatic LLM semantic review; no human confirmation or judge calibration. Missing reviews are not zero scores.'})
    return status


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--model',default='gpt-6.1-sol-science')
    parser.add_argument('--adopt-pids',type=int,nargs=4)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    lifetime=(output/'.judge-supervisor.lock').open('a+');fcntl.flock(lifetime,fcntl.LOCK_EX|fcntl.LOCK_NB)
    (output/'lanes/0/reviews').mkdir(parents=True,exist_ok=True)
    # The successful real pilot remains an immutable judgment and is reused.
    old=output/'reviews/paired-000';new=output/'lanes/0/reviews/paired-000'
    if old.exists() and not new.exists():old.rename(new)
    if (output/'initial-trial.json').exists() and not (output/'lanes/0/initial-trial.json').exists():
        (output/'lanes/0/initial-trial.json').write_bytes((output/'initial-trial.json').read_bytes())
    sources={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ['run_judge_supervisor.py','run_judge.py','judge_case.py','judge_protocol.py','judge_packet_codec.py']}
    binding={'schema':'redact-api-judge-supervisor-v1','judge_model':args.model,'lanes':4,
        'source_sha256':sources,'prompt_sha256':hashlib.sha256(judge_protocol.SYSTEM.encode()).hexdigest(),
        'max_output_tokens':16384,'per_process_address_space_limit_bytes':536870912,
        'memory_watermark_bytes':1468006400,'memory_heavy_work_parallelism':1,'provisional_automated_scores':True}
    path=output/'judge-binding.json'
    if path.exists() and json.loads(path.read_text())!=binding:
        previous=json.loads(path.read_text())
        if not args.adopt_pids:raise ValueError('Judge supervisor binding changed')
        for key in ['judge_model','prompt_sha256','max_output_tokens','lanes']:
            if previous[key]!=binding[key]:raise ValueError('Cannot adopt lanes with different judging parameters')
        for name,sha in previous['source_sha256'].items():
            if name!='run_judge_supervisor.py' and sources[name]!=sha:raise ValueError('Judge lane source changed')
        snapshot=output/'source-snapshots'/('supervisor-binding-'+hashlib.sha256(path.read_bytes()).hexdigest()+'.json')
        snapshot.write_bytes(path.read_bytes())
    write(path,binding)
    children=[]
    for index in range(4):
        lane=output/'lanes'/str(index);lane.mkdir(parents=True,exist_ok=True)
        if args.adopt_pids:
            children.append(AttachedLane(args.adopt_pids[index],lane));continue
        command=['prlimit','--as=536870912','--core=0','--',str(ROOT/'github_test_bundle/.venv/bin/python'),
            str(ROOT/'run_judge.py'),'--directory',str(args.directory.resolve()),'--output',str(lane),
            '--model',args.model,'--partition-index',str(index),'--partition-count','4','--resource-root',str(output)]
        with (output/(f'lane-{index}.log')).open('a') as log:
            children.append(subprocess.Popen(command,cwd=ROOT,env=os.environ,stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT))
    def helper_running():
        path=output/'parallel-status.json'
        if not path.exists():return False
        status=json.loads(path.read_text())
        pid=status.get('pid')
        if status.get('status')!='running' or not pid:return False
        try:return str(ROOT/'run_parallel_judge.py').encode() in (Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0')
        except OSError:return False
    while any(child.poll() is None for child in children) or helper_running():
        collect(output,args.model)
        if STOP:
            for child in children:
                if child.poll() is None:child.terminate()
            break
        time.sleep(5)
    codes=[child.wait() for child in children]
    status=collect(output,args.model)
    status['status']='stopped' if STOP else ('complete' if status['completed_cases']==615 and
        not status['needs_review'] and not status['failed_cases'] and not any(codes) else 'partial')
    status['lane_exit_codes']=codes;write(output/'status.json',status)
    summary=json.loads((output/'summary.json').read_text());summary['status']=status['status'];write(output/'summary.json',summary)


def stop(*_):
    global STOP
    STOP=True


if __name__=='__main__':
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
    try:main()
    except Exception as exc:
        key=os.environ.get('REDACT_API_KEY','');message=str(exc).replace(key,'[REDACTED]') if key else str(exc)
        print(type(exc).__name__+': '+message);raise SystemExit(2)
