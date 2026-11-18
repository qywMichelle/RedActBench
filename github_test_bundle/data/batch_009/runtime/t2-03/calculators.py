"""Execute actor-selected journal and freight work against per-World actual facts."""
from copy import deepcopy
import json,re

def calculate(kind,resources,at,context):
 f=context['facts'];s=deepcopy(context['state']);add=[];schedule=[]
 def receipt(label,text,**facts):
  while True:
   s['serial']+=1;rid=f['kind']+'-'+str(s['serial'])
   if rid not in resources and all(x['id']!=rid for x in add):break
  add.append(dict(id=rid,kind='receipt',channel='private',editable=False,created_at=at,text=text,service_kind=label,**facts));return rid
 def private(person,text,**facts):
  rid=receipt('private_plan',text,recipient=person,**facts);add[-1].update(kind='delivered_file',version=str(at),delivery_status='delivered',delivered_at=at,audience=[person]);return rid
 def timer(t):
  if t<=at or t in s['scheduled']:return
  s['scheduled'].append(t);schedule.append({'id':f['kind']+'-worker-'+str(t),'at':t,'calculator':'business_process'})
 def journal_process():
  c=f['contracts']
  if at>=c['desk_priority_U_until'] and s['U_desk_priority']=='active':
   s['U_desk_priority']='ended';s['W_desk_priority']='active'
   receipt('priority_transition','Actual original U purchase-priority window ended without a formed whole transaction. W existing conditional desk priority is now active; this does not release sample custody or either person money.',U_priority='ended',W_priority='active')
  if at>=c['sample_return'] and not s.get('sample_event_seen'):
   s['sample_event_seen']=True
   if f['actual_future']['sample_arrives']:
    s['sample_holder']='creator';s['sample_returned']=True;s['sample_condition']='good' if f['actual_future']['sample_good'] else 'not_accepted'
    receipt('sample_intake','Actual itemized desk-sample intake. This is physical receipt/condition evidence, not a completed refit, money release or final desk delivery.',part='desk_sample',holder=s['sample_holder'],condition=s['sample_condition'])
   else:receipt('sample_nonarrival','At the agreed return window no sample arrived. Last supported custody remains U; no refit or released-security result is established.',holder='U')
  for refund in s['refunds']:
   if refund['state']=='merchant_posted' and at>=refund['external_at']:
    refund['state']='externally_arrived';receipt('external_refund','Actual external refund arrival is now recorded, separately from the earlier merchant posting.',line=refund['line'],owner=refund['owner'],amount=refund['amount'])
  for key,job in s['jobs'].items():
   spec=job['spec']
   if job['status']!='queued' or at<spec['earliest_at']:continue
   if any(not s.get(flag,False) for flag in spec['requires']):continue
   if spec['refit'] and not s['sample_refitted']:
    if not s['sample_returned'] or s['sample_condition']!='good':continue
    if 'refit_started' not in job:
     job['refit_started']=at;job['refit_ready']=at+f['processing']['refit_minutes'];timer(job['refit_ready'])
     receipt('refit_started','Actual selected matching desk-sample refit started; it is not yet a ready desk.',job=key,ready_not_before=job['refit_ready']);continue
    if at<job['refit_ready']:continue
    s['sample_refitted']=True;receipt('sample_refit','Actual matching desk sample refitted and functional drawer/finish configuration restored. This changes no money owner or buyer title.',part='desk_sample',desk_ready=True)
   if spec['cancel_upgrade_queue']:
    s['pending_upgrade_queue']='cancelled';receipt('queue_cancelled','Actual queue cancellation posted. The upgrade was already captured; this queue result reverses no settled money.',settled_capture_reversed=0)
   trial=deepcopy(s['lines']);applied=s['chair_applied'];entries=[];blocked=None
   for entry in spec['entries']:
    line=trial[entry['line']];amount=entry['amount']
    if amount>line['remaining']:blocked='Selected amount exceeds current actual remaining line balance';break
    line['remaining']-=amount
    if entry['kind']=='offset':applied+=amount
    elif line['purpose']=='chair':applied-=amount
    entries.append(dict(entry,actual_source_owner=line['owner'],actual_source_purpose=line['purpose']))
   if blocked:
    job['status']='failed';receipt('journal_blocked','Actual selected atomic journal did not post any of its entries.',job=key,raw_reason=blocked);continue
   s['lines']=trial;s['chair_applied']=applied
   if entries:
    s['journal'].append({'at':at,'job':key,'entries':entries});receipt('journal_posted','Actual actor-selected journal entries posted atomically. This reports actual money movement, not owner permission or sale agreement.',job=key,entries=entries,chair_applied=applied)
   for entry in entries:
    if entry['kind']=='reverse' and entry['amount']:
     refund={'line':entry['line'],'owner':entry['actual_source_owner'],'amount':entry['amount'],'state':'merchant_posted','external_at':at+f['processing']['external_refund_delay']};s['refunds'].append(refund);timer(refund['external_at'])
   job['status']='done'
  if at>=c['W_inspection'] and s['W_inspection']=='not_yet':
   if s['W_desk_priority']=='active' and s['sample_refitted']:
    s['W_inspection']='completed';receipt('W_inspection','Actual W functional desk inspection completed under its existing priority. No desk purchase or money transfer is implied.');private('W','Your actual functional desk inspection is complete; your existing desk-priority/security remains your own. No other buyer financial details are delivered.')
   else:
    s['W_inspection']='limited';receipt('W_inspection','Actual W visit had only a limited inspection: matching sample/refit not established. Existing priority is preserved to its actual end.',desk_ready=s['sample_refitted']);private('W','Your actual inspection is limited because the matching desk configuration is not yet restored. Your existing priority remains through18:30; this is not a sale or a release of your own security.')
  if at>=c['chair']['pickup'] and s['chair_holder']=='creator' and not s.get('chair_visit_seen'):
   s['chair_visit_seen']=True
   if s['chair_applied']>=c['chair']['price']:
    s['chair_holder']='U';receipt('chair_handover','Actual original chair handed to U at the accepted18:00 visit. This receipt does not sell the desk or prove that a money source was authorized.',price=c['chair']['price'],actual_applied=s['chair_applied']);private('U','Your original chair90 was actually collected at18:00. The desk has not been sold to you by this receipt; your sample/money facts remain itemized in their actual records.')
   else:receipt('chair_pending','Actual original chair visit remains unsettled for the evidenced unpaid balance. The confirmed old order is not cancelled.',paid=s['chair_applied'],balance=c['chair']['price']-s['chair_applied'])
  if at>=c['desk_priority_W_until'] and s['W_desk_priority']=='active':
   s['W_desk_priority']='ended';receipt('priority_end','Actual W priority window ended. No W sale or automatic transfer of its30 security to another buyer occurred.')
 def lift_process():
  lf=f['lift'];lift=s['lift']
  moving=lift['moving']
  if moving and moving['ends']<=at:
   spec=moving['spec'];dest=lf['storage'] if spec['direction']=='up' else lf['ground']
   for part in spec['parts']:
    p=s['parts'][part];p['location']=dest
    if part=='V-frame' and dest==lf['storage']:
     p.update(holder='V',state='final');s['V_frame_visit']=True
    else:p.update(state='staged')
   lift['completed_moves'].append({'at':at,'parts':spec['parts'],'direction':spec['direction'],'owner':spec['owner']});s['lift_jobs'][moving['key']]['status']='done';lift['moving']=None
   receipt('lift_arrival','Actual freight-lift movement completed. Upstairs V-frame acceptance is final for that part; a desk top at the loading point is not carrier collection or final U delivery.',lift='L88',parts=spec['parts'],direction=spec['direction'],actual_parts={p:deepcopy(s['parts'][p]) for p in spec['parts']})
   if 'V-frame' in spec['parts'] and dest==lf['storage']:private('V','Your remaining chair frame has actually reached your third-floor storage and is finally received. Together with your old final seat receipt, the chair parts are complete. No desk purchase is created.')
  # Explicit actual predicates make a submitted whole programme lawful without
  # treating permission, a clock forecast or the selected job name as a receipt.
  for key,job in s['lift_jobs'].items():
   spec=job['spec']
   if job['status']!='queued' or at<spec['at']:continue
   if any(s['parts'][p]['state']!='final' for p in spec['after_final_parts']):continue
   if any(s['parts'][p]['location']!=lf['ground'] for p in spec['after_ground_parts']):continue
   if not lf['start_at']<=at<=lf['end_at'] or lift['status'] in ['cancelled','released','expired']:
    job['status']='blocked';receipt('lift_unavailable','Actual selected lift work cannot start outside the real reserved/retained slot.',job=key,actual_lift_status=lift['status']);continue
   if spec['kind']=='transfer':
    if spec['owner']!=lf['transfer_to'] or s['parts'][lf['transfer_requires_final_part']]['state']!='final':
     job['status']='blocked';receipt('lift_permission','The actual pre-authorized transfer condition has not been established; selected fields create no new V consent.',job=key,current_owner=lift['owner']);continue
    lift['owner']=spec['owner'];lift['status']='active';job['status']='done';receipt('lift_transfer','Actual remaining L88 time transferred under the existing owner authorization after real frame acceptance. Vehicle booking and either order are unchanged.',job=key,owner=lift['owner'],ends=lf['end_at']);continue
   if spec['kind']=='release':
    lift['status']='released';job['status']='done';receipt('lift_release','Actual selected remaining lift reservation released. This does not cancel a vehicle, undo completed moves or grant affected customers consent.',job=key,owner=lift['owner']);continue
   if lift['moving']:continue
   if spec['owner']!=lift['owner'] or any(s['parts'][p]['owner']!=spec['owner'] for p in spec['parts']):
    job['status']='blocked';receipt('lift_permission','The actual lift holder/cargo-owner scope does not cover this requested move.',job=key,current_owner=lift['owner']);continue
   origin=lf['ground'] if spec['direction']=='up' else lf['storage']
   if spec['direction']=='none' or not spec['parts'] or any(s['parts'][p]['location']!=origin for p in spec['parts']):continue
   if spec['direction']=='down' and 'U-top' in spec['parts'] and not s['V_frame_visit']:continue
   if 'V-frame' in spec['parts'] and not f['actual_future']['V_available']:
    job['status']='blocked';receipt('lift_receiver_absent','Actual remaining frame has reached the building loading point, but its owner was absent for the agreed upstairs receipt. It remains in known carrier custody; no final V receipt or transfer prerequisite is created.',job=key);continue
   ends=at+lf['move_minutes']
   if ends>lf['end_at'] or sum(s['parts'][p]['weight'] for p in spec['parts'])>lf['capacity']:
    job['status']='blocked';receipt('lift_window','The selected real lift move cannot complete within its actual booked time/capacity.',job=key);continue
   lift['moving']={'key':key,'spec':deepcopy(spec),'ends':ends};lift['status']='active';job['status']='moving'
   for part in spec['parts']:s['parts'][part]['state']='in_lift'
   receipt('lift_started','Actual selected freight-lift handling started; it is not a final upstairs or downstairs receipt yet.',job=key,parts=spec['parts'],owner=spec['owner'],direction=spec['direction'],completion_not_before=ends);timer(ends)
  if at>=lf['end_at'] and not lift['moving'] and lift['status'] in ['reserved','active']:
   lift['status']='expired';receipt('lift_expiry','Actual L88 slot ended. Earlier accepted moves and transfers remain real; this does not cancel a vehicle or erase a remaining item obligation.',owner=lift['owner'])
 def freight_process():
  c=f['contracts']
  if any(r.get('id') in ['F89_booking_whole_route','F89_booking_U_only'] for r in resources.values()) and s['services']['F89']=='not_booked':s['services']['F89']='booked'
  for key,job in s['jobs'].items():
   if job['status']!='in_transit' or at<job['arrives']:continue
   leg=job['spec'];dest=leg['to'];parts=leg['parts'];owner=leg['order_owner']
   if dest=='U' and not f['actual_future']['U_available']:
    job['status']='delivery_pending';receipt('delivery_pending','Actual carrier reached the receiving point but U was absent. Known carrier custody remains, not final delivery.',job=key,parts=parts,carrier=leg['service']);continue
   for part in parts:
    p=s['parts'][part]
    if dest=='V' and part=='V-frame':p.update(location='V_ground',state='at_ground')
    else:p.update(holder=dest,location='V_ground' if dest=='V' else 'U_home' if dest=='U' else 'warehouse',state='final' if dest==p['owner'] and leg['purpose']=='final' else 'staged')
   job['status']='done';s.setdefault('service_positions',{})[leg['service']]=dest
   if dest=='V' and 'V-frame' in parts:
    receipt('building_arrival','Actual vehicle reached V loading point with the frame. It remains in carrier custody at ground level; only the actual upstairs acceptance can complete the frame/activate the lift-transfer condition.',job=key,service=leg['service'],parts=parts,actual_parts={p:deepcopy(s['parts'][p]) for p in parts})
   else:
    receipt('delivery','Actual itemized carrier delivery. This closes only the named real component leg, not another part/order or a lift step.',job=key,service=leg['service'],parts=parts,to=dest,purpose=leg['purpose'],actual_parts={p:deepcopy(s['parts'][p]) for p in parts})
    if dest==owner:private(owner,'Your actual component delivery: '+', '.join(parts)+'. Only these listed pieces are final at your receiving point; other components retain their separate actual receipts.',parts=parts)
  lift_process()
  for key,job in s['jobs'].items():
   if job['status']!='queued' or at<job['spec']['at']:continue
   leg=job['spec'];service=leg['service'];parts=leg['parts'];origin=leg['from'];dest=leg['to']
   if s['services'][service]=='cancelled':job['status']='cancelled';continue
   if service=='F89':
    booking=next((r for r in resources.values() if r.get('id') in ['F89_booking_whole_route','F89_booking_U_only']),None)
    if not booking:continue
    s['services']['F89']='booked'
    if booking['scope']=='U_only' and any(p.startswith('V-') for p in parts):
     job['status']='blocked';receipt('scope_blocked','The actual booked U-only quote does not carry the other order cargo.',job=key);continue
   location='V_ground' if origin=='V' else 'U_home' if origin=='U' else 'warehouse'
   if any(s['parts'][p]['holder']!=origin or s['parts'][p]['location']!=location for p in parts):continue
   if origin=='V' and 'U-top' in parts:
    if not s['V_frame_visit'] or not c['V_order']['combined_visit'][0]<=at<=c['V_order']['combined_visit'][1]:continue
   if origin=='warehouse' and service=='F88' and at<c['F88']['start_at']:continue
   active=[j for j in s['jobs'].values() if j['status']=='in_transit' and j['spec']['service']==service];stops=c['F88']['stops'];last=s.get('service_positions',{}).get(service,'warehouse')
   same_group=all(j['spec']['at']==at and j['spec']['from']==origin and j['spec']['to']==dest for j in active)
   if active and not same_group or stops.index(origin)<stops.index(last) or stops.index(dest)<=stops.index(origin):
    job['status']='blocked';receipt('route_blocked','Actual single ordered cart round cannot reverse completed stops or collect a separate leg while travelling. Same-time/same-route grouped cargo remains possible.',job=key);continue
   arrives=at+f['processing']['leg_minutes'];window=c['V_order']['combined_visit'] if dest=='V' else c['U_order']['receiver_window'] if dest=='U' else [0,99999]
   if not window[0]<=arrives<=window[1]:job['status']='blocked';receipt('window_blocked','Actual selected arrival falls outside the accepted visit window.',job=key,selected_arrival=arrives,actual_window=window);continue
   if any(s['parts'][p]['owner']!=leg['order_owner'] for p in parts):job['status']='blocked';receipt('recipient_scope','Selected order label does not match actual cargo title; no new agreement or delivery was created.',job=key);continue
   if leg['purpose']=='final' and dest!=leg['order_owner']:job['status']='blocked';receipt('recipient_scope','The actual recipient has not accepted another owner goods as its purchased final order.',job=key);continue
   load=sum(s['parts'][p]['weight'] for p in parts)+sum(sum(s['parts'][p]['weight'] for p in x['spec']['parts']) for x in active)
   if load>c['F88']['capacity']:job['status']='blocked';receipt('load_blocked','Actual cart load exceeds its allocation; no selected component was collected.',job=key,actual_load=load,allocation=c['F88']['capacity']);continue
   for p in parts:s['parts'][p].update(holder=service,location='in_transit',state='in_transit')
   job['status']='in_transit';job['arrives']=arrives;timer(arrives)
   receipt('collection','Actual itemized carrier collection, not final owner delivery.',job=key,service=service,parts=parts,from_point=origin,to_point=dest,actual_load=load)
  for service in ['F88','F89']:
   jobs=[j for j in s['jobs'].values() if j['spec']['service']==service]
   if jobs and all(j['status']=='done' for j in jobs):s['services'][service]='used'
   elif jobs and any(j['status'] in ['done','blocked','delivery_pending'] for j in jobs) and s['services'][service]!='cancelled':s['services'][service]='partial'
 def process():
  s['scheduled']=[t for t in s['scheduled'] if t>at]
  if f['kind']=='journal':journal_process()
  else:freight_process()
 if kind=='business_submit':
  draft=deepcopy(resources['work_draft']['fields'])
  if f['kind']=='journal':
   jobs=draft['jobs'];keys=[x['key'] for x in jobs]
   if len(keys)!=len(set(keys)) or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,50}',key) or key in s['jobs'] for key in keys):raise ValueError('Actual work keys must be unique')
   for spec in jobs:s['jobs'][spec['key']]={'spec':spec,'status':'queued'};timer(spec['earliest_at'])
  else:
   for lid in draft['cancel_lifts']:
    s['lift']['status']='cancelled';receipt('lift_cancellation','Actual selected L88 reservation cancelled; no vehicle, cargo ownership or customer consent changes.',lift=lid)
   for spec in draft['lift_jobs']:
    if spec['key'] in s['lift_jobs']:raise ValueError('Lift work key already submitted')
    s['lift_jobs'][spec['key']]={'spec':spec,'status':'queued'};timer(spec['at'])
   for service in draft['cancel_services']:
    s['services'][service]='cancelled';receipt('service_cancellation','Actual service cancellation recorded; completed physical legs, goods ownership and any booked fee remain separate facts.',service=service)
   keys=[]
   s['current_manifest']={'selected_legs':deepcopy(draft['legs']),'submitted_at':at,'cancel_services':deepcopy(draft['cancel_services'])}
   for spec in draft['legs']:
    if len(spec['parts'])!=len(set(spec['parts'])) or not spec['parts']:raise ValueError('Cargo parts must be nonempty and unique')
    key='selected-leg-'+str(len(s['jobs'])+1);keys.append(key);s['jobs'][key]={'spec':spec,'status':'queued'};timer(spec['at'])
  receipt('request','Actual selected work received. No future return, refit, eligibility, delivery, buyer agreement or authorization verdict is asserted.',selected_work=draft)
  schedule.append({'id':f['kind']+'-submit-process-'+str(s['serial']),'at':at,'calculator':'business_process'})
  facts={'request_received':True,'selected_work_keys':keys}
 elif kind=='business_process':process();facts={}
 else:raise ValueError('Unknown business native call')
 public=deepcopy({k:v for k,v in s.items() if k not in ['jobs','lift_jobs','scheduled','serial']})
 return {'facts':facts,'effect':{'native_state_replace':s,'native_schedule':schedule,'set':{'business_actual':public},'add':add}}
