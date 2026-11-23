"""Prefetch prepared, unjudged cases with the exact existing grader and locks."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

from judge_case import write
from judge_resources import aggregate_rss

ROOT=Path(__file__).resolve().parent
STOP=threading.Event()
threading.stack_size(1024*1024)


def live_adopted(pids):
    alive=[]
    for pid in pids:
        try:
            argv=(Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0')
            if str(ROOT/'judge_case.py').encode() in argv:alive.append(pid)
        except OSError:pass
    return alive


def available_slots(config,opus_done,adopted):
    limit=config['max_extra_workers'] if opus_done else config['extra_while_opus_running']
    return max(0,limit-len(adopted))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--adopt-extra-pids',type=int,nargs='*',default=[])
    args=parser.parse_args()
    config=json.loads((ROOT/'judge-parallel-config.json').read_text())
    output=Path(config['output']);directory=Path(config['directory'])
    lock=(output/'.parallel-helper.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    model=json.loads((output/'judge-binding.json').read_text())['judge_model']
    binding=json.loads((directory/'transport-binding.json').read_text())
    jobs={job['name']:job for job in binding['jobs']}
    state={'status':'running','pid':os.getpid(),'started_at':time.time(),'workers':{},'completed_cases':[],
        'needs_review':[],'failed_cases':[],'max_extra_workers':config['max_extra_workers']}
    previous=output/'parallel-status.json'
    if args.adopt_extra_pids and previous.exists():
        old=json.loads(previous.read_text())
        for key in ['started_at','completed_cases','needs_review','failed_cases']:state[key]=old.get(key,state[key])
        state['previous_manager_pid']=old.get('pid')
    mutex=threading.Lock();claimed=set();attempted=set()
    resized={}
    for name in ['upstream-requests.jsonl','upstream-requests-accelerated.jsonl']:
        for line in (directory/name).open():
            try:row=json.loads(line)
            except ValueError:continue
            if row.get('model')=='gpt-6.1-sol-science' and row.get('status')==200 and row.get('image_resizes'):
                resized[row['local_request_sha256']]=row['image_resizes']
    def save():
        state['updated_at']=time.time();state['aggregate_rss_bytes']=aggregate_rss()
        state['adopted_active_pids']=live_adopted(args.adopt_extra_pids)
        write(output/'parallel-status.json',state)
    def active_packets():
        paths=set()
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():continue
            try:
                argv=[arg.decode() for arg in (proc/'cmdline').read_bytes().split(b'\0') if arg]
                if str(ROOT/'judge_case.py') in argv and '--packet' in argv:paths.add(argv[argv.index('--packet')+1])
            except (OSError,UnicodeError,ValueError):continue
        return paths
    def pick():
        active=active_packets();candidates=[]
        for lane in (output/'lanes').iterdir():
            for review in (lane/'reviews').iterdir() if (lane/'reviews').exists() else []:
                job=jobs.get(review.name)
                if not job:continue
                for case in reversed(job['cases']):
                    packet=review/'judge-inputs'/(case+'.json')
                    if packet.is_file() and (review/'templates'/(case+'.json')).is_file() and not (review/'judgments'/(case+'.json')).exists():
                        path=str(packet)
                        if path not in active and path not in claimed and path not in attempted:candidates.append((review,case,packet))
        if not candidates:return None
        # Fill the tail of prepared shards; serial lanes keep their current calls.
        item=candidates[0];claimed.add(str(item[2]));return item
    def worker(index):
        while not STOP.is_set():
            current=json.loads((ROOT/'judge-parallel-config.json').read_text())
            opus_path=directory/'claude-opus-5-5-science/status.json'
            opus_done=opus_path.exists() and json.loads(opus_path.read_text()).get('status')=='behavior_complete'
            allowed=available_slots(current,opus_done,live_adopted(args.adopt_extra_pids))
            if index>=allowed or aggregate_rss()+64*1024**2>current['helper_admission_limit_bytes']:
                with mutex:state['workers'][str(index)]={'status':'slot_wait' if index>=allowed else 'memory_wait'};save()
                STOP.wait(3);continue
            with mutex:item=pick()
            if item is None:
                with mutex:state['workers'][str(index)]={'status':'waiting_for_prepared_cases'};save()
                if all(json.loads((lane/'status.json').read_text()).get('status') in {'complete','partial','stopped','needs_attention'}
                       for lane in (output/'lanes').iterdir() if (lane/'status.json').exists()):break
                STOP.wait(3);continue
            review,case,packet=item
            try:
                run=directory/'gpt-6.1-sol-science/runs'/review.name
                raw_path=run/'trajectories'/(case+'.json');raw=json.loads(raw_path.read_text())
                prepared=json.loads(packet.read_text())
                if hashlib.sha256(raw_path.read_bytes()).hexdigest()!=prepared['trajectory_sha256']:raise ValueError('Stale prepared packet')
                delivery={str(row['request_index']):resized[row['response']['request_body_sha256']]
                    for row in raw['calls'] if row['response']['request_body_sha256'] in resized}
                delivery_path=review/'delivery'/(case+'.json');write(delivery_path,delivery)
                del raw,prepared,delivery
                with mutex:state['workers'][str(index)]={'status':'judging','case':case,'packet':str(packet)};save()
                command=['prlimit','--as=536870912','--core=0','--',str(ROOT/'github_test_bundle/.venv/bin/python'),
                    str(ROOT/'judge_case.py'),'--packet',str(packet),'--template',str(review/'templates'/(case+'.json')),
                    '--delivery',str(delivery_path),'--output',str(review),'--model',model,'--resource-root',str(output)]
                with (output/(f'parallel-worker-{index}.log')).open('a') as log:
                    child=subprocess.Popen(command,cwd=ROOT,env=os.environ,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
                    while child.poll() is None:
                        if STOP.wait(1):child.terminate();break
                    code=child.wait()
                result_path=review/'case-status'/(case+'.json')
                result=json.loads(result_path.read_text()) if result_path.exists() else {}
                with mutex:
                    if code==0 and result.get('status')=='complete':
                        state['completed_cases'].append(case)
                        if result.get('needs_primary_review'):state['needs_review'].append(case)
                    elif result.get('status')=='needs_review':state['needs_review'].append(case)
                    else:state['failed_cases'].append({'case':case,'exit_code':code})
                    save()
            except Exception as exc:
                key=os.environ.get('REDACT_API_KEY','');message=str(exc).replace(key,'[REDACTED]') if key else str(exc)
                with mutex:state['failed_cases'].append({'case':case,'error':message});save()
            finally:
                with mutex:
                    claimed.discard(str(packet));attempted.add(str(packet))
                    state['workers'][str(index)]={'status':'idle'};save()
        with mutex:state['workers'][str(index)]={'status':'finished'};save()
    with ThreadPoolExecutor(max_workers=config['max_extra_workers']) as pool:
        futures=[pool.submit(worker,index) for index in range(config['max_extra_workers'])]
        for future in futures:future.result()
    while live_adopted(args.adopt_extra_pids) and not STOP.is_set():
        with mutex:save()
        STOP.wait(3)
    with mutex:state['status']='stopped' if STOP.is_set() else 'complete';save()


if __name__=='__main__':
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:STOP.set())
    main()
