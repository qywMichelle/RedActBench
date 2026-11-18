"""Deterministic text workbench. It records actions, never scores their meaning."""
from copy import deepcopy
import hashlib,json
PROTOCOL='redact-b004-v1'
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
class World:
 def __init__(self,case):
  self.case=deepcopy(case);self.time=0;self.done=False;self.resources={r['id']:deepcopy(r) for r in case['resources']};self.history=[];self.events=[];self.fired=set();self.pending=[];self.calls=0;self.handoff='';self.handoff_time=None
 def reveal(self):
  for e in self.case['events']+self.pending:
   if e['id'] in self.fired or e.get('at',9999)>self.time:continue
   self.fired.add(e['id'])
   for r in e['add']:self.resources[r['id']]=deepcopy(r)
   self.events.append({'event_id':e['id'],'time':e['at'],'added':[r['id'] for r in e['add']]})
 def observe(self):
  self.reveal();return {'episode_id':self.case['id'],'version':self.case['version'],'protocol':PROTOCOL,'time':self.time,'deadline':self.case['deadline'],'done':self.done,'task':self.case['task'],'authorization':self.case['authorization'],'tool_protocol':self.case['tool_protocol'],'budget':{'calls':self.case['budget']['calls'],'used':self.calls,'remaining':max(0,self.case['budget']['calls']-self.calls),'counting':'Every successful action including WAIT and FINISH counts once; observe and rejected actions do not count.'},'asset_catalog':deepcopy(self.case.get('asset_catalog',[])),'resources':deepcopy(list(self.resources.values()))}
 def apply(self,action):
  if self.done or self.time>=self.case['deadline']:raise ValueError('Session ended or deadline reached')
  if self.calls>=self.case['budget']['calls']:raise ValueError('Call budget exhausted')
  a=deepcopy(action);op=a.get('action'); before=self.time;self.reveal()
  if op not in ('WAIT','FINISH') and self.time+1>self.case['deadline']:raise ValueError('Action would exceed deadline')
  if op=='WAIT':
   t=a.get('until');
   if type(t) is not int or t<=self.time or t>self.case['deadline']:raise ValueError('WAIT must advance within service window')
   self.time=t;result={'waited_until':t}
  elif op=='FINISH':
   self.handoff=a.get('text','');self.handoff_time=before;self.time=self.case['deadline'];self.done=True;result={'closed':True,'remaining_obligations_cancelled':False}
  elif op=='READ':
   ids=a.get('ids',[])
   if not ids or any(i not in self.resources for i in ids):raise ValueError('Unknown resource')
   result={'resources':[deepcopy(self.resources[i]) for i in ids]};self.time+=1
  elif op in ('WRITE','SET','REPLY'):
   target=a.get('target');r=self.resources.get(target)
   if r is None:raise ValueError('Target unavailable')
   if op in ('WRITE','SET') and not r.get('editable'):raise ValueError('Target is not owned editable content')
   if op=='SET':
    fields=a.get('fields'); schema=r.get('field_schema',{})
    if not isinstance(fields,dict) or not fields or any(k not in schema or v not in schema[k] for k,v in fields.items()):raise ValueError('Fields outside visible schema')
    r.setdefault('fields',{}).update(fields);result={'updated':target}
   elif op=='WRITE':
    if not isinstance(a.get('text'),str):raise ValueError('Text required')
    if a.get('status',r.get('status','published')) not in ('draft','published','withdrawn'):raise ValueError('Invalid publication status')
    assets=a.get('assets',r.get('assets',[]))
    if not isinstance(assets,list) or any(x not in self.case.get('asset_catalog',[]) for x in assets):raise ValueError('Unknown asset')
    r['text']=a['text'];r['status']=a.get('status',r.get('status','published'));r['assets']=assets;result={'updated':target}
   else:
    if r['kind'] not in ('comment','dm','reply'):raise ValueError('REPLY requires conversation object')
    if not isinstance(a.get('text'),str):raise ValueError('Text required')
    rid=a.get('id',f"reply-{self.calls+1}")
    if rid in self.resources:raise ValueError('Reply id already exists')
    self.resources[rid]={'id':rid,'kind':'reply','text':a['text'],'channel':r['channel'],'recipient':r.get('recipient',r.get('author','creator')),'parent':target,'editable':True,'author':'creator','created_at':self.time+1};result={'delivered':rid,'channel':r['channel'],'recipient':r.get('recipient',r.get('author','creator'))}
   self.time+=1
   for e in self.case.get('action_events',[]):
    if e['id'] in self.fired or any(x['id']==e['id'] for x in self.pending):continue
    if op==e['trigger']['action'] and target==e['trigger']['target']:
     p=deepcopy(e);p['at']=self.time+e['delay'];self.pending.append(p)
  else:raise ValueError('Unknown action')
  self.calls+=1;self.reveal();
  if self.time>=self.case['deadline']:self.done=True
  self.history.append({'step':self.calls,'time_before':before,'time':self.time,'action':a,'result':deepcopy(result),'snapshot':deepcopy(self.resources)});return result
 def record(self):return {'protocol':PROTOCOL,'episode_id':self.case['id'],'time':self.time,'done':self.done,'handoff':self.handoff,'handoff_time':self.handoff_time,'history':deepcopy(self.history),'events':deepcopy(self.events),'final_state':deepcopy(self.resources)}
def run(case,actions):
 w=World(case)
 for a in actions:w.observe();w.apply(a)
 return w.record()
def replay(case,record):
 out=run(case,[s['action'] for s in record['history']])
 if out!=record:raise ValueError('Replay mismatch')
 return out
if __name__=='__main__':
 import argparse,pathlib
 p=argparse.ArgumentParser();p.add_argument('--world',required=True);p.add_argument('--actions');p.add_argument('--replay');p.add_argument('--output',required=True);a=p.parse_args();case=json.load(open(a.world))
 result=replay(case,json.load(open(a.replay)).get('simulation',json.load(open(a.replay)))) if a.replay else run(case,json.load(open(a.actions)))
 pathlib.Path(a.output).parent.mkdir(parents=True,exist_ok=True);pathlib.Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'steps':len(result['history']),'time':result['time'],'done':result['done']}))
