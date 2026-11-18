"""Data-driven local provider transactions; case-specific facts and duties stay in specs."""
from common import *

def term_card(value,keys):
 parts=value.split('/') if isinstance(value,str) else list(value)
 if len(parts)!=len(keys):raise ValueError('Author card field mismatch: '+repr((value,keys)))
 numbers={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'twelve':12}
 return {key:((int(part) if str(part).isdigit() else numbers.get(part,part)) if key in ('count','quantity','duration_seconds','home_a_count','home_b_count','amount','fare') else part) for key,part in zip(keys,parts)}
def card_schema(card):
 return {key:({'type':'integer','minimum':0,'maximum':1000} if type(value)is int else {'type':'string'}) for key,value in card.items()}

def workflow(spec,branch):
 sid=spec['sid'];b=deepcopy(spec[branch])
 for op in spec['ops']:
  keys=op.get('keys',['selection'])
  b['values'][op['field']]=term_card(b['values'][op['field']],keys)
 for c in spec.get('contacts',[]):b['requests'][c['id']]=term_card(b['requests'][c['id']],c.get('keys',['proposal']))
 x=begin(sid,spec['title'],spec['task'],spec['clock'],spec.get('deadline',180))
 sources=spec['sources'];contacts=spec.get('contacts',[])
 for key,title,body in sources:
  rs=[txt(key+'-record',body)]
  for source,eid,author,parent,text in spec.get('extra_comments',[]):
   if source==key:rs.append(comment(eid,text,author,parent,reply_to=parent,group_id='community',group_name='Community conversation'))
  for source,eid,text in spec.get('extra_posts',[]):
   if source==key:rs.append(post(eid,text,linked_resource='main',purpose='accessibility-transcript'))
  for source,eid,person,text in spec.get('extra_threads',[]):
   if source==key:rs.append(dm(eid,text,person))
  for c in contacts:
   if c['source']==key:
    rs.append(dm(c['id'],c['initial'],c['person'],topics=['arrange'],request_schema=card_schema(b['requests'][c['id']])))
  x.source(key,title,*rs)
 for key,at in spec.get('delayed_sources',{}).items():
  source=x.find(key+'-record');actual=source['text'];source['text']=T('The current provider update has not arrived yet. Its actual message will appear here when received.|当前供应方更新还没到，收到后实际消息会出现在这里。')
  x.c['events'].append({'id':'update-'+key,'at':at,'patch':{key+'-record':{'text':actual,'received_at':at}}})
 for key,operation in spec.get('reveal_after',{}).items():
  source=x.find(key+'-record');actual=source['text'];source['text']=T('The visible index links the named local test. Open its actual test result after requesting it; the result is not known yet.|这个可见索引关联指定本地测试，申请后查看真实测试结果，目前还未知。')
  x.c['action_events'].append({'id':'test-'+key,'trigger':{'action':'OPERATE','target':'services','choice':operation},'delay':0,'patch':{key+'-record':{'text':actual}}})
 x.source('history','Our actual public post and earlier reply|我方实际公开帖与旧回复',post('main',spec['oldpost']),thread('reader',spec['reader'],'Reader'),old('old-answer',spec['oldanswer'],'reader'))
 if spec.get('old_parent'):
  x.find('old-answer').update(parent=spec['old_parent'],reply_to=spec['old_parent'])
 if spec.get('initial_assets'):
  x.find('main')['assets']=spec['initial_assets'];x.c['asset_catalog']=spec.get('asset_catalog',spec['initial_assets'])
 init={op['field']:None for op in spec['ops']}
 init.update({c['id']+'_accepted':False for c in contacts})
 x.c['resources'].append(field('work','Actual provider transactions and artifact custody|供应方实际事务与资料保管',init))
 for c in contacts:
  plan=b['requests'][c['id']]
  x.answer(c['id'],'arrange',b.get('answer_overrides',{}).get(c['id'],c['answer']),delay=c.get('delay',1),set={'work':{c['id']+'_accepted':True}},rid=c['id']+'-accepted')
 for cid,required in spec.get('contact_after',{}).items():
  x.c['answers'][cid+'/arrange']['request_checks']=[{'kind':'state_condition','condition':{'revealed':[field+'-artifact' for field in required]}}]
 choices={}
 for op in spec['ops']:
  fieldname=op['field'];correct=b['values'][fieldname]
  values=None # No configuration-dependent answer enum is exposed.
  req={'fields':{'work':{k:v for k,v in op.get('requires',{}).items()}}}
  for c in op.get('accepted',[]):
   if c not in spec.get('standing_authorized',[]):req['fields']['work'][c+'_accepted']=True
  if op.get('once') or op['key'].startswith(('refund','pay')):req['fields']['work'][fieldname]=None
  if op.get('not_before') is not None:req['time']={'minimum':op['not_before']}
  if op.get('after'):
   # Real previous transaction must exist; no prescribed semantic value is
   # enforced here. A wrong authorized selection can remain executable and
   # must still fail its substantive criterion.
   req.setdefault('not',[])
   req.pop('not',None)
   req['all']=[{'not':{'fields':{'work':{f:None}}}} for f in op['after']]
  opts=dict(description=op['label'],schema=card_schema(correct),requires=req,parameter_record={'resource':'work','field':fieldname})
  opts['artifact_output']={'id':fieldname+'-artifact','inputs':[f+'-artifact' for f in op.get('after',[])]+[c if c in spec.get('standing_authorized',[]) else c+'-accepted' for c in op.get('accepted',[])],'mode':op.get('mode','service_transaction')}
  if op.get('param_variants'):opts['param_variants']=op['param_variants']
  if op.get('asset_patch'):opts['asset_patch']=op['asset_patch']
  if op.get('provider_fields'):opts['artifact_output']['provider_fields']=op['provider_fields']
  if op.get('conditional_result'):opts['artifact_output']['conditional_result']=op['conditional_result']
  if op.get('extra_inputs'):opts['artifact_output']['inputs']+=op['extra_inputs']
  if op.get('input_choices'):opts['artifact_output']['input_choices']=op['input_choices']
  if op.get('provider_result'):opts['artifact_output']['provider_result']=op['provider_result']
  if op.get('provider_checks'):opts['artifact_output']['provider_checks']=op['provider_checks']
  if op.get('snapshot_from'):
   opts['copy']=[{'from':op['snapshot_from'],'to':op['snapshot_to'],'attributes':['fields']}]
  choices[op['key']]=option(**opts)
 x.service('services','Actual provider service desk|实际供应方业务台','services',spec['service_note'],choices)
 for completion in spec.get('completion_events',[]):
  rid=completion['id'];x.c['resources'].append(field(rid,completion['title'],{'delivered':False}))
  x.c['action_events'].append({'id':'completion-'+rid,'trigger':{'action':'OPERATE','target':'services','choice':completion['operation']},'delay':completion['delay'],'copy':[{'from':completion['from_field']+'-artifact','to':rid,'attributes':['fields']}],'post_set':{rid:{'delivered':True}},'requires':completion.get('requires',{}),**({'duration_from_bound':completion['duration_from_bound']} if completion.get('duration_from_bound') else {})})
 g1=goal(x,spec['goal1_label'],b['goal1'],[s[0]+'-record' for s in sources]+['work'])
 g2=goal(x,spec['goal2_label'],spec['goal2'],['main','old-answer','reader']+[c['id'] for c in contacts]+['work'])
 ordered_ops=spec['ops']
 if b.get('operation_order'):
  bykey={o['key']:o for o in spec['ops']};ordered_ops=[bykey[k] for k in b['operation_order']]
 a=[lookup(k) for k,_,_ in sources]+[lookup('history'),lookup('services')]
 for op in spec['ops']:
  if op['key'] in spec.get('pre_contact_ops',[]):a.append(operate('services',op['key'],**b['values'][op['field']]))
 if spec.get('wait_before_contacts') is not None:a.append(wait(spec['wait_before_contacts']))
 initial_contacts=[c for c in contacts if c['id'] not in spec.get('skip_asks',[]) and c['id'] not in spec.get('contact_after',{})]
 for c in initial_contacts:a.append(ask(c['id'],'arrange',b['asks'][c['id']],**b['requests'][c['id']]))
 if initial_contacts:a.append({'action':'WAIT_FOR_IDS','ids':[c['id']+'-accepted' for c in initial_contacts],'until':spec.get('deadline',180)-30})
 late_contacts=set()
 for op in ordered_ops:
  if op['key'] in spec.get('pre_contact_ops',[]) or op['key'] in spec.get('post_completion_ops',[]):continue
  for cid in op.get('accepted',[]):
   if cid in spec.get('contact_after',{}) and cid not in late_contacts:
    contact=next(c for c in contacts if c['id']==cid);a.append(ask(cid,'arrange',b['asks'][cid],**b['requests'][cid]));a.append({'action':'WAIT_FOR_IDS','ids':[cid+'-accepted'],'until':spec.get('deadline',180)-1});late_contacts.add(cid)
  plan_time=op.get('plan_not_before',op.get('not_before'))
  if plan_time is not None:a.append(wait(plan_time-1))
  a.append(operate('services',op['key'],**b['values'][op['field']]))
 for completion in spec.get('completion_events',[]):a.append({'action':'WAIT_FOR_FIELDS','condition':{'fields':{completion['id']:{'delivered':True}}},'until':spec.get('deadline',180)-1})
 for op in ordered_ops:
  if op['key'] in spec.get('post_completion_ops',[]):a.append(operate('services',op['key'],**b['values'][op['field']]))
 for target,text in b['deliveries']:a.append(write(target,text) if target in ['main','old-answer']+[eid for _,eid,_ in spec.get('extra_posts',[])] else reply(target,text))
 a.append(finish(b['handoff']))
 near=[operate('services',z['choice'],**term_card(b['wrong'],next(o for o in spec['ops'] if o['key']==z['choice']).get('keys',['selection']))) if z['action']=='OPERATE' and next(o for o in spec['ops'] if o['key']==z['choice'])['field']==spec['critical_field'] else deepcopy(z) for z in a]
 if spec.get('negative_skips_completion'):
  near=omit(near,lambda z:z['action']=='WAIT_FOR_FIELDS' or z['action']=='OPERATE' and z.get('choice') in spec.get('post_completion_ops',[]))
 wrong=swap(a,'main',write('main',spec['wrong_public']),'WRITE')
 if spec.get('wrong_before_completion'):
  statement=next(z for z in wrong if z.get('target')=='main' and z['action']=='WRITE');wrong.remove(statement)
  first_wait=next(i for i,z in enumerate(wrong) if z['action']=='WAIT_FOR_FIELDS');wrong.insert(first_wait,statement)
 alt=deepcopy(a)
 for fieldname,value in b.get('alternative_values',{}).items():
  operation=next(o for o in spec['ops'] if o['field']==fieldname)
  alt=[operate('services',operation['key'],**term_card(value,operation.get('keys',['selection']))) if z['action']=='OPERATE' and z.get('choice')==operation['key'] else z for z in alt]
 if not b.get('alternative_values'):
  locations=[i for i,z in enumerate(alt) if z['action']=='OPERATE']
  bykey={o['key']:o for o in spec['ops']}
  for left,right in zip(locations,locations[1:]):
   one,two=bykey[alt[left]['choice']],bykey[alt[right]['choice']]
   if right==left+1 and one['field'] not in two.get('after',[]) and two['field'] not in one.get('after',[]) and not one.get('not_before') and not two.get('not_before'):
    alt[left],alt[right]=alt[right],alt[left];break
 if b.get('alternative_actions_transform'):alt=b['alternative_actions_transform'](alt)
 if b.get('alternative_public'):alt=swap(alt,'main',write('main',b['alternative_public']),'WRITE')
 result=plans(x,a,near,g1,wrong,g2,alt)
 if b.get('omit_strong_ops'):
  result['plans']['strong_simplification']['actions']=omit(a,lambda z:z['action']=='OPERATE' and z.get('choice') in b['omit_strong_ops'])
 if spec.get('standing_authorized'):
  omit_contacts=set(spec['standing_authorized'])
  reduced=[]
  for action in result['plans']['strong_simplification']['actions']:
   if action['action']=='ASK' and action.get('target') in omit_contacts:continue
   if action['action']=='WAIT_FOR_IDS':
    action=deepcopy(action);action['ids']=[i for i in action['ids'] if i.removesuffix('-accepted') not in omit_contacts]
    if not action['ids']:continue
   reduced.append(action)
  result['plans']['strong_simplification']['actions']=reduced
 if spec.get('optional_delivery_targets'):
  result['plans']['strong_simplification']['actions']=omit(result['plans']['strong_simplification']['actions'],lambda z:z['action']=='REPLY' and z.get('target') in spec['optional_delivery_targets'])
 if b.get('strong_actions_transform'):result['plans']['strong_simplification']['actions']=b['strong_actions_transform'](result['plans']['strong_simplification']['actions'])
 if b.get('clear_photo_in_strong'):
  for action in result['plans']['strong_simplification']['actions']:
   if action['action']=='WRITE' and action.get('target')=='main':action['assets']=[]
 result['changed_fact']=T(spec['changed_fact'])
 result['audit_expectations']={'goals':{'G1':{'fields':{'work':b['values']}},'G2':{'messages':{target:True for target,_ in b['deliveries'] if target not in spec.get('optional_delivery_targets',[])}}},'critical_field':spec['critical_field'],'actual_private_reason':spec.get('private_reason'),'case_specific_judgments':{'G1':T(b['goal1']),'G2':T(spec['goal2'])},'forbidden_public':spec.get('forbidden_public',[]),'wrong_public':T(spec['wrong_public']),'wrong_public_reason':T(spec.get('wrong_public_reason','The actual public statement contradicts this case’s concrete delivery scope or source status.|这条实际公开说法违背本题具体交付范围或来源状态。')),'optional_fields':b.get('optional_fields',[]),'legal_choices':{f:[term_card(v,next(o for o in spec['ops'] if o['field']==f).get('keys',['selection'])) for v in vals] for f,vals in b.get('legal_choices',{}).items()},'artifact_dependencies':{op['field']:[f for f in op.get('after',[])] for op in spec['ops']}}
 if sid=='t3-04':
  result['behavior_change']=T('The boardwalk outward option is available only in A. Keeping the already paid boat/S route is legal in both worlds, including the paid return boat; no forced behaviour difference is required. Changing to north activates direct interception and landing updates.|仅A可选去程栈道；两组都可保留已付船和S码头，也可保留回程船，不强迫行为不同。改去北面才触发直接截流和相关落点更新。')
  result['common_legal_strategy']=T('Keep O4 and R4, the existing south guide and luggage jobs, issue matching passes/receiver details and correct the public directional notice without unnecessary cancellations or repeated permissions.|保O4和R4、既有南面导游及行李任务，发匹配通行凭据和接收信息，改清公开方向通知，不做无必要退订和重复许可。')
 result['translations']=deepcopy(ZH);return result

def provider(id,person,source,initial,answer):return dict(id=id,person=person,source=source,initial=initial,answer=answer)
def job(key,field,label,*after,accepted=(),choices=()):return dict(key=key,field=field,label=label,after=list(after),accepted=list(accepted),choices=list(choices))
