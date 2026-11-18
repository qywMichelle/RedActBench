"""Audit mechanical work-call candidates; semantic necessity requires review."""
import argparse
import json
from pathlib import Path


def audit(initial, simulation):
    previous={r['id']:r for r in initial.get('resources',[])}
    rows=[]
    for step in simulation['history']:
        a=step['action'];op=a['action'];r=step.get('result',{});now=step.get('snapshot',{});target=a.get('target')
        effective=False
        if op in ('WAIT','FINISH'):
            reason='Scheduling/closure; excluded from effective work.'
        elif r.get('applied') is False or r.get('clarification_required'):
            reason='Rejected/conflicting/incomplete request; excluded.'
        elif op=='LOOKUP':
            ids=[x['id'] for x in r.get('resources',[])]
            effective=any(i not in previous for i in ids)
            reason='Previously unavailable evidence retrieved.' if effective else 'Only already displayed evidence; excluded.'
        elif op=='READ':
            reason='Observation already exposes current revealed resource content; redundant READ excluded.'
        elif op in ('SET','PATCH'):
            effective=any(previous.get(target,{}).get('fields',{}).get(k)!=v for k,v in a.get('fields',{}).items())
            reason='Local typed record changed; semantic necessity must be checked.' if effective else 'No substantive field change; excluded.'
        elif op=='WRITE':
            effective=any(previous.get(target,{}).get(k)!=a[k] for k in ('text','status','assets') if k in a)
            reason='Owned content changed; semantic necessity must be checked.' if effective else 'No substantive content change; excluded.'
        elif op in ('ASK','REPLY','SEND_LINK'):
            effective=True;reason='Actual request/message delivered; necessity and recipient coverage require review.'
        elif op=='OPERATE':
            effective=True;reason='Actual business operation/result obtained. An informative business failure receipt differs from a rejected protocol call.'
        else:
            reason='Unclassified; manual review required.'
        rows.append({'step':step['step'],'operation':op,'target':target,'mechanically_effective':effective,'reason':reason})
        previous=now
    return {'outer_calls':len(rows),'mechanically_effective_calls':sum(x['mechanically_effective'] for x in rows),'excluded_calls':sum(not x['mechanically_effective'] for x in rows),'semantic_minimality_proven':False,'scope':'Mechanical accounting only. Unnecessary messages, redundant evidence entry partitioning, avoidable record updates and legally mergeable actions must be challenged separately. This is not a global shortest-path proof.','steps':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--initial',required=True);p.add_argument('--trajectory',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    record=json.loads(Path(a.trajectory).read_text());result=audit(json.loads(Path(a.initial).read_text()),record.get('simulation',record))
    Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('outer_calls','mechanically_effective_calls','semantic_minimality_proven')}))
