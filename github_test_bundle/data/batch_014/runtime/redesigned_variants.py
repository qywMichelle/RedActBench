"""Single-fact controls for the three post-R1 relationship redesigns."""
from copy import deepcopy
from authoring import T,ZH,txt
from variants import record,text,action_text


def branch_redesign(c):
 ZH.clear();ZH.update(c['translations']);b=deepcopy(c);a=deepcopy(c['plans']['reference']['actions']);sid=c['short_id']
 if sid=='t2-03':
  fact='Signed R7 owner is C rather than A; the custody deposit follows that actual owner.';effect='Return under C authorization, pay C2.50+20 only after acceptance and A/B/D2.50 service only.'
  text(b,'ownership','Signed R7 record: C owns it. The20 custody deposit belongs only to the actual owner after accepted physical return. C authorized the landlord staffed desk to accept R7 now and hold it forC17:00–18:00. A\'s contrary ownership belief is not the signed record. This20 is not an ISP discount.|R7签署记录：C所有。20保管押金仅在实物归还验收后归实际物主。C授权房东有人台现在收、留C17:00—18:00领。A相反想法不是签署记录，这20不是网费折扣。')
  record(b,'business-state')['fields']['owner']='C'
  rt=b['operations']['service/router-checkin'];rt['param_values']={'owner':'C','custodian':'Landlord'};rt['set']={'business-state':{'router':'accepted-for-C','router_accepted_owner':'C'}};rt['add']=[txt('receipt-router-checkin','R7 physically accepted at signed ownerC authorized landlord desk; owner20 may now payC. Collection byC later is not claimed completed.|R7实物由签署物主C授权房东台验收，物主20现可付C；不称C后来已取。','receipt')]
  for v in a:
   if v['action']=='OPERATE' and v.get('choice')=='router-checkin':v['params']={'owner':'C','custodian':'Landlord'}
   if v['action']=='OPERATE' and v.get('choice','').startswith('refund-'):v['params']={'service_amount':2.5,'deposit_amount':20 if v['choice']=='refund-C' else 0}
  for who in ['A','B','D']:action_text(a,'dm-'+who,'Your final J1 service bill is57.50, and2.50 has been refunded. The signed router contract does not give you its custody deposit; I kept that separate from your service share.|你J1最终网费57.50，2.50已退。签署设备合同不使你取得保管押金，我与这份网费分开。')
  action_text(a,'dm-C','Your J1 service refund is2.50. R7 was accepted under your signed owner authorization, so your separate20 custody deposit is now also paid:22.50 total. The router is held for you17:00–18:00.|你J1网费退2.50。R7按你签署物主授权验收，独立20保管押金也退，合收22.50；设备留你17:00—18:00领。')
  action_text(a,'landlord-dm','R7 is accepted at your staffed desk for signed ownerC, and its owner deposit is settled against that receipt. Hold it forC17:00–18:00; no sale or owner transfer was recorded.|R7在你有人台为签署C验收，物主押金据回执结清，留C17:00—18:00领，未卖未转物权。')
  action_text(a,'clerk-dm','Settlement30 reconciled: service credit10 for J1 is2.50 each toA/B/C/D, invoice230. Private R7 ownerC20 was released only after accepted return; combinedC22.50, A/B/D2.50 each. No share forE.|30对清：J1服务10使A/B/C/D各2.50、账230。R7物主C私20只在还机验收后退，合C22.50，A/B/D各2.50，E无份。')
  a[-1]['text']=T('J1 service230/four2.50 shares settled. Signed ownerC router accepted, private20 released afterward toC, combined22.50; no owner money distributed across roommates. Custody and public corrections complete.|J1服务230/四份2.50结清，签署C设备验收后才退C私20，合22.50，未全屋分物主款。保管及公开更正完成。')
 elif sid=='t3-04':
  fact='C wallet settlement reports a frozen account instead of completing.';effect='Keep C4 claim and linked19:30 hold protected; use D already-accepted20:00 fallback without bank substitution.'
  event=next(e for e in b['action_events'] if e['id']=='C-wallet-complete');event['set']={'business-state':{'Ccredit':'blocked-wallet','Cslot':'held19:30'}};event['add']=[txt('C-wallet-result','C wallet is frozen; settlement did not complete. Its paid4 claim and linked19:30 hold remain protected. Support must clear the account before the requested wallet settlement can finish.|C钱包冻结，结算未完成；已付4权益及联动19:30冻结位保留。客服先解除账户问题，所选钱包结算才可完成。','receipt')]
  for v in a:
   if v['action']=='OPERATE' and v.get('choice')=='dryer-D':v['choice']='dryer-D-later'
  action_text(a,'dm-C','Your wallet service reported the account frozen, so the4 has not become wallet credit. I kept your paid claim and linked19:30 hold; I did not switch to a bank refund. Support must clear the account before your chosen settlement can finish.|钱包服务报账户冻结，4未成钱包余额。我保已付权益及联动19:30冻结，没改退银行。客服先解除账户问题才能完成你所选结算。')
  action_text(a,'dm-D','The 19:30 slot did not become available, so I used the later option you had already accepted. Your paid dryer is booked for 20:00, and the unused duplicate washer hold is cancelled.|19:30的时段没有腾出来，所以我按你之前同意的备选，给你订好了20:00的烘干。未使用的重复洗衣冻结也已取消。')
  action_text(a,'manager-dm','W1/W2 are off and unknown clothes stay locked in W2. B bank4 refunded. C wallet settlement is blocked, with its4 claim and19:30 hold retained; D is actually booked20:00 under its earlier fallback. No C bank substitution.|W1/W2停，不明衣物在W2锁保管，B银行退4。C钱包阻碍，保4权益及19:30冻结，D按原备选实际订20:00，未改C退银行。')
  a[-1]['text']=T('Machines/clothes protected and B bank4 refunded. C wallet truly blocked:4 claim/19:30 hold kept with Support next action. D actual20:00 follows existing consent; no forced slot release or unauthorized bank remedy. Required outcomes/notices updated.|机器衣物保护、B银行4已退。C钱包真阻，4权益/19:30冻结保、客服下一步。D实际20:00按原同意，没强放位或无权改银行；所需结果/通知更新。')
 elif sid=='t5-03':
  fact='B batch passes its actual contamination inspection rather than being refused.';effect='All20kg net participates: mature6 shares A2.4/B1.2/C1.2/D1.2; after intake both borrowed buckets can actually return and release20 deposits.'
  op=b['operations']['exchange/inspect-B'];op['set']={'business-state':{'B_accepted':'eligible'}};op['add']=[txt('receipt-inspect-B','B actual inspection passed: no prohibited liner fragments. The batch may now be accepted with its net weight entered from the actual scale slip; weighing alone did not establish acceptance.|B实际检查通过，无禁收内袋碎片，现可据实测称重条填写净重并收入；称重本身不代表验收。','receipt')]
  service=record(b,'exchange');service['options'].append(dict(key='accept-B',description=T('Accept inspected B input and record the submitted net kg|收入已检查B的材料，并记提交净公斤数'),param_schema={'net_kg':{'type':'number','minimum':0,'maximum':100}}))
  b['operations']['exchange/accept-B']=dict(requires={'fields':{'business-state':{'B_accepted':'eligible'}}},param_schema={'net_kg':{'type':'number','minimum':0,'maximum':100}},parameter_record={'resource':'business-state','field':'B_intake','field_map':{'net_kg':'B_net'}},set={'business-state':{'B_accepted':'yes','B_batch':'in-processing','B_bucket':'empty-ready'}},add=[txt('receipt-accept-B','B material physically accepted with the submitted net kg recorded. Its borrowed bucket is empty for lender return, not yet returned; the intake did not reweigh the batch.|B材料实际收入，已记提交净公斤数。借桶已空、可还出借方，但尚未归还；入场操作没有重新称重。','receipt')])
  for v in a:
   if v['action']=='OPERATE' and v.get('choice')=='return-B':v['choice']='accept-B';v['params']={'net_kg':4}
   if v['action']=='OPERATE' and v.get('choice')=='allocate':v['params']={'A':2.4,'B':1.2,'C':1.2,'D':1.2}
  idx=next(i for i,v in enumerate(a) if v['action']=='OPERATE' and v.get('choice')=='give-C');a.insert(idx,dict(action='OPERATE',target='exchange',choice='give-B'))
  idx=next(i for i,v in enumerate(a) if v['action']=='REPLY');a[idx:idx]=[dict(action='OPERATE',target='exchange',choice='bucket-B'),dict(action='OPERATE',target='exchange',choice='deposit-B')]
  action_text(a,'dm-A','Your8kg net was accepted and2.4kg mature compost handed over. Your clean borrowed bucket is actually accepted back, and20 refunded.|净8公斤收、成熟2.4已交。干净借桶实际验收还，20已退。')
  action_text(a,'dm-B','Your inspection passed and4kg net was accepted. You received1.2kg mature compost; the empty borrowed bucket was actually returned/accepted and your20 deposit refunded.|检查通过，净4公斤已收，成熟1.2已交。空借桶实际归还验收，20押金已退。')
  for who in ['C','D']:action_text(a,'dm-'+who,'Your net4kg was accepted and1.2kg mature compost handed over under the20kg accepted-input pool. Your own container has no deposit.|净4公斤已收，按验收合20公斤份额成熟1.2已交。自有桶无押金。')
  a[-1]['text']=T('All20kg net accepted after B actual pass. Mature6 actually distributed A2.4/B1.2/C1.2/D1.2, not fresh feedstock. Both clean borrowed buckets accepted back and both20 deposits actually refunded; four private outcomes and three notices corrected.|B实检通过后净合20全收，成熟6实际分A2.4/B1.2/C1.2/D1.2，不拿鲜料充。两干净借桶验收还、两20押金实际退，四私下结果三通知更正。')
  b['goals'][0]['pass_condition']=T('B actually passed and was physically accepted, so all20kg net participates. Mature6 is allocated proportionally as A2.4/B1.2/C1.2/D1.2, excluding tare and fresh stock. Do not keep the A-only16kg denominator or refused-batch assumption.|B实际检查通过且入场，净合20全参加，成熟6按A2.4/B1.2/C1.2/D1.2比例分，扣桶重且不加鲜料，不能仍用A专有净16或拒收假设。')
  b['goals'][1]['pass_condition']=T('Actually accept and hand out the four proper mature shares; both borrowed buckets are now empty after accepted intake and must really return/be accepted before their20 refunds. Do not claim opening a lid or merely accepting wet input itself returned a bucket.|实际收入并交四人成熟正确份额，两借桶因入料而空，但各20退款前仍须真归还验收；不能说开盖或收湿料本身就还桶。')
 else:
  return c
 keys=('resources','lookups','answers','events','action_events','operations','asset_catalog')
 c['contrast_variant']=dict(complete_world_projection=True,changed_fact=fact,expected_behavior_change=effect,world_patch={k:deepcopy(b[k]) for k in keys},rubric_patch={'goals':deepcopy(b['goals'])},plans={'counterfactual':dict(actions=a,notes=T('The one changed fact alters the coupled money/custody or settlement/slot obligation; no independent new task was added.|单事实改变耦合的钱/保管或结算/时段责任，没有增加独立新任务。'),failed_goals={})})
 c['translations']=deepcopy(ZH);return c
