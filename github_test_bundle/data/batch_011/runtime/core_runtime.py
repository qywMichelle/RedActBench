"""Deterministic fictional workbench. State receipts never score prose."""
from copy import deepcopy
import json,hashlib
PROTOCOL='redact-structure-v2-typed-fields-1'
def valid_field(value,schema):
 if isinstance(schema,list):return value in schema
 if not isinstance(schema,dict):return False
 typ=schema.get('type')
 if typ=='integer':return type(value) is int and schema.get('minimum',float('-inf'))<=value<=schema.get('maximum',float('inf'))
 if typ=='number':return type(value) in (int,float) and schema.get('minimum',float('-inf'))<=value<=schema.get('maximum',float('inf'))
 if typ=='string':return isinstance(value,str) and (not schema.get('enum') or value in schema['enum'])
 if typ=='array':return isinstance(value,list) and len(value)<=schema.get('maxItems',100) and all(valid_field(v,schema['items']) for v in value)
 if typ=='object':return isinstance(value,dict) and set(value)==set(schema['properties']) and all(valid_field(value[k],v) for k,v in schema['properties'].items())
 return False
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
class World:
 def __init__(self,case):
  self.case=deepcopy(case);self.resources={r['id']:deepcopy(r) for r in case['resources']};self.time=0;self.calls=0;self.done=False;self.history=[];self.events=[];self.fired=set();self.pending=[];self.asked=set();self.handoff='';self.handoff_time=None
  self.reserved=set(self.resources)
  def ids(x):
   if isinstance(x,dict):
    if 'id' in x:self.reserved.add(x['id'])
    assembly=x.get('assemble_from')
    if isinstance(assembly,dict) and isinstance(assembly.get('output'),str):self.reserved.add(assembly['output'])
    for v in x.values():ids(v)
   elif isinstance(x,list):
    for v in x:ids(v)
  ids(case)
 def matches(self,c):
  return all(i in self.resources for i in c.get('revealed',[])) and all(self.resources.get(r,{}).get('fields',{}).get(k)==v for r,fs in c.get('fields',{}).items() for k,v in fs.items()) and all(self.resources.get(r,{}).get(k)==v for r,fs in c.get('attributes',{}).items() for k,v in fs.items())
 def effect(self,e):
  for r in e.get('reveal',[]):
   if r['id'] not in self.resources:self.resources[r['id']]=deepcopy(r)
  for r in e.get('add',[]):
   self.resources[r['id']]=deepcopy(r)
  for rid,fs in e.get('set',{}).items():self.resources[rid].setdefault('fields',{}).update(deepcopy(fs))
  for rid,fs in e.get('patch',{}).items():self.resources[rid].update(deepcopy(fs))
  for cp in e.get('copy',[]):
   for key in cp['attributes']:
    if key in self.resources[cp['from']]:self.resources[cp['to']][key]=deepcopy(self.resources[cp['from']][key])
    else:self.resources[cp['to']].pop(key,None)
 def reveal(self):
  for e in self.case.get('events',[])+self.pending:
   if e['id'] in self.fired or e.get('at',10**9)>self.time or not self.matches(e.get('when',{})):continue
   self.fired.add(e['id']);payload=e
   for v in e.get('variants',[]):
    if self.matches(v.get('when',{})):payload=v;break
   self.effect(payload);self.events.append({'event_id':e['id'],'time':self.time,'scheduled_at':e['at'],'added':[r['id'] for r in payload.get('add',[])]})
 def pending_view(self):
  return [{'delivery_token':'pending-'+str(i+1),'due_at':e['at'],'status':'scheduled'} for i,e in enumerate(self.pending) if e['id'] not in self.fired]
 def observe(self):
  self.reveal();return dict(episode_id=self.case['id'],version=self.case['version'],protocol=PROTOCOL,time=self.time,deadline=self.case['deadline'],done=self.done,task=self.case['task'],authorization=self.case['authorization'],tool_protocol=self.case['tool_protocol'],budget={'calls':self.case['budget']['calls'],'used':self.calls,'remaining':self.case['budget']['calls']-self.calls},asset_catalog=self.case.get('asset_catalog',[]),pending_deliveries=self.pending_view(),resources=deepcopy(list(self.resources.values())))
 def apply(self,action):
  a=deepcopy(action);op=a.get('action');before=self.time
  if self.done or self.time>=self.case['deadline']:raise ValueError('Session ended')
  if self.calls>=self.case['budget']['calls']:raise ValueError('Budget exhausted')
  if op=='WAIT':
   t=a.get('until')
   if type(t)is not int or not self.time<t<=self.case['deadline']:raise ValueError('Invalid wait')
   wake=[e['at'] for e in self.case.get('events',[])+self.pending if e['id'] not in self.fired and self.time<e.get('at',10**9)<=t and self.matches(e.get('when',{}))];self.time=min([t]+wake);result={'requested_until':t,'waited_until':self.time}
  elif op=='FINISH':
   if not isinstance(a.get('text'),str) or not a['text'].strip():raise ValueError('Handoff text required')
   self.handoff=a['text'];self.handoff_time=self.time;self.done=True;result={'closed':True,'obligations_cancelled':False}
  elif op=='READ':
   ids=a.get('ids')
   if not isinstance(ids,list) or not ids or any(i not in self.resources for i in ids):raise ValueError('Unavailable resources')
   result={'resources':[deepcopy(self.resources[i]) for i in ids]};self.time+=1
  elif op=='LOOKUP':
   r=self.resources.get(a.get('target'),{});entry=a.get('entry')
   if entry not in [x['key'] for x in r.get('entries',[])]:raise ValueError('Entry not in visible directory')
   found=self.case.get('lookups',{}).get(r['id']+'/'+entry)
   if found is None:raise ValueError('Missing directory configuration')
   for x in found:
    if x['id'] not in self.resources:self.resources[x['id']]=deepcopy(x)
   result={'resources':[deepcopy(self.resources[x['id']]) for x in found]};self.time+=1
  elif op=='ASK':
   r=self.resources.get(a.get('target'),{});topic=a.get('topic');key=r.get('id','')+'/'+str(topic)
   if topic not in r.get('topics',[]):raise ValueError('Topic not listed')
   if not isinstance(a.get('text'),str) or not a['text'].strip():raise ValueError('Question required')
   if key in self.asked:raise ValueError('Request already sent')
   self.asked.add(key);self.time+=1;answer=self.case.get('answers',{}).get(key)
   if answer:
    e=deepcopy(answer);e.update(id='answer-'+key,at=self.time+answer.get('delay',0));self.pending.append(e)
   result={'request_sent':key,'channel':'private','recipient':r.get('recipient'),'reply_guaranteed':False}
  elif op=='OPERATE':
   r=self.resources.get(a.get('target'),{});choice=a.get('choice')
   if choice not in [x['key'] for x in r.get('options',[])]:raise ValueError('Operation choice not listed')
   spec=self.case['operations'][r['id']+'/'+choice]
   if not self.matches(spec.get('requires',{})):raise ValueError(spec.get('requirement_message','Required visible record unavailable'))
   eff=spec
   for v in spec.get('variants',[]):
    if self.matches(v.get('when',{})):eff=v;break
   if spec.get('calculator'):
    from calculators import calculate
    computed=calculate(spec['calculator'],self.resources,self.time+1)
    eff=deepcopy(eff);eff.update(computed.get('effect',{}));eff['facts']=computed.get('facts',{})
    for event in computed.get('events',[]):
     event=deepcopy(event);event['id']=event['id']+'-'+str(self.calls+1);self.pending.append(event)
   self.effect(eff);self.time+=1;result={'operation':r['id'],'choice':choice,'channel':r['channel'],'observed_resources':{i:deepcopy(self.resources[i]) for i in spec.get('inspect',[]) if i in self.resources},'facts':deepcopy(eff.get('facts',{}))}
   if spec.get('aggregate'):
    rows=self.case['datasets'][spec['aggregate']];mode=choice;before_values=[x['before'] for x in rows if x.get('before')is not None];after_values=[x['after'] for x in rows if x.get('after')is not None];pairs=[x for x in rows if x.get('before')is not None and x.get('after')is not None]
    result['facts']={'before_count':len(before_values),'before_mean':sum(before_values)/len(before_values),'after_count':len(after_values),'after_mean':sum(after_values)/len(after_values),'paired_count':len(pairs),'paired_before_mean':sum(x['before'] for x in pairs)/len(pairs),'paired_after_mean':sum(x['after'] for x in pairs)/len(pairs),'mode':mode}
   receipt='receipt-'+str(self.calls+1)
   while receipt in self.resources or receipt in self.reserved:receipt+='-op'
   self.resources[receipt]={'id':receipt,'kind':'receipt','channel':r['channel'],'editable':False,'text':'Local operation result. This records state and delivery only, not semantic completion.','result':deepcopy(result),'created_at':self.time};result['receipt_id']=receipt
  elif op in ('WRITE','SET','REPLY','SEND_LINK'):
   rid=a.get('target');r=self.resources.get(rid)
   if r is None:raise ValueError('Unavailable target')
   if op in ('WRITE','SET') and not r.get('editable'):raise ValueError('Not owned editable content')
   if op=='SET':
    fs=a.get('fields');schema=r.get('field_schema',{})
    if not isinstance(fs,dict) or not fs or any(k not in schema or not valid_field(v,schema[k]) for k,v in fs.items()):raise ValueError('Fields outside visible schema')
    r.setdefault('fields',{}).update(deepcopy(fs));result={'updated':rid,'fields':deepcopy(r['fields'])}
   elif op=='WRITE':
    if not isinstance(a.get('text'),str):raise ValueError('Text required')
    status=a.get('status',r.get('status','published'));assets=a.get('assets',r.get('assets',[]))
    if status not in ('draft','published','withdrawn'):raise ValueError('Invalid status')
    if not isinstance(assets,list) or any(i not in self.case.get('asset_catalog',[]) for i in assets):raise ValueError('Unknown asset')
    r.update(text=a['text'],status=status,assets=assets);result={'updated':rid}
   else:
    if r.get('kind') not in ('comment','dm','reply'):raise ValueError('Conversation target required')
    if not isinstance(a.get('text'),str):raise ValueError('Text required')
    if op=='SEND_LINK':
     linked=self.resources.get(a.get('resource'))
     if linked is None or linked.get('channel')!='public' or linked.get('status','published')!='published':raise ValueError('Link resource must be public and published')
    newid=a.get('id','reply-'+str(self.calls+1))
    if newid.startswith('sys-') or newid in self.resources or newid in self.reserved:raise ValueError('Duplicate/reserved ID')
    self.resources[newid]={'id':newid,'kind':'reply','channel':r['channel'],'recipient':r.get('recipient',r.get('author')),'author':'creator','parent':rid,'editable':True,'text':a['text'],'created_at':self.time+1}
    if op=='SEND_LINK':self.resources[newid]['linked_resource']=a['resource']
    result={'delivered':newid,'channel':r['channel'],'recipient':self.resources[newid]['recipient']}
   self.time+=1
  else:raise ValueError('Unknown action')
  self.calls+=1
  for e in self.case.get('action_events',[]):
   if e['id'] in self.fired or any(x['id']==e['id'] for x in self.pending):continue
   if all(a.get(k)==v for k,v in e['trigger'].items()) and self.matches(e.get('requires',{})):
    p=deepcopy(e);p['at']=self.time+e.get('delay',0);self.pending.append(p)
  self.reveal()
  if self.time>=self.case['deadline']:self.done=True
  result['pending_deliveries']=self.pending_view()
  self.history.append({'pending_deliveries':self.pending_view(),'step':self.calls,'time_before':before,'time':self.time,'action':a,'result':deepcopy(result),'snapshot':deepcopy(self.resources)})
  return result
 def record(self):return dict(protocol=PROTOCOL,episode_id=self.case['id'],time=self.time,done=self.done,handoff=self.handoff,handoff_time=self.handoff_time,history=deepcopy(self.history),events=deepcopy(self.events),final_state=deepcopy(self.resources),pending_events=[{'event_id':e['id'],'due_at':e['at'],'trigger':deepcopy(e.get('trigger',{}))} for e in self.pending if e['id'] not in self.fired])
def run(case,actions):
 w=World(case)
 for a in actions:w.apply(a)
 return w.record()
def replay(case,record):
 expected=record.get('simulation',record);actual=run(case,[s['action'] for s in expected['history']])
 if actual!=expected:raise ValueError('Replay mismatch')
 return actual
if __name__=='__main__':
 import argparse,pathlib
 p=argparse.ArgumentParser();p.add_argument('--world',required=True);p.add_argument('--actions');p.add_argument('--replay');p.add_argument('--output',required=True);a=p.parse_args();c=json.load(open(a.world));out=replay(c,json.load(open(a.replay))) if a.replay else run(c,json.load(open(a.actions)));pathlib.Path(a.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'steps':len(out['history']),'done':out['done']}))
