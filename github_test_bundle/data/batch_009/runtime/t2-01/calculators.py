"""Generic selected rental processing; facts and private state are per World."""
from copy import deepcopy
import json,re

def public_state(s):return {k:deepcopy(s[k]) for k in ['devices','bridge','licence','reservations','returned']}

def calculate(kind,resources,at,context):
 f=context['facts'];s=deepcopy(context['state']);add=[];schedule=[]
 def receipt(label,text,**facts):
  while True:
   s['receipt_serial']+=1;rid='rental-'+str(s['receipt_serial'])
   if rid not in resources and not any(r['id']==rid for r in add):break
  add.append(dict(id=rid,kind='receipt',channel='private',editable=False,created_at=at,text=text,service_kind=label,**facts));return rid
 def note(person,label,text):
  rid=receipt(label,text,recipient=person,delivery_mode='copy_on_send');add[-1]['kind']='delivered_file';add[-1]['version']=str(at);add[-1]['delivery_status']='delivered';add[-1]['delivered_at']=at;add[-1]['audience']=[person];add[-1].pop('delivery_mode',None);return rid
 def timer(when):
  if when<=at or when in s['scheduled'] or when in f['static_times']:return
  s['event_serial']+=1;eid='rental-process-'+str(s['event_serial'])
  while eid in resources:s['event_serial']+=1;eid='rental-process-'+str(s['event_serial'])
  s['scheduled'].append(when);schedule.append({'id':eid,'at':when,'calculator':'rental_process'})
 def function(unit,person,mode):
  if mode=='none':return True,'No new camera function requested; selected account/state actions only'
  d=s['devices'][unit];cap=f['units'][unit].get(mode,False)
  if not cap:return False,'The manufacturer card does not support requested '+mode+' on '+unit
  if cap=='requires R':
   ok=s['bridge']['attached']==unit and s['bridge']['owner']==person
   return ok,'The actual compatible personal bridge is '+('fitted' if ok else 'not fitted for this user')
  ok=d['session']==person and s['licence']['owner']==person and s['licence']['binding']==unit and s['bridge']['attached']!=unit
  return ok,'Actual own activation and free port '+('present' if ok else 'not both present')
 def close_session(unit,account,reason):
  if s['devices'][unit]['session']==account:
   s['devices'][unit]['session']='none';s['devices'][unit]['session_until']=0
   if s['licence']['binding']==unit:s['licence']['binding']='none'
   receipt('session_closed','Actual temporary device session closed; personal entitlement is retained by its owner.',unit=unit,account=account,reason=reason,entitlement_owner=s['licence']['owner'])
 def due(leg,use):
  row=f['legs'][leg]
  if leg=='L-indoor' and use['unit']!=f['legs']['L-night']['original_unit']:return row['return_if_substituted']
  return row['return_at']
 def return_body(leg,use):
  row=f['legs'][leg];unit=use['unit'];person=row['person'];d=s['devices'][unit]
  if d['holder']!=person:return
  d['holder']='provider';returned=[leg]
  if leg=='L-indoor' and unit==f['legs']['L-night']['original_unit'] and 'L-night' in s['uses']:returned.append('L-night')
  if leg=='L-night' and 'L-indoor' in s['uses'] and s['uses']['L-indoor']['unit']==unit:returned.append('L-indoor')
  final=person=='L' and at>=f['legs']['L-night']['return_at']
  if s['bridge']['attached']==unit:
   if final:s['bridge']['attached']='none';s['bridge']['holder']='L'
   else:s['bridge']['holder']='provider'
  for ref in returned:
   if ref not in s['returned']:s['returned'].append(ref)
   s['reservations'][ref]['status']='returned'
  receipt('body_return','Actual body returned. This physical receipt does not close a personal session; accessory custody is itemized separately.',legs=returned,unit=unit,from_person=person,session_owner=d['session'],bridge=deepcopy(s['bridge']))
 def client_ok(leg,unit,person):
  row=f['legs'][leg]
  if row['person']!=person:return False,'The selected recipient is not the actual already accepted customer'
  if unit!=row['original_unit'] and not row.get('compatible_substitute',False):return False,'The actual existing leg names its original unit and has no compatible-substitution agreement for that leg'
  ok,reason=function(unit,person,row['mode'])
  if not ok:return False,reason
  foreign=s['devices'][unit]['session'] not in ['none',person]
  return (not foreign),('Another client temporary session is still active' if foreign else 'Actual required function and personal-session boundary supported')
 def availability(cfg):
  unit=cfg['unit']
  if s['devices'][unit]['holder']!='provider':return False,'Unit is not physically at the provider'
  for leg in ['E-L','E-M']:
   r=s['reservations'][leg]
   if r['unit']==unit and r['status']=='confirmed' and at<f['legs'][leg]['return_at']:return False,'Existing early reservation still occupies this configuration'
  if cfg['accessory']=='R':
   attached=s['bridge']['attached']
   if s['bridge']['holder']!='provider' or attached!='none' and s['devices'][attached]['holder']!='provider':return False,'Personal bridge is not physically available to reconfigure'
  if cfg['account']=='M':
   old=s['licence']['binding']
   if old!='none' and old!=unit and s['devices'][old]['holder']!='provider':return False,'Current activated body has not actually returned'
  return True,'Physical prerequisites present'
 def commit(job):
  spec=job['spec'];trial=deepcopy(s['reservations'])
  for leg in spec['cancel_legs']:trial[leg]['status']='cancelled'
  for cfg in spec['prepare']:
   for leg in cfg['apply_legs']:trial[leg].update(unit=cfg['unit'],person=cfg['person'],requested_mode=cfg['mode'],return_at=cfg['return_at'],status='confirmed')
  active=[(leg,row) for leg,row in trial.items() if row['status']=='confirmed']
  for i,(a,x) in enumerate(active):
   for b,y in active[i+1:]:
    ca,cb=f['legs'][a],f['legs'][b]
    overlap=max(ca['reservation_from'],cb['reservation_from'])<min(ca['reservation_until'],cb['reservation_until'])
    if x['unit']==y['unit'] and x['person']!=y['person'] and overlap:return False,'One actual body has overlapping selected reservations for different people'
  s['reservations']=trial
  if not spec['cancel_legs'] and not any(cfg['apply_legs'] for cfg in spec['prepare']):return True,'No reservation changes selected; actual state/account handling only'
  receipt('registry_commit','Actual selected registry amendments posted atomically. This does not amend immutable customer agreement scope.',job=spec['key'],cancelled_legs=spec['cancel_legs'],selected_configs=spec['prepare'])
  for cfg in spec['prepare']:
   if not cfg['apply_legs']:continue
   foreign=s['devices'][cfg['unit']]['session'] not in ['none',cfg['person']]
   own_refs=[leg for leg in cfg['apply_legs'] if f['legs'][leg]['person']==cfg['person']]
   note(cfg['person'],'private_plan','Your actual selected provider plan: body '+cfg['unit']+', requested function '+cfg['mode']+', your own existing leg references '+json.dumps(own_refs)+'. Original accepted customer terms are separate. Other-client session present='+str(foreign)+'. No other client account details are delivered here.')
  return True,'Selected registry posted'
 def process():
  s['scheduled']=[t for t in s['scheduled'] if t>at]
  # End-of-use is processed before same-instant expiry; no false endpoint outage.
  for leg,use in s['uses'].items():
   row=f['legs'][leg]
   if not use.get('end_reported') and at>=row['use_end']:
    if use.get('gap_start') is not None:use['gaps'].append([use['gap_start'],row['use_end']]);use['gap_start']=None
    use['end_reported']=True
    receipt('use_end','Actual booked-use interval ended; actual availability is reported without a quality verdict.',leg=leg,unit=use['unit'],actual_start=use['at'],booked_start=row['start'],booked_end=row['use_end'],unavailable_intervals=use['gaps'])
  for unit,d in s['devices'].items():
   if d['session']!='none' and d['session_until'] and d['session_until']<=at:close_session(unit,d['session'],'actual selected expiry')
  for leg,use in list(s['uses'].items()):
   if leg not in s['returned'] and at>=due(leg,use):return_body(leg,use)
  changed=True
  while changed:
   changed=False
   for key,job in s['jobs'].items():
    spec=job['spec']
    if job['status']=='preparing' and job['ready_at']<=at:
     outcomes=[]
     for cfg in spec['prepare']:
      ok,reason=function(cfg['unit'],cfg['person'],cfg['mode']);outcomes.append({'unit':cfg['unit'],'requested_mode':cfg['mode'],'function_supported':ok,'raw_reason':reason,'session_owner':s['devices'][cfg['unit']]['session'],'bridge':deepcopy(s['bridge'])})
     job['outcomes']=outcomes
     if all(row['function_supported'] for row in outcomes):
      ok,reason=commit(job) if spec['commit'] else (True,'Preparation only; no registry amendment selected')
      job['status']='done' if ok else 'failed';job['reason']=reason
     else:job['status']='failed';job['reason']='A selected requested configuration is not supported by actual hardware/port/activation'
     receipt('preparation','Actual selected configuration processing finished. Function support is not proof of another old leg, consumer assent or cleared foreign session.',job=key,outcomes=outcomes,registry_result=job['reason']);changed=True
    if job['status']!='queued' or at<spec['earliest_at']:continue
    if not all(ref in s['returned'] for ref in spec['after_returns']):continue
    if not all(s['jobs'].get(ref,{}).get('status')=='done' for ref in spec['after_batches']):continue
    checks=[availability(cfg) for cfg in spec['prepare']]
    if not all(value[0] for value in checks):job['waiting_reason']=[value[1] for value in checks if not value[0]];continue
    permission=None
    for cfg in spec['prepare']:
     if cfg['accessory']=='R' and (cfg['person']!='L' or cfg['accessory_owner']!='L'):permission='Actual R handling authority is for its owner L use only'
     if cfg['account']=='M' and cfg['person']!='M':permission='M entitlement authorizes M own actual use only'
    if len([cfg for cfg in spec['prepare'] if cfg['accessory']=='R'])>1:permission='One physical R cannot occupy two selected bodies'
    if len([cfg for cfg in spec['prepare'] if cfg['account']=='M'])>1:permission='One actual activation cannot be on two selected bodies'
    if permission:
     job['status']='failed';job['reason']=permission;receipt('permission_result','Selected processing could not start under the actual personal resource scope.',job=key,raw_reason=permission);changed=True;continue
    for cfg in spec['prepare']:
     unit=cfg['unit'];d=s['devices'][unit]
     for account in cfg['clear_sessions']:close_session(unit,account,'explicit selected returned-device cleanup')
     if s['bridge']['attached']==unit and cfg['accessory']=='none':s['bridge']['attached']='none';s['bridge']['holder']='provider'
     if cfg['accessory']=='R':s['bridge']['attached']=unit;s['bridge']['holder']='provider'
     if cfg['account']=='M':
      old=s['licence']['binding']
      if old!='none' and old!=unit:close_session(old,'M','actual selected retarget')
      d['session']='M';d['session_until']=cfg['session_until'];s['licence']['binding']=unit
      if cfg['session_until']>at:timer(cfg['session_until'])
     if cfg['mode']!='none':d['ready_after']=at+f['policy']['preparation_minutes']
    job['status']='preparing';job['ready_at']=at+(f['policy']['preparation_minutes'] if any(cfg['mode']!='none' for cfg in spec['prepare']) else 0)
    if job['ready_at']>at:timer(job['ready_at'])
    changed=True
  # The actual accepted customer/window/function is independent of posted labels.
  for leg,row in sorted(f['legs'].items(),key=lambda item:item[1]['start']):
   if leg in s['uses'] or leg in s['closed_windows'] or at<row['start']:continue
   r=s['reservations'][leg]
   if at>row['start']+row['pickup_wait']:
    s['closed_windows'].append(leg);receipt('pickup_window','Actual accepted counter waiting window ended without a usable handover.',leg=leg);continue
   unit=r['unit'];person=r['person'];d=s['devices'][unit]
   if leg=='E-L' and r['status']=='confirmed' and person=='L' and unit==row['original_unit'] and s['bridge']['holder']=='L' and s['bridge']['attached']=='none':
    s['bridge']['attached']=unit;s['bridge']['holder']='provider';receipt('customer_accessory_intake','Actual L-owned R brought to the agreed early pickup and accepted for its authorized fitting; body issue is separate.',owner='L',accessory='R',attached=unit)
   ok,reason=client_ok(leg,unit,person)
   if r['status']=='confirmed' and d['holder'] in ['provider',person] and d['ready_after']<=at and ok:
    continuation=d['holder']==person;d['holder']=person
    if s['bridge']['attached']==unit:s['bridge']['holder']=person
    s['uses'][leg]={'unit':unit,'at':at,'gaps':[],'gap_start':None,'end_reported':False};r['status']='in_use'
    receipt('continuation' if continuation else 'handover','Actual accepted configured use '+('continued on the same held unit' if continuation else 'began with an actual body handover')+'.',leg=leg,person=person,unit=unit,required_function=row['mode'],bridge=deepcopy(s['bridge']),session_owner=d['session'])
   else:
    if leg not in s.get('wait_notices',[]):
     s.setdefault('wait_notices',[]).append(leg);note(row['person'],'actual_wait','Your accepted counter window has no actual usable handover yet. Current raw reason: '+reason+'. A selected registry row is not new consumer assent or a physical receipt.')
    timer(row['start']+row['pickup_wait']+1)
  for leg,use in s['uses'].items():
   if use.get('end_reported') or at>=f['legs'][leg]['use_end']:continue
   ok,_=client_ok(leg,use['unit'],f['legs'][leg]['person'])
   if not ok and use.get('gap_start') is None:use['gap_start']=at;receipt('function_unavailable','Actual required function/session boundary became unavailable during a booked use.',leg=leg,unit=use['unit'])
   elif ok and use.get('gap_start') is not None:use['gaps'].append([use['gap_start'],at]);use['gap_start']=None
 if kind=='rental_submit':
  draft=deepcopy(resources['programme_draft']['fields']);specs=draft['batches']
  for key in draft['cancel_requests']:
   if key not in s['jobs']:raise ValueError('Unknown submitted work reference')
   job=s['jobs'][key]
   if job['status']=='queued':job['status']='cancelled'
   elif job['status']=='preparing':job['spec']['commit']=False
   receipt('request_cancellation','Actual request cancellation affects only unstarted work or its unposted commit; completed physical work and old rentals are not erased.',job=key,actual_work_status=job['status'])
  keys=[row['key'] for row in specs]
  if len(set(keys))!=len(keys) or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,50}',key) for key in keys):raise ValueError('Programme job keys must be unique short identifiers')
  if any(key in s['jobs'] for key in keys):raise ValueError('Submitted job key already exists; use a new actual work identifier')
  for spec in specs:
   if type(spec['commit']) is not bool:raise ValueError('Commit must be a concrete Boolean')
   if not spec['prepare'] and not spec['cancel_legs']:raise ValueError('Empty work batch')
   if any(ref not in set(keys)|set(s['jobs']) for ref in spec['after_batches']):raise ValueError('Unknown selected predecessor job')
   s['jobs'][spec['key']]={'spec':spec,'status':'queued'}
   if spec['earliest_at']>at:timer(spec['earliest_at'])
  rid=receipt('request','Actual selected programme request stored. No future return, readiness, confirmation or agency approval is asserted.',selected_batches=specs)
  # Immediate private processing is still separate from request acknowledgment.
  if specs:
   s['event_serial']+=1;schedule.append({'id':'rental-process-'+str(s['event_serial']),'at':at,'calculator':'rental_process'})
  facts={'request_received':True,'request_receipt':rid,'selected_job_keys':keys}
 elif kind=='rental_process':process();facts={}
 else:raise ValueError('Unknown rental native operation')
 return {'facts':facts,'effect':{'native_state_replace':s,'native_schedule':schedule,'set':{'rental_actual':public_state(s)},'add':add}}
