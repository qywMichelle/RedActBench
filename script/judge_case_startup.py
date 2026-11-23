"""Targeted venv startup lock/admission only; unchanged grading program and inputs."""
import sys

HELD=None


def configure(config_path='/data/project/RedActBench/judge-parallel-config.json'):
    global HELD
    # CPython processes this venv's .pth twice. Keep one lock/reservation per process.
    if HELD is not None:return
    if not sys.argv or not sys.argv[0].endswith('/judge_case.py'):return
    import atexit
    import fcntl
    import hashlib
    import importlib.util
    import json
    import os
    from pathlib import Path
    import time
    try:
        config=json.loads(Path(config_path).read_text())
        if not config.get('enabled') or str(Path(sys.argv[0]).resolve())!=config['entrypoint']:return
        packet=Path(sys.argv[sys.argv.index('--packet')+1]).resolve()
        output=Path(config['output']).resolve()
        if not packet.is_relative_to(output/'lanes'):return
        source=Path(config['resources_source'])
        if hashlib.sha256(source.read_bytes()).hexdigest()!=config['resources_sha256']:return
        spec=importlib.util.spec_from_file_location('judge_admission_resources',source)
        resources=importlib.util.module_from_spec(spec);spec.loader.exec_module(resources)
    except (OSError,ValueError,KeyError):return
    locks=output/'.case-locks';locks.mkdir(exist_ok=True)
    HELD=(locks/(hashlib.sha256(str(packet).encode()).hexdigest()+'.lock')).open('a+')
    fcntl.flock(HELD,fcntl.LOCK_EX)
    requested=resources.charge(packet);pid=os.getpid();ledger=output/'memory-reservations.json'
    def prune(values,observed):return {owner:value for owner,value in values.items() if int(owner) in observed}
    while True:
        with (output/'.memory-reservation.lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            observed=resources.process_memory()
            state=json.loads(ledger.read_text()) if ledger.exists() else {'charges':{},'waiting':[]}
            values=prune(state.get('charges',{}),observed)
            waiting=[owner for owner in state.get('waiting',[]) if int(owner) in observed]
            if str(pid) not in waiting:waiting.append(str(pid))
            if waiting[0]==str(pid) and resources.admitted(sum(observed.values()),values,observed,pid,requested,config['reservation_limit_bytes']):
                values[str(pid)]=requested;waiting.remove(str(pid))
                ledger.write_text(json.dumps({'charges':values,'waiting':waiting}));break
            ledger.write_text(json.dumps({'charges':values,'waiting':waiting}))
        time.sleep(2)
    def release():
        try:
            with (output/'.memory-reservation.lock').open('a+') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                state=json.loads(ledger.read_text()) if ledger.exists() else {'charges':{},'waiting':[]}
                state['charges'].pop(str(pid),None)
                state['waiting']=[owner for owner in state.get('waiting',[]) if owner!=str(pid)]
                ledger.write_text(json.dumps(state))
        except (OSError,ValueError):pass
        if HELD is not None:HELD.close()
    atexit.register(release)
