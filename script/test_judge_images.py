"""Reconstruct the completed GPT trajectory's actual PNG/SVG image transmissions."""
from pathlib import Path
import json
import resource

from judge_case import image_parts

ROOT=Path(__file__).resolve().parent
directory=ROOT/'github_test_bundle/output/ab-eval-20261119'
case='batch_015/t4-02/B/A'
trajectory=json.loads((directory/'gpt-6.1-sol-science/runs/paired-012/trajectories'/(case+'.json')).read_text())
index={}
for name in ['upstream-requests.jsonl','upstream-requests-accelerated.jsonl']:
    for line in (directory/name).open():
        try:row=json.loads(line)
        except ValueError:continue
        if row.get('model')=='gpt-6.1-sol-science' and row.get('status')==200 and row.get('image_resizes'):
            index[row['local_request_sha256']]=row['image_resizes']
delivery={str(row['request_index']):index[row['response']['request_body_sha256']]
    for row in trajectory['calls'] if row['response']['request_body_sha256'] in index}
packet={'case':case,'calls':[{'request':row['request_index'],'image_inputs':row['response'].get('image_inputs',[])}
    for row in trajectory['calls']]}
parts,metadata=image_parts(packet,delivery,'responses')
assert len(metadata)>=3 and len(parts)==2*len(metadata)
assert any(binding for bindings in delivery.values() for binding in bindings)
report={'case':case,'images':metadata,'recorded_transmissions_reconstructed':True,
    'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024}
(ROOT/'github_test_bundle/output/performance/judge-image-test.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
