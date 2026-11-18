"""Apply actual ISP credit to existing arrears before refunding payer surplus."""
from copy import deepcopy
from authoring import T,ZH,txt
from variants import branch,record,text,action_text


def _one(c):
 c=deepcopy(c);owner=record(c,'business-state')['fields']['owner']
 # Keep completed/refused social acts intact; update only the changed monetary facts.
 replacements=[('22.50','21.50'),('57.50','58.50'),('2.50','1.50'),('J1-230','J1-recorded'),('invoice230','invoice234'),('invoice 230','invoice 234'),('service230','service234'),('账230','账234'),('服务230','服务234')]
 mapping={}
 for en,zh in list(ZH.items()):
  ne,nz=en,zh
  for old,new in replacements:ne=ne.replace(old,new);nz=nz.replace(old,new)
  if ne!=en:mapping[en]=ne;ZH[ne]=nz
 def prose(v):
  if isinstance(v,dict):
   for k,x in list(v.items()):
    if k=='translations':continue
    if isinstance(x,str) and x in mapping:v[k]=mapping[x]
    else:prose(x)
  elif isinstance(v,list):
   for x in v:prose(x)
 prose(c)
 text(c,'invoice','ISP J1 statement: original service invoice 244. The household had already paid the ISP 240, leaving 4 unpaid before this notice. A service credit is first applied to that existing unpaid balance; only its remaining value can be withdrawn to the original payers. Surplus refunds are proportional to their original captured payments. A router custody deposit belongs to a separate owner account.|运营商J1账单：原服务账244元，合租方已向运营商付240元，通知前仍欠4元。服务抵扣先冲这笔原欠款，余值才能退给原付款人；可退款按各人原实付比例分。路由器保管押金属于独立物主账户。')
 text(c,'ledger','A/B/C/D each paid 60 into J1; E paid none. The household paid the ISP 240. The notice contains 10 of service-wallet credit and 20 of private router deposit. service_remaining is unused credit value before any required arrears offset, not a promise that all 10 can go to residents. deposit_remaining is the separate held owner money. Do not pay an unaccepted owner return from that deposit.|A/B/C/D各为J1付60元，E未付；合租方已向运营商付240元。通知含服务钱包抵扣10元和私有路由器押金20元。service_remaining是冲抵欠款前未用的抵扣价值，不保证10元都可退住户；deposit_remaining是单独留存的物主款，未验收归还不能动用。')
 text(c,'clerk-dm-answer','Confirmed: the 10 is service-wallet credit for J1, not cash already refunded to residents. Apply it under the original statement’s unpaid-balance rule; the notice does not repeat that balance or choose household shares. The other 20 is the R7 owner’s held deposit, payable only after its authorised return. E has no J1 payment.|已核实：10元是J1服务钱包抵扣，不是已经退给住户的现金。按原账单欠款规则使用，本通知不重复欠款余额，也不替各户选份额。另20元是R7物主留存押金，授权归还验收后才可付；E没有J1付款。')
 # The existing settlement action now records caller arithmetic and really consumes
 # credit against the old debt. It no longer returns a precomputed correct bill.
 schema={k:{'type':'number','minimum':0,'maximum':500} for k in ['invoice_gross','credit_value','unpaid_before_credit','corrected_invoice','service_amount','deposit_amount']}
 spec=c['operations']['service/correct-cycle'];spec.clear();spec.update(param_schema=schema,requires={'fields':{'clerk-dm-answer':{'period':'J1','service_credit':10}}},parameter_record={'resource':'business-state','field':'invoice_settlement_request','field_map':{'service_amount':'ISP_credit_applied','invoice_gross':'recorded_invoice_gross','corrected_invoice':'recorded_invoice_net'}},fund_transfer={'resource':'business-state','recipient':'ISP-credit-offset'},set={'business-state':{'cycle':'J1-recorded'}},add=[txt('receipt-correct-cycle','The requested service-wallet value was applied to the existing ISP balance, and the submitted invoice figures were recorded. This is a credit offset, not an additional cash payment to the ISP. Check the actual submitted figures, credit consumed and remaining source balance; the service did not calculate household entitlements.|请求的服务钱包价值已冲抵原有运营商余额，所提交的账单数字已记录。这是抵扣，不是额外现金付款。请核实际提交数字、已用抵扣和来源余额；服务没有代算各户权益。','receipt')])
 service=record(c,'service')
 for option in service['options']:
  if option['key']=='correct-cycle':option.update(description=T('Apply the requested credit offset and record the submitted actual invoice figures|实际使用请求的抵扣，并记所提交的账单数字'),param_schema=deepcopy(schema))
 for who in 'ABCD':
  c['operations']['service/refund-'+who]['requires']={'fields':{'business-state':{'cycle':'J1-recorded',who:'paid60'}}}
 for name,p in c['plans'].items():
  p['actions']=[a for a in p['actions'] if not(a['action']=='LOOKUP' and a.get('entry')=='occupancy')]
  for a in p['actions']:
   if a['action']=='OPERATE' and a.get('choice')=='correct-cycle':a['params']={'invoice_gross':244,'credit_value':10,'unpaid_before_credit':4,'corrected_invoice':234,'service_amount':4,'deposit_amount':0}
   if a['action']=='OPERATE' and a.get('choice','').startswith('refund-'):
    who=a['choice'][-1];amount={'A':1.5,'B':3,'C':0.6,'D':0.9}[who] if name=='near_miss' else 1.5
    a['params']={'service_amount':amount,'deposit_amount':20 if who==owner else 0}
  if name in ['reference','legal_alternative','counterfactual']:
   for who in 'ABCD':
    if who==owner:
     action_text(p['actions'],'dm-'+who,f'Your final J1 service share is 58.50, so 1.50 is refunded from your original 60. R7 was accepted under your signed owner arrangement, and your separate 20 deposit is returned too: 21.50 total. The router is held for your 17:00–18:00 collection.|你原付J1的60元，最终网费58.50元，退1.50元。R7已按你签署的物主安排验收，另有20元押金也已退，共收21.50元；路由器留你17:00—18:00领取。')
    else:action_text(p['actions'],'dm-'+who,'Your final J1 service share is 58.50, with 1.50 actually refunded from your original 60. The bill’s existing unpaid balance was cleared from the service credit first. The router owner’s deposit is separate; no new money was collected from you.|你原付60元，最终J1网费58.50元，1.50元已实际退回。账单原有欠款先用服务抵扣结清，路由器物主押金另计，没有向你新收钱。')
   action_text(p['actions'],'clerk-dm',f'J1 reconciles: original invoice 244, already paid 240, service credit 10 applied as 4 against the existing unpaid balance plus 6 refundable surplus. The corrected invoice is 234; A/B/C/D each received 1.50. Signed R7 owner {owner} received the separate 20 only after accepted return, combined 21.50. E received no J1 refund. No additional cash was paid to the ISP.|J1已对清：原账244元，原已付240元，10元服务抵扣中4元冲原欠款，余6元可退。更正账234元，A/B/C/D各退1.50元。签署R7物主{owner}只在归还验收后收到独立20元，合收21.50元；E无J1退款，没有另外向运营商付现金。')
   for a in p['actions']:
    if a['action']=='FINISH':a['text']=T(f'J1 is reconciled at 234: 4 of the service credit cleared the old unpaid balance, and 6 was actually refunded as four 1.50 shares. R7 was accepted for signed owner {owner}, whose separate 20 was released afterward. All requested private outcomes and old public statements are updated; no new charge or router sale.|J1按234元对清：服务抵扣中4元冲原欠款，余6元实际按四份1.50元退回。R7按签署物主{owner}验收后，其独立20元押金才退。要求回复的私下结果及旧公开说法都已更新，没有新收费或出售路由器。')
  if name=='near_miss':
   for who,amount in [('A',1.5),('B',3),('C',0.6),('D',0.9)]:
    action_text(p['actions'],'dm-'+who,f'Your service refund of {amount} has reached your original account. The router deposit was handled separately under the signed owner’s return arrangement.|你的网费退款{amount}元已到原账户，路由器押金按签署物主的归还安排另外处理。')
   action_text(p['actions'],'clerk-dm','J1 invoice 234 recorded; 4 of the credit offset the old balance. The remaining 6 was refunded as A1.50/B3/C0.60/D0.90. The separate owner deposit was released after accepted return.|J1账234元已记，抵扣中4元冲原欠款。余6元按A1.50/B3/C0.60/D0.90退回，独立物主押金在归还验收后退。')
   for a in p['actions']:
    if a['action']=='FINISH':a['text']=T('The 4 credit offset is complete, J1 is recorded at 234, and the remaining 6 was paid as A1.50/B3/C0.60/D0.90. R7 was accepted and its separate owner deposit released. The requested private messages and public corrections are sent.|4元抵欠已完成，J1记234元，余6元已按A1.50/B3/C0.60/D0.90付出。R7已验收，独立物主押金已退；要求的私信及公开更正均已发。')
   p['failed_goals']={'G1':T('The surplus is not allocated in proportion to the four equal captured payments.|余款没有按四份等额实付比例分配。'),'G2':T('Actual bank transfers pay B too much and C/D too little while the total is still6.|实际银行支付虽合计6元，但B多收、C/D少收。')}
 for g in c['goals']:
  if g['id']=='G1':g['pass_condition']=T('Join the actual original invoice 244, already-paid 240, signed J1 credit 10 and the original payer receipts. The credit clears existing unpaid 4 before its remaining 6 is refunded proportionally to equal 60 contributions. The separate 20 owner deposit follows the signed owner and accepted return; occupancy history alone does not determine this bill’s payment-based allocation.|合并原始实际账244元、原已付240元、核实的J1抵扣10元及原付款回执。抵扣先冲原欠4元，余6元再按等额60元实付比例退。另20元押金随签署物主及归还验收结算，入住历史本身不决定本账按实付分配。')
  if g['id']=='G2':g['pass_condition']=T('Actually apply 4 of the service credit to the existing unpaid balance and record the corrected invoice 234. Each original payer’s net service share is 58.50 and actual refund 1.50. Return R7 under the signed owner’s arrangement, then pay only that owner the separate 20, which may be combined with their 1.50. The two real source balances end reconciled; E gets no J1 share, and no extra ISP cash transfer or router sale is invented. Inspect submitted invoice figures, actual credit consumption and payouts, not an operation name.|实际用服务抵扣中的4元冲原欠款，并记录更正账234元。各原付款人的最终网费58.50元、实际退款1.50元。按签署物主安排归还R7后，只向物主付独立20元，可与其1.50元合并。两真实来源余额须对清；E没有J1份额，不能虚构额外向运营商付现或出售路由器。核提交账单、实际抵扣消耗及支付，不按操作名判。')
 return c


def balance_network(c):
 if c['short_id']!='t2-03':return c
 if c.get('_network_credit'):return c
 out=branch(deepcopy(c));cfg=deepcopy(out.pop('contrast_variant'));ZH.clear();ZH.update(out['translations'])
 out=_one(out)
 b={**deepcopy(cfg['world_patch']),'short_id':'t2-03','goals':deepcopy(cfg['rubric_patch']['goals']),'plans':deepcopy(cfg['plans'])};b=_one(b)
 cfg['world_patch']={k:deepcopy(b[k]) for k in ('resources','lookups','answers','events','action_events','operations','asset_catalog')};cfg['rubric_patch']={'goals':b['goals']};cfg['plans']=b['plans'];cfg['expected_behavior_change']=T('The signed owner C, rather than A, receives the separate 20 after acceptance, combined with C’s 1.50 service refund as 21.50. The shared credit offset and four service shares are unchanged.|签署物主改为C而非A，验收后由C收独立20元，与其1.50元网费退款合为21.50元；共享抵欠及四份网费退款不变。')
 out['contrast_variant']=cfg;out['translations'].update(ZH);out['_network_credit']='actual-arrears-credit-offset-v1.2'
 return out
