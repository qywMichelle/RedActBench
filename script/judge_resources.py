"""Shared RSS accounting and conservative admission charges for judge workers."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def process_memory():
    scripts={str(ROOT/name).encode() for name in ['resume_with_rate_control.py','run_accelerated.py',
        'run_extra_opus.py','run_judge.py','run_judge_supervisor.py','judge_case.py','run_parallel_judge.py']}
    scripts.add(str(ROOT/'github_test_bundle/redact_bench.py').encode())
    result={}
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            argv=(path/'cmdline').read_bytes().split(b'\0')
            if not scripts.intersection(argv):continue
            values={}
            for line in (path/'status').read_text().splitlines():
                if line.startswith(('VmRSS:','State:')):
                    key,value=line.split(':',1);values[key]=value.strip()
            result[int(path.name)]=int(values.get('VmRSS','0').split()[0])*1024
        except (OSError,ValueError):continue
    return result


def aggregate_rss():return sum(process_memory().values())


def charge(packet):
    data=Path(packet).read_bytes()
    import re
    images=re.search(rb'"image_inputs"\s*:\s*\[\s*\{',data) is not None
    return (192 if images else 64)*1024**2+len(data)*8


def admitted(total,charges,observed,pid,requested,limit):
    excess=sum(max(0,value-observed.get(int(owner),0)) for owner,value in charges.items())
    return total+excess+max(0,requested-observed.get(pid,0))<=limit
