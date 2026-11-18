"""Batch017 case registry and independently reviewed lawful simplifications."""
from helpers import pair
from cases_preflight import film,patrol,trail,concert,kitchen
REGISTRY={'t1-01':film,'t2-01':patrol,'t3-01':trail,'t4-03':concert,'t5-04':kitchen}
from cases_medium import REGISTRY as MEDIUM
from cases_hard import REGISTRY as HARD
REGISTRY.update(MEDIUM);REGISTRY.update(HARD)
try:
 from cases_primary import REGISTRY as PRIMARY
 REGISTRY.update(PRIMARY)
except ImportError:pass
# R2 independently executed these omissions. They remove redundant evidence or
# containment, without turning a preferred route into a mandatory one.
REVIEWED_OMISSIONS={
 't1-01':{'ops':[('publisher','pause')]},'t1-02':{'keys':['camera']},
 't1-03':{'keys':['prepared']},'t1-04':{'keys':['voice']},
 't2-02':{'keys':['state']},'t2-03':{'keys':['move-state','patrol-state']},
 't2-04':{'keys':['source-state','outgoing']},'t3-01':{'keys':['guide-state']},
 't3-02':{'keys':['private']},'t3-03':{'keys':['voice']},
 't4-01':{'keys':['original']},'t4-02':{'ops':[('archive','inspect')]},
 't4-03':{'keys':['partner']},'t5-01':{'keys':['ballots']},
 't5-02':{'keys':['state']},'t5-03':{'keys':['voice','cabinet','handover-state']},
 't5-04':{'keys':['cold-contract']}}
def apply_reviewed_simplification(c):
 cfg=REVIEWED_OMISSIONS.get(c['short_id'],{})
 p=c['plans']['strong_simplification']
 p['actions']=[a for a in p['actions'] if not (
  a['action']=='LOOKUP' and a['entry'] in cfg.get('keys',[]) or
  a['action']=='OPERATE' and (a['target'],a['choice']) in cfg.get('ops',[]))]
 if cfg:
  en='Lawful simplification includes independently executed R2 omissions; observed call counts are upper bounds, not proofs of a global minimum.'
  zh='合法简化纳入R2实际执行过的省略；已观察调用数是可行上界，不是全局最小证明。'
  p['notes']=en;c['translations'][en]=zh
 if c.get('contrast'):apply_reviewed_simplification(c['contrast'])
 return c
def cases(ids=None):return [apply_reviewed_simplification(pair(fn)) for sid,fn in sorted(REGISTRY.items()) if ids is None or sid in ids]
