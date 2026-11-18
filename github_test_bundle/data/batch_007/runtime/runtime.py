"""Deterministic local social workbench; no text matching or semantic scoring."""
from copy import deepcopy
import hashlib,json
PROTOCOL='redact-b007-structure-v1'
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
class World:
 def __init__(self,case):
  self.case=deepcopy(case);self.datasets=deepcopy(case.get('datasets',{}));self.resources={r['id']:deepcopy(r) for r in case['resources']};self.reserved=set(self.resources)
  def reserve(x):
   if isinstance(x,dict):
    if 'id' in x:self.reserved.add(x['id'])
    for v in x.values():reserve(v)
   elif isinstance(x,list):
    for v in x:reserve(v)
  reserve(case);self.reserved.update(['vote-tally','aggregate-respondents','aggregate-selections'])
  self.revealed=set(self.resources);self.time=0;self.calls=0;self.done=False;self.history=[];self.events=[];self.fired=set();self.pending=[];self.asked=set();self.handoff='';self.handoff_time=None
 def matches(self,c):
  return all(i in self.revealed for i in c.get('revealed',[])) and all(self.resources.get(r,{}).get('fields',{}).get(k)==v for r,fs in c.get('fields',{}).items() for k,v in fs.items()) and all(i not in self.resources for i in c.get('absent',[]))
 def reveal(self):
  for e in self.case.get('events',[])+self.pending:
   if e['id'] in self.fired or e.get('at',99999)>self.time or not self.matches(e.get('when',{})): continue
   self.fired.add(e['id'])
   for key,indices in e.get('remove_rows',{}).items():self.datasets[key]=[row for i,row in enumerate(self.datasets[key]) if i not in indices]
   payload=e.get('add',[])
   for variant in e.get('variants',[]):
    if self.matches(variant.get('when',{})):
     payload=variant['add'];break
   for r in payload:
    self.resources[r['id']]=deepcopy(r);self.revealed.add(r['id'])
   for rid,fs in e.get('set',{}).items():self.resources[rid].setdefault('fields',{}).update(fs)
   self.events.append({'event_id':e['id'],'time':self.time,'scheduled_at':e['at'],'added':[r['id'] for r in payload]})
 def observe(self):
  self.reveal()
  return dict(episode_id=self.case['id'],version=self.case['version'],protocol=PROTOCOL,time=self.time,deadline=self.case['deadline'],done=self.done,task=self.case['task'],authorization=self.case['authorization'],tool_protocol=self.case['tool_protocol'],budget=dict(calls=self.case['budget']['calls'],used=self.calls,remaining=self.case['budget']['calls']-self.calls),asset_catalog=self.case.get('asset_catalog',[]),resources=deepcopy(list(self.resources.values())))
 def apply(self,a):
  a=deepcopy(a);op=a.get('action');before=self.time
  if self.done or self.time>=self.case['deadline']:raise ValueError('Session ended')
  if self.calls>=self.case['budget']['calls']:raise ValueError('Budget exhausted')
  if op=='WAIT':
   t=a.get('until')
   if type(t) is not int or not self.time<t<=self.case['deadline']:raise ValueError('Invalid wait')
   wake=[e['at'] for e in self.case.get('events',[])+self.pending if e['id'] not in self.fired and self.time<e.get('at',99999)<=t and self.matches(e.get('when',{}))]
   self.time=min([t]+wake);result={'requested_until':t,'waited_until':self.time,'woke_for_event':self.time<t}
  elif op=='FINISH':
   if not isinstance(a.get('text'),str):raise ValueError('Private handoff text required')
   self.handoff=a['text'];self.handoff_time=self.time;self.time=self.case['deadline'];self.done=True;result={'closed':True,'obligations_cancelled':False}
  elif op=='READ':
   ids=a.get('ids')
   if not isinstance(ids,list) or not ids or any(i not in self.resources for i in ids):raise ValueError('Unavailable resource')
   result={'resources':[deepcopy(self.resources[i]) for i in ids]};self.time+=1
  elif op=='LOOKUP':
   directory=self.resources.get(a.get('target'),{});entry=a.get('entry')
   if entry not in [x['key'] for x in directory.get('entries',[])]:raise ValueError('Entry is not in a visible directory')
   key=directory['id']+'/'+entry;found=self.case.get('lookups',{}).get(key)
   if found is None:raise ValueError('Directory configuration missing')
   for r in found:
    if r['id'] not in self.resources:self.resources[r['id']]=deepcopy(r)
    self.revealed.add(r['id'])
   result={'resources':[deepcopy(self.resources[r['id']]) for r in found]};self.time+=1
  elif op in ('TABULATE','TALLY'):
   r=self.resources.get(a.get('target'),{})
   if r.get('operation')!=op or any(i not in self.revealed for i in r.get('requires',[])):raise ValueError('Service or required evidence unavailable')
   if op=='TABULATE':
    basis=a.get('basis')
    if basis not in ('respondents','selections'):raise ValueError('Unknown aggregate basis')
    rows=self.datasets[r['dataset']];counts={k:sum(k in row for row in rows) for k in sorted({k for row in rows for k in row})};total=sum(counts.values());denom=len(rows) if basis=='respondents' else total
    result=dict(basis=basis,respondents=len(rows),selections=total,counts=counts,percentages={k:round(v/denom*100,3) for k,v in counts.items()},denominator=denom)
    rid='aggregate-'+basis
   else:
    ballots=[b for b in self.case.get('ballots',[]) if b['valid']];counts={k:sum(b['choice']==k for b in ballots) for k in ('compact','large','abstain')};winner='compact' if counts['compact']>=counts['large'] else 'large';result=dict(present=len(ballots),quorum=len(ballots)>=3,choices=counts,adopted=winner,scope='Signed ballots; abstention counts for presence only. This grants no hosting authority.');rid='vote-tally'
   self.resources[rid]=dict(id=rid,kind='evidence',channel='private',editable=False,text=json.dumps(result,sort_keys=True),facts=deepcopy(result));self.revealed.add(rid);self.time+=1
  elif op=='ASK':
   r=self.resources.get(a.get('target'),{});topic=a.get('topic');key=r.get('id','')+'/'+str(topic)
   if topic not in r.get('topics',[]):raise ValueError('Topic not listed on visible contact')
   if not isinstance(a.get('text'),str) or not a['text'].strip():raise ValueError('Question text required')
   if key in self.asked:raise ValueError('This topic already has a pending or completed request')
   self.asked.add(key);self.time+=1
   answer=self.case.get('answers',{}).get(key)
   if answer:
    p=deepcopy(answer);p['id']='answer-'+key;p['at']=self.time+p.pop('delay',0);self.pending.append(p)
   result={'request_sent':key,'channel':'private','recipient':r.get('recipient'),'reply_guaranteed':False}
  elif op in ('WRITE','SET','REPLY','SEND_LINK'):
   rid=a.get('target');r=self.resources.get(rid)
   if r is None:raise ValueError('Unavailable target')
   if op in ('WRITE','SET') and not r.get('editable'):raise ValueError('Not owned editable content')
   if op=='SET':
    fs=a.get('fields');schema=r.get('field_schema',{})
    if not isinstance(fs,dict) or not fs or any(k not in schema or v not in schema[k] for k,v in fs.items()):raise ValueError('Fields outside visible schema')
    merged=dict(r.get('fields',{}),**fs)
    for guard in r.get('guards',[]):
     if any(k in fs for k in guard['setting']) and all(merged.get(k)==v for k,v in guard['setting'].items()) and not self.matches(guard['requires']):raise ValueError(guard['message'])
    r.setdefault('fields',{}).update(fs);result={'updated':rid,'fields':deepcopy(r['fields'])}
   elif op=='WRITE':
    if not isinstance(a.get('text'),str):raise ValueError('Text required')
    if a.get('status',r.get('status','published')) not in ('draft','published','withdrawn'):raise ValueError('Invalid status')
    assets=a.get('assets',r.get('assets',[]))
    if not isinstance(assets,list) or any(i not in self.case.get('asset_catalog',[]) for i in assets):raise ValueError('Unknown asset')
    r.update(text=a['text'],status=a.get('status',r.get('status','published')),assets=assets);result={'updated':rid}
   else:
    if op=='SEND_LINK':
     linked=self.resources.get(a.get('resource'))
     if linked is None or linked.get('channel')!='public' or linked.get('status','published')!='published':raise ValueError('SEND_LINK requires an available published public resource')
    if r['kind'] not in ('comment','dm','reply'):raise ValueError('Conversation target required')
    if not isinstance(a.get('text'),str):raise ValueError('Text required')
    newid=a.get('id',f'reply-{self.calls+1}')
    if newid in self.resources or newid in self.reserved:raise ValueError('Duplicate or reserved environment ID')
    self.resources[newid]=dict(id=newid,kind='reply',channel=r['channel'],recipient=r.get('recipient',r.get('author')),author='creator',parent=rid,editable=True,text=a['text'],created_at=self.time+1)
    if op=='SEND_LINK':self.resources[newid]['linked_resource']=a['resource']
    result={'delivered':newid,'channel':r['channel'],'recipient':self.resources[newid]['recipient']}
    if op=='SEND_LINK':result['linked_resource']=a['resource']
   self.time+=1
  else:raise ValueError('Unknown action')
  self.calls+=1
  for e in self.case.get('action_events',[]):
   tr=e['trigger']
   if e['id'] in self.fired or any(x['id']==e['id'] for x in self.pending):continue
   fields=tr.get('fields',{})
   ordinary=all(a.get(k)==v for k,v in tr.items() if k!='fields')
   field_match=not fields or (op=='SET' and any(k in a.get('fields',{}) for k in fields) and all(self.resources.get(a.get('target'),{}).get('fields',{}).get(k)==v for k,v in fields.items()))
   if ordinary and field_match and self.matches(e.get('requires',{})):
    p=deepcopy(e);p['at']=self.time+e.get('delay',0);self.pending.append(p)
  self.reveal()
  if self.time>=self.case['deadline']:self.done=True
  self.history.append(dict(step=self.calls,time_before=before,time=self.time,action=a,result=deepcopy(result),snapshot=deepcopy(self.resources)))
  return result
 def record(self):return dict(protocol=PROTOCOL,episode_id=self.case['id'],time=self.time,done=self.done,handoff=self.handoff,handoff_time=self.handoff_time,history=deepcopy(self.history),events=deepcopy(self.events),final_state=deepcopy(self.resources))
def run(case,actions):
 w=World(case)
 for a in actions:w.apply(a)
 return w.record()
def replay(case,record):
 actual=run(case,[s['action'] for s in record['history']])
 if actual!=record:raise ValueError('Replay mismatch')
 return actual
if __name__=='__main__':
 import argparse,pathlib
 p=argparse.ArgumentParser();p.add_argument('--world',required=True);p.add_argument('--actions');p.add_argument('--replay');p.add_argument('--output',required=True);a=p.parse_args();c=json.load(open(a.world));record=json.load(open(a.replay)) if a.replay else None
 out=replay(c,record.get('simulation',record)) if record else run(c,json.load(open(a.actions)));pathlib.Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(steps=len(out['history']),done=out['done'])))
