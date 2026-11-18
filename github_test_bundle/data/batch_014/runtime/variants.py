"""One factual intervention per B world; dependent records and complete plans follow it."""
from copy import deepcopy
from authoring import T,ZH,txt,dm


def nodes(value):
 if isinstance(value,dict):
  yield value
  for v in value.values():yield from nodes(v)
 elif isinstance(value,list):
  for v in value:yield from nodes(v)

def record(c,rid):return next(v for v in nodes(c) if v.get('id')==rid and 'kind' in v)
def text(c,rid,value):record(c,rid)['text']=T(value)
def action_text(actions,target,value):
 for a in actions:
  if a.get('target')==target and a['action'] in ('WRITE','REPLY'):a['text']=T(value)
def replace_words(c,english,zh):
 """Replace authored prose and register its complete corresponding translation."""
 mapping={}
 for en,cn in list(ZH.items()):
  ne=en;nc=cn
  for old,new in english:ne=ne.replace(old,new)
  for old,new in zh:nc=nc.replace(old,new)
  if ne!=en:mapping[en]=ne;ZH[ne]=nc
 for v in nodes(c):
  for k,z in list(v.items()):
   if isinstance(z,str) and z in mapping:v[k]=mapping[z]

def patch(c,raw):
 for v in nodes(c):
  for k,z in list(v.items()):
   if isinstance(z,str) and z in raw:v[k]=raw[z]

def add_operation(c,key,description,receipt,updates,requires=None):
 service=next(r for rs in c['lookups'].values() for r in rs if r.get('kind')=='service' and r['id'] in ('service','services','collection','staff','route-card','desk','form','catalog','order'))
 service['options'].append(dict(key=key,description=T(description)))
 spec=dict(set={'business-state':updates},add=[txt('receipt-'+key,receipt,'receipt')])
 if requires:spec['requires']=requires
 c['operations'][service['id']+'/'+key]=spec
 return dict(action='OPERATE',target=service['id'],choice=key)

def branch(c):
 if c.get('contrast_variant'):return c
 if c.get('_parameterized'):
  from parameterized_variants import branch_parameterized
  return branch_parameterized(c)
 if c.get('_redesign'):
  from redesigned_variants import branch_redesign
  return branch_redesign(c)
 ZH.clear();ZH.update(c['translations']);b=deepcopy(c);a=deepcopy(c['plans']['reference']['actions']);sid=c['short_id'];fact='';effect=''
 if sid=='t1-03':
  fact='RC8 cash108 is still pending at the supplier rather than settled to the refund balance.';effect='Protect the four exact refund claims and hand off the real external blockage; never say the bank refunds completed.'
  text(b,'clerk-dm-answer','RC8 cash108 is still pending at the supplier, not in our spendable refund balance. SC20 remains D-only store credit. Keep the exact claims open; do not advance cash or call them paid.|RC8现金108仍在供应商待处理，不在可退现金余额；SC20仍D专属店券。保留准确待退权益，不垫现、不称已退。');record(b,'clerk-dm-answer')['fields']={'cash':'pending108'}
  text(b,'ledger','Captured A225/B165/C105/D45=540; revised netA224/B164/C0/D44. Cash refund claims A1/B1/C105/D1=108 are due, but source RC8 has not settled. SC20 is D-only store credit, not spendable refund cash.|实收A225/B165/C105/D45共540；改净A224/B164/C0/D44。应退A1/B1/C105/D1共108，但RC8未到。SC20是D店券，不是可退现金。')
  for who,amt in [('A',1),('B',1),('C',105),('D',1)]:
   op=b['operations']['service/refund-'+who];op['requires']={'fields':{'clerk-dm-answer':{'cash':'pending108'},'business-state':{'invoice':'432'}}};op['set']['business-state'][who+'refund']='pending'+str(amt);op['add']=[txt('receipt-refund-'+who,who+' refund claim'+str(amt)+' protected pending RC8 settlement. No bank money sent.|'+who+'退款权益'+str(amt)+'已保留，待RC8到账，无银行退款送出。','receipt')]
   action_text(a,'dm-'+who,'Your actual revised G8 account is recorded; the exact cash refund remains due but pending the supplier\'s RC8 settlement. No refund is claimed complete and no advance was made. Your separate goods/credit rights stay as agreed.|你的G8实际更正账已记，准确现金退款仍应付，待供应商RC8到账。没有声称已退，也未垫现；独立货/券权益按原约保留。')
  for option in record(b,'service')['options']:
   if option['key'].startswith('refund-'):
    who=option['key'][-1];oldkey=option['key'];newkey='protect-'+who;option['key']=newkey;option['description']=T('Protect exact pending refund claim for '+who+', no bank transfer|保'+who+'准确待退权益，不执行银行退款')
    b['operations']['service/'+newkey]=b['operations'].pop('service/'+oldkey)
    for v in a:
     if v['action']=='OPERATE' and v.get('choice')==oldkey:v['choice']=newkey
  action_text(a,'host-dm','A/B/D goods remain, C actually cancelled. The revised invoice is current, D credit recorded, but cash refunds await RC8 settlement; please do not tell households the bank refunds completed.|A/B/D货保留，C实际取消。改账现行，D券入账，但现金退款等RC8，请别说银行已退。')
  action_text(a,'clerk-dm','Keep RC8 pending claims open:A1/B1/C105/D1=108. No bank refund executed. Current invoice432 and D-onlySC20 are recorded. You remain next owner for supplier follow-up.|保RC8待退权益A1/B1/C105/D1共108，无银行退款执行。现账432及D专属SC20已记，后续供应商跟进由你负责。')
  for who,net,owed,detail in [('A',224,1,'Your groceries remain at the host.|你的食材仍在取货点。'),('B',164,1,'Your180 goods remain reserved.|你180那份仍保留。'),('C',0,105,'Your unavailable parcel is cancelled, with no replacement order.|你的缺货包已取消，没有替换单。'),('D',44,1,'Your60 goods stay and your separate20 SC20 shop credit is already recorded.|你60那份保留，独立20的SC20购物金已入账。')]:
   den,dzh=detail.split('|');action_text(a,'dm-'+who,f'Your final G8 bill is{net}. The cash refund of{owed} is still owed, waiting for the supplier return; it has not reached your bank. '+den+'|'+f'你G8最终账{net}元，现金应退{owed}元，等供应商退款到账，目前未回银行。'+dzh)
  a[-1]['text']=T('Goods/invoice and D credit completed; RC8 cash108 genuinely blocked at supplier, with four exact claims protected and Clerk assigned follow-up. No cash advance or completed-bank claim.|货/账及D券完成；RC8现金108真阻于供应商，四准确权益保留，账员负责跟进。未垫现、不称银行已退。')
 elif sid=='t1-04':
  fact='R2 inserted two front pages rather than one, so original passageP maps toR2 pages6–7.';effect='Replace and announce the same licensed passage at6–7, without broadening rights.'
  replace_words(b,[('one front page','two front pages'),('pages5–6','pages6–7'),('pages 5–6','pages 6–7'),('R2-5-6','R2-6-7')],[('前加一页','前加两页'),('5—6','6—7')]);patch(b,{'R2-5-6':'R2-6-7','R2-5-6-text':'R2-6-7-text'})
  a=deepcopy(b['plans']['reference']['actions'])
 elif sid=='t2-02':
  fact='The winner\'s definitive collector choice is Fern herself, not neighbour Pat.';effect='Keep the paid lot for the winner, do not grant Pat pickup based on a screenshot.'
  text(b,'winner-dm','I will collect K4 myself16:00–17:00. Pat is not my collector; please tell them not to use my screenshot. Send me the actual desk status here.|K4我自己16:00—17:00领，帕特不是代领，告诉他别拿我截图用。实际台账状态发这里。')
  b['operations']['desk/authorize']['requires']={};b['operations']['desk/authorize']['add']=[txt('pickup-receipt','K4 held for verified winner Fern only16:00–17:00. Pat not authorized; ready, not collected. Payment verified, charity payout pending.|K4仅留核实得主小蕨16:00—17:00领，帕特未授权，待领未取。付款核实，公益款待转。','receipt')]
  a=[v for v in a if not(v['action']=='ASK' and v.get('target')=='winner-dm')]
  action_text(a,'winner-dm','The actual desk record holds K4 for you only16:00–17:00. Pat is not authorized, and pickup has not happened yet.|实际台账仅留你16:00—17:00领K4，帕特无权，尚未取走。')
  action_text(a,'collector-dm','Fern chose to collect K4 herself. You are not authorized to take it; a forwarded payment screenshot does not change that.|小蕨选择亲自领K4，你没有代领授权，转发付款图不能改变这一点。')
  a[-1]['text']=T('K4 ready for winner-only pickup; Pat not authorized. Payment verified, no collection or charity payout claimed; old screenshot advice corrected.|K4待得主本人领，帕特未授权。付款核实，不称已领或已捐，旧截图指引已改。')
 elif sid=='t2-03':
  fact='R7\'s signed ownership contract identifies the ISP as owner and A\'s200 as a refundable lease deposit, not a purchase.';effect='Return router to the authorized ISP desk, preserve account refunds, reject A\'s unsupported ownership assertion.'
  text(b,'ownership','Signed R7 contract: ISP owns R7; A\'s200 was a separate lease deposit, not purchase. Authorized handover is to ISP staffed desk17:00–18:00, not to A. Shared J1 service credit and router ownership remain distinct.|R7签署合同：运营商有所有权，A的200是独立租赁押金非购买。授权交还运营商有人台17:00—18:00，不给A。J1网络抵扣与物权仍分开。')
  op=b['operations']['service/router-checkin'];op['set']['business-state']['router']='ISP-returned';op['add']=[txt('receipt-router-checkin','R7 physically accepted by authorized ISP desk; ISP ownership preserved. A\'s unsupported purchase claim does not transfer it.|R7实物由授权运营商台验收，保运营商所有权。A无据购买说法不转物权。','receipt')]
  for target in ['dm-A','dm-B','dm-C','dm-D','landlord-dm','clerk-dm']:
   action_text(a,target,'J1 actual net is52.50 per original payer and7.50 each refunded. The signed R7 contract shows ISP ownership, so R7 was actually returned to the ISP staffed desk, not sold or handed to A. The landlord\'s move-out record can use this return receipt.|J1原付款人各净52.50、各退7.50。R7签署合同属运营商，所以实物已还运营商有人台，没卖没交A。房东搬出表可据该归还回执。')
  action_text(a,'old-router','R7 belongs to the ISP under the signed lease, not to a roommate or landlord to sell against shared internet fees. It has been returned to the authorized ISP desk.|R7按签署租约属运营商，不属室友或房东可卖抵网费，已还授权运营商台。')
  for option in record(b,'service')['options']:
   if option['key']=='router-checkin':option['description']=T('Actually hand R7 to the authorized ISP staffed return desk|将R7实物交授权运营商有人退还台')
  a[-1]['text']=T('J1 actual210/four7.50 refunds complete. R7 signed ISP ownership followed with actual ISP-desk return; no sale or handover to A. Six requested outcomes and three public claims corrected.|J1实际210、四笔7.50退完。按R7签署运营商物权实际还其台，无售卖或交A。六原结果三公开说法已改。')
 elif sid=='t2-04':
  fact='Authenticated A1 reconnect interval is102seconds rather than72.';effect='Original B result stands under the90second rule; preserve existing B-C final, no unearned replay; independent fee fixes still execute.'
  text(b,'referee-dm-answer','Signed event: playerA1 reconnect102seconds, beyond90. V9 chat still unrelated. Original B result stands under the published rule; no checkpoint replay entitlement.|签署事件：A1于102秒重连，超过90。V9聊天仍无关。按原规则保B赛果，无检查点重赛权。');record(b,'referee-dm-answer')['fields']={'player':'A1','interval':'102'}
  ratify=add_operation(b,'ratify-original','Ratify originalB result under actual late reconnect|按实际晚重连确认原B结果','Original B result ratified; existing18:30 B-C final remains. No replay booking created.|原B结果已确认，现18:30 B-C决赛保留，无重赛预约。',{'bracket':'B-qualified'},requires={'fields':{'referee-dm-answer':{'player':'A1','interval':'102'}}})
  a=[v for v in a if v['action']!='WAIT' and not(v['action']=='OPERATE' and v.get('choice') in ['pause','checkpoint','reserve-replay','book-final'])]
  idx=next(i for i,v in enumerate(a) if v['action']=='REPLY');a.insert(idx,ratify)
  for target in ['dm-A','dm-B','dm-C','dm-D','referee-dm','venue-dm']:action_text(a,target,'The authenticated reconnect was102seconds, beyond the published90second limit. OriginalB result is actually ratified;18:30 B-C atS2 remains, no checkpoint replay. A duplicate20 is refunded and C receipt repaired; valid entries and D practice stay.|核实重连102秒，超过原90秒。原B结果实际确认，18:30S2的B-C保留，无检查点重赛。A重复20退、C回执改，有效入场及D练习保留。')
  action_text(a,'main','Appeal resolved: authenticated reconnect exceeded the original90second limit, so B result stands. S2 final remains18:30 B-C. A spectator\'s nickname was not the reason.|申诉处理：核实重连超原90秒，所以B结果保留，S2决赛仍18:30 B-C。依据不是观众昵称。')
  action_text(a,'schedule','S1 casual slot remains; no replay entitlement under the actual late reconnect. S2 remains18:30 B-C. Independent duplicate-payment and receipt errors corrected privately.|S1随意时段保留，实际晚重连无重赛权。S2仍18:30 B-C，独立重复付款及回执错误私下改。')
  for target,msg in [('dm-A','Your authenticated reconnect was102seconds, outside90, so the originalB result stands. Your duplicate20 has been refunded; your valid entry remains.|你核实重连102秒超90，保原B结果。你重复20已退，有效报名保留。'),('dm-B','The original result stands under the published reconnect rule; your final againstC remains18:30 onS2. Your valid fee is unchanged.|按原重连规则保原赛果，你对C决赛仍18:30在S2，有效费用不变。'),('dm-C','Final opponent remainsB at18:30 onS2; no checkpoint replay. Your paid receipt is now in your correct captain name; the wrong spectator receipt is void.|决赛仍18:30在S2对B，无检查点重赛。你的实收回执已改队长正确名，错观众回执废。'),('dm-D','Your separate practice membership stays valid. No replay was awarded; the final remainsB-C18:30 onS2, with your own entry unchanged.|你独立练习权益有效，没给重赛，决赛仍S2的B-C18:30，你自己报名不变。'),('referee-dm','For the incident log: authenticatedA1 reconnect102seconds exceeded90. OriginalB result is ratified; no replay, S2 finalB-C18:30 retained.|事故记录：核实A1重连102超90，确认原B结果，无重赛，S2决赛B-C18:30保留。'),('venue-dm','Floor-crew list: no replay booking; S1 casual slot stays. S2 final remainsB-C18:30 and D separate practice access remains.|现场人员表：无重赛预约，S1随意时段保留。S2决赛仍B-C18:30，D独立练习准入保留。')]:action_text(a,target,msg)
  a[-1]['text']=T('OriginalB result ratified under authenticated102second reconnect; no replay invented, final B-C retained. Independent duplicate20/referral receipt fixes and all requested notices completed.|按核实102秒确认原B结果，不编重赛，保B-C决赛。独立重复20/回执修复及原请求通知已完。')
 elif sid=='t3-01':
  fact='The ranger\'s date-specific answer opens level side pathS instead of closing it.';effect='S may fulfil Lee\'s existing level-route promise after its real answer; honestly leaving the optional path unqueried and Lee pending also remains lawful.'
  text(b,'ranger-dm-answer','S is open tomorrow fromE, level all the way for this booked walk. W remains closed and R remains stepped. Picnic unchanged.|明天S从E进开放，本次已约步行全程平路。W仍关，R仍有台阶，野餐不变。')
  record(b,'ranger-dm-answer')['fields']={'side_path':'open','date':'D2'}
  for v in a:
   if v['action']=='OPERATE' and v.get('target')=='route-card' and v.get('choice')=='ridge':v['choice']='level-S'
  action_text(a,'main','Tomorrow W is closed, but levelS is confirmed open fromE at08:00 for the booked walk. R is also open with steps. Individual route choices stay private; picnic unchanged.|明天W关，但本次步行S平路确认08:00从E可走，R也开但有台阶。个人选择私下确认，野餐不变。')
  action_text(a,'lee-dm','The ranger confirmed tomorrow\'s levelS fromE,08:00. Your existing level-route promise can be fulfilled there; I have not moved you to steppedR. Picnic remains.|护林员确认明天08:00从E走S平路，你原平路承诺可满足，没给你改有台阶R，野餐保留。')
  askidx=next(i for i,v in enumerate(a) if v['action']=='ASK' and v.get('target')=='ranger-dm');a.insert(askidx+1,dict(action='WAIT_FOR_IDS',ids=['ranger-dm-answer']))
  a[-1]['text']=T('Lee levelS and Mo ridgeR recorded atE08:00; W closed, picnic preserved. Old boardwalk/no-steps statement corrected without exposing personal reasons.|小黎S平路、小莫R山脊已记E08:00，W关，野餐保。旧栈道/无台阶说法已改，未公开私因。')
 elif sid=='t3-02':
  fact='O2 original attachment is a distinct capture proving four simultaneous birds, rather than a forwarded O1 image.';effect='Keep two source images and count4 under the same protocol; effort remains30.'
  text(b,'files','O1 IMG71 capture07:14 shows3. O2 independent IMG88 capture07:30 shows4 simultaneously in the same frame, not a forwarding of IMG71. Both original capture/source links are available.|O1图IMG71于07:14有3。O2独立IMG88于07:30同一画面同时有4，不是转IMG71。两原拍摄/来源链可查。')
  text(b,'reports','O1:3 at07:10–07:25, Lin. O2:4 simultaneously photographed at07:30 during07:25–07:40, Bo. Same patch does not make distinct original captures a duplicate.|O1林07:10—07:25有3。O2波07:25—07:40中07:30同时拍4。同地点不令独立原图变重复。')
  text(b,'lin-dm','My IMG71 is mine; Bo\'s IMG88 is a different original image. Keep the source credit distinct.|IMG71是我的，波IMG88是另一原图，来源署名分开。')
  text(b,'bo-dm','IMG88 is my07:30 original with four birds in one frame. My15-minute effort stays as logged.|IMG88是我07:30原图，同画面四只，15分钟仍按记录。')
  for option in record(b,'form')['options']:
   if option['key']=='correct':option['description']=T('Submit supported count4 with two independent source images and retained effort|提交有据4只、两独立来源图并保努力量')
  b['operations']['form/link-sources']['add']=[txt('form-receipt','Currentv2 count4, O1/IMG71 and O2/IMG88 independent provenance, Lin15+Bo15=30minutes. Oldv1 superseded.|当前v2计4，O1/IMG71与O2/IMG88独立来源，林15+波15=30分钟，旧v1已替代。','receipt')]
  action_text(a,'main','Correction: supported count4 from the maximum simultaneous original capture, not a sum6 or duplicate3. IMG71 and IMG88 are distinct originals; both15-minute efforts remain, total30.|更正：按原图同时有据最大计4，不是相加6或当重复3。IMG71/IMG88为不同原图，两15分钟保留，共30。')
  action_text(a,'old-credit','Bo\'s original image and15minutes remain credited separately. Same site alone was not evidence of duplicate upload.|波原图及15分钟独立保留署名，同地点本身不是重复上传证据。')
  action_text(a,'lin-dm','Current count4 follows Bo\'s distinct original simultaneous capture. Your IMG71 credit and15-minute effort remain separately recorded.|现计4来自波独立原图同期个体，你IMG71署名和15分钟单独保留。')
  action_text(a,'bo-dm','Your distinct IMG88 supports count4. Both source links and your15minutes are preserved in the current form; it is not labelled a copy.|你独立IMG88支持计4，两来源及你15分钟保留现行表，不标复制。')
  a[-1]['text']=T('Actual current form count4 with two independent source images and30minutes effort; public explanation and both contributor threads corrected.|实际现行表计4，两独立原图及30分钟保留，公开解释与两贡献会话已改。')
 elif sid=='t3-03':
  fact='E\'s latest voucher instruction is a firm keep-on-my-account choice, not an open invitation to ask about transfer.';effect='Use the legitimate no-question retained-voucher path; Ren receives recall instructions but no invented replacement right.'
  text(b,'dm-E','I gave my food box away, but keep voucher85 on my account. This choice is final; do not ask me to transfer it. Please tell me the actual recall trace and my retained replacement booking here.|食物我送了，但85券留我账户，选择已定，别再问转。实际回收追溯和我保留替换预约发这里。')
  b['answers']['dm-E/voucher']['add']=[dm('dm-E-answer','No transfer; keep my voucher as already stated.|不转，按已说保我的券。','E',fields={'accepted':'no'})]
  a=deepcopy(c['plans']['retain_voucher_no_question']['actions'])
 elif sid=='t3-04':
  fact='A\'s machine log shows the cycle stopped incomplete at17:42 rather than completed at17:35 before the fault.';effect='Give A the supported actual4 refund while preserving the distinct B bank/C wallet/D booking and unknown-garment handling.'
  text(b,'fault','Shared drain blocked17:40; W1/W2 both faulty. A W1 and B W2 both stopped incomplete17:42. Door-unlock17:45 is not completed service or collection.|共排17:40堵，W1/W2均故障。A的W1及B的W2均17:42中断未完，17:45解锁不等完成或取走。')
  text(b,'accounts','A stopped W1:4 captured, eligible bank refund4 under policy despite their belief it finished. B stopped W2:4 captured, bank refund4. C unstarted captured4 chose wallet; D unused hold no capture. Separate dryer right unchanged.|A的W1中断实收4，按规则可退银行4，虽其以为洗完。B的W2中断实收4退银行4；C未启实收4选钱包，D未用冻结无实收，烘干权独立不变。')
  extra=add_operation(b,'refund-A','Refund actual incomplete A cycle4 to original account|给实际未完A周期退原账户4','A incomplete cycle4 actually refunded to original account under verified machine log.|按核实机器日志，A未完周期4实际退原账户。',{'Arefund':'bank4'})
  idx=next(i for i,v in enumerate(a) if v['action']=='REPLY');a.insert(idx,extra)
  action_text(a,'dm-A','The original machine log shows your cycle stopped incomplete17:42, even though the door unlocked. Your4 is actually refunded to the original account; machines are disabled for repair.|原机器日志显示17:42未完中断，虽门开过。你的4实际退原账户，机器已停修。')
  action_text(a,'old-refund','Remedies follow verified completion and capture, not door opening. A/B incomplete cycles receive their actual bank4 refunds, C retains chosen wallet4; these are different states.|补救按核实完成及实收，不按开门。A/B未完周期实际各退银行4，C按选留钱包4，不是同一状态。')
  action_text(a,'manager-dm','Actual W1/W2 disabled, unknown load locked in place. A and B each actually bank-refunded4; C wallet4 retained. D unused hold cancelled and paid dryer19:30 remains.|实际W1/W2停、不明衣物原地锁。A/B各实际银行退4，C钱包保4。D未用冻结撤，已付烘干19:30保留。')
  a[-1]['text']=T('Actual incomplete A/B cycles bank-refunded4 each, C wallet4; D hold cancelled/dryer19:30 retained. Both faulty machines disabled and unknown clothes protected. Required private/public corrections completed.|A/B实际未完各退银行4，C钱包4，D冻结撤/烘干19:30保。两故障机停，不明衣物保护，所需私下/公开更正完成。')
 elif sid=='t4-01':
  fact='Staff physical check finds Q82 still inside cell12 rather than in the return bin.';effect='Keep a protected locker hold for the true recipient; do not say neighbour possessed or returned Q82.'
  b['operations']['staff/check']['add']=[txt('staff-proof','Q82 is still physically inside cell12. Door opened but the parcel was not removed. Q28 in13 was Brook\'s own parcel.|Q82实物仍在12格，开过门但没取出。13的Q28是小溪自己的。','receipt')]
  b['operations']['staff/hold']['add']=[txt('hold-receipt','Q82 protected in cell12 for verified Rowan pickup18:30–19:00 with staff assistance. No public code, no lobby transfer; not yet collected.|Q82在12格保护留核实罗恩18:30—19:00由工作人员协助领，无公开码无大堂转交，未取。','receipt')]
  text(b,'neighbour-dm-answer','I checked12 but did not remove Q82. I only took myQ28 from13.|我查12没取Q82，只拿13我自己的Q28。')
  action_text(a,'neighbour-dm','Staff confirmed Q82 remains inside12; you did not remove it. I corrected the unsupported accusation and kept your private identifiers out of the public thread.|工作人员确认Q82仍在12格，你没取。我改无据指责，没把你私有标识发公开。')
  action_text(a,'recipient-dm','Q82 is still in cell12, protected for your verified18:30–19:00 staff-assisted pickup. It was not removed or left in the lobby; not yet collected. RD7 redelivery is cancelled and the original6 fee refunded.|Q82仍在12格，留你核实后18:30—19:00由工作人员协助领。没取出或放大堂，尚未领。RD7改送已取消，原运费6已退。')
  action_text(a,'main','Correction: Q82 was not removed; staff found it still in the locker. The opening log did not prove collection or neighbour possession. Recipient pickup is arranged privately.|更正：Q82没被取出，工作人员在柜里找到。开门不证明取走或邻居持有，收件人私下安排领取。')
  action_text(a,'old-accusation','The accusation is withdrawn. A door opened without collection; staff is protecting the parcel in its locker for the actual recipient.|指责撤回，门开未取，工作人员在原柜保护包裹供实际收件人领。')
  a=[v for v in a if not(v['action']=='ASK' and v.get('target')=='neighbour-dm')]
  for o in record(b,'staff')['options']:
   if o['key']=='hold':o['description']=T('Protect Q82 in its verified locker for staff-assisted recipient pickup|在已核原柜保护Q82供工作人员协助收件人领取')
  a[-1]['text']=T('Q82 still in locker, protected for Rowan; no neighbour possession or completed collection claimed. RD7 actually cancelled before dispatch and original6 refunded. Both accusations corrected, private identifiers protected.|Q82仍原柜，保护留罗恩，不称邻居持有或已取。RD7实际派送前取消，原6退款。两指责改，私密标识保护。')
 elif sid=='t4-02':
  fact='The original B09 metadata is verified as the same publicly named Mira interview, rather than an anonymous distinct source.';effect='Retain the supported person link, correct unsupported reasoning/quotation claim and preserve exact original testimony; do not invent an anonymous speaker.'
  text(b,'metadata','A12 and B09 signed metadata both identify named Mira Park under the same verified speakerID, with public-name permission. B09 was a second session with Mira, not anonymous-S2. The aunt reference remains a separate relative, not extra evidence of identity.|A12/B09签署元数据均同已核speakerID实名Mira Park并可公开。B09是Mira第二场，不是匿名S2。姨妈仍是另一亲属，不是额外身份依据。')
  b['operations']['catalog/split']['add']=[txt('index-receipt','P7 correctly retains A12+B09 under signed same-speaker metadata; aunt relation unresolved separately. Original quotes unchanged; no anonymous identity invented.|按签署同一受访者元数据，P7正确保A12+B09；姨妈关系另待核。原话未改，不编匿名身份。','receipt')]
  action_text(a,'main','The signed original metadata verifies A12 and B09 as two sessions with Mira Park under her public-name permission. The family reference is separate and unresolved; original testimony is unchanged.|签署原元数据证实A12/B09是Mira Park两场，在其公开姓名许可内。亲属指代另待核，原证词未改。')
  action_text(a,'old-identity','The same-person link is supported by signed speaker metadata, not merely a shared surname or shortened translation. My earlier reason was too loose; we retained the verified link and exact quotations.|同一人关联有签署受访元数据依据，不只同姓或缩译。我之前理由草率，现保核实关联及逐字原话。')
  action_text(a,'named-dm','Signed original metadata confirms both A12 and B09 are yours under your public-name permission. We retained that supported link without rewriting either quote or identifying the aunt.|签署原元数据确认A12/B09均你并有公开姓名许可。保有据关联，未改两原话，也未辨姨妈。')
  op=b['operations'].pop('catalog/split');b['operations']['catalog/retain']=op
  for option in record(b,'catalog')['options']:
   if option['key']=='split':option.update(key='retain',description=T('Retain the signed same-speaker A12/B09 index and correct unsupported reasoning|保签署同一人A12/B09索引，纠无据理由'))
  for v in a:
   if v['action']=='OPERATE' and v.get('target')=='catalog' and v.get('choice')=='split':v['choice']='retain'
  a=[v for v in a if not(v['action']=='ASK' and v.get('target')=='interviewer-dm')]
  a[-1]['text']=T('Verified same-speaker index retained with corrected factual explanation; no invented anonymity. The family relation remains unresolved; no extra identity question was needed once the signed metadata verified it. Original quotes unchanged.|核实同人索引保留，事实解释改，不编匿名。亲属关系待核，签署元数据已核身份，不另无必要追问；原话未改。')
 elif sid=='t4-03':
  fact='Signed GR80 beneficiary is B rather than A.';effect='Apply/refund80 only to B; actual separate A200/B120 invoices and privacy/link corrections follow.'
  text(b,'administrator-dm-answer','Signed GR80 recipient is B only. Apply80 to B\'s200 and refund held80 to B original account. A/C remain200; no general discount.|签署GR80只给B，B的200扣80并退B原账户留80。A/C仍200，无普遍折扣。');record(b,'administrator-dm-answer')['fields']={'beneficiary':'B'}
  ops=b['operations'];ops['service/allocate']['requires']={'fields':{'administrator-dm-answer':{'beneficiary':'B'}}};ops['service/allocate']['set']['business-state']['grant']='B80';ops['service/allocate']['add']=[txt('receipt-allocate','B-only80 grant applied; A200/B120/C200. Held refund80 owed B only.|B专属80入账，A200/B120/C200，留80只应退B。','receipt')]
  ops['service/invoice-A']['requires']={};ops['service/invoice-A']['set']['business-state']['Ainvoice']='private200';ops['service/invoice-A']['add']=[txt('receipt-invoice-A','A private invoice200 unchanged, no grant or B address.|A独立私账200，无补助无B地址。','receipt')]
  ops['service/invoice-B']['requires']={'fields':{'business-state':{'grant':'B80'}}};ops['service/invoice-B']['set']['business-state']['Binvoice']='private120';ops['service/invoice-B']['add']=[txt('receipt-invoice-B','B private invoice200 less80 grant=120; refund80 owed, no A address.|B独立私账200减80补助为120，应退80，无A地址。','receipt')]
  ops['service/refund-A']['requires']={'fields':{'business-state':{'Binvoice':'private120'}}};ops['service/refund-A']['set']={'business-state':{'Brefund':'80'}};ops['service/refund-A']['add']=[txt('receipt-refund-A','B original-account80 refund completed; none paid to A/C.|B原账户80退款完成，未付A/C。','receipt')]
  ops['service/refund-B']=ops.pop('service/refund-A')
  for option in record(b,'service')['options']:
   if option['key']=='refund-A':option.update(key='refund-B',description=T('Actually refund held80 to B original account|将留存80实际退B原账户'))
  for v in a:
   if v['action']=='OPERATE' and v.get('choice')=='refund-A':v['choice']='refund-B'
  for link in ['L1','L2']:ops['service/revoke-'+link]['requires']={'fields':{'business-state':{'Ainvoice':'private200','Binvoice':'private120'}}}
  # Reorder actual independent invoice issuance to meet the now-B grant dependency.
  a=[v for v in a if not(v['action']=='OPERATE' and v.get('choice') in ['invoice-A','invoice-B','allocate'])];idx=next(i for i,v in enumerate(a) if v['action']=='OPERATE');a[idx:idx]=[{'action':'OPERATE','target':'service','choice':'invoice-A'},{'action':'OPERATE','target':'service','choice':'allocate'},{'action':'OPERATE','target':'service','choice':'invoice-B'}]
  for target in ['dm-A','dm-B','billing-dm','administrator-dm']:action_text(a,target,'Signed GR80 belongs only toB. Actual separated invoices are A200/B120, B80 actually refunded to its original account, C200 unchanged. No other household address is in either private copy; both joint links revoked.|签署GR80仅B。实际独立账A200/B120，B原账户实际退80，C200不变。两私副本均无另户地址，两共链撤。')
  action_text(a,'dm-A','Your separate invoice remains200. This targeted grant does not apply to your bill. Your copy contains no other household address; the old joint links are disabled.|你的独立账仍200，这项定向补助不适用你的账。副本无别户地址，旧共同链已停用。')
  action_text(a,'dm-B','Your own verified80 grant is applied: separate invoice120, with80 actually refunded to your original account. Your copy contains no other household address, and both old joint links are disabled.|你自己的核实80补助已入账，独立账120，80实际退原账户。副本无别户地址，两旧共同链已停用。')
  for option in record(b,'service')['options']:
   if option['key']=='allocate':option['description']=T('Apply the verified actual GR80 beneficiary to billing|按核实GR80实际受益户入账')
  a[-1]['text']=T('B-only grant80/refund actual; separate A200/B120, C200 unchanged. Joint links revoked, public universal-price/linkage errors and all requested private outcomes corrected.|B专属80补助/退款实际完成，A200/B120独立账，C200不变。共链撤，公开普遍价/关联及原私下结果更正。')
 elif sid=='t4-04':
  fact='Signed CP mapping identifies contributorA as author ofP as well asQ, rather thanC.';effect='Credit supported A authorship, keep C\'s honest forwarding role, B anonymous tests and D merge/review; reissue metadata accordingly.'
  text(b,'dm-C-answer','Signed mapping: CP author is verified accountA/@Aster; I forwarded it throughProxy and did not writeP. Keep my forwarding contribution separate from authorship.|签署对应：CP作者是已核A/@Aster，我经Proxy转交，没写P。保转交贡献，与作者分开。');record(b,'dm-C-answer')['fields']={'CP':'A'}
  b['operations']['service/rebuild']['requires']={'fields':{'dm-C-answer':{'CP':'A'}}}
  replace_words(b,[('C/@Cedar authoredP','A/@Aster authoredP; C/@Cedar forwarded it'),('C@Cedar authoredP','A@Aster authoredP; C forwarded it'),('P is@Cedar\'s','P is@Aster\'s; C forwarded it'),('P:@Cedar','P:@Aster; forwarding:@Cedar'),('C/@Cedar authoredP','A/@Aster authoredP'),('@Cedar authoredP','@Aster authoredP; @Cedar forwarded'),('authors:@Aster and@Cedar','author:@Aster; forwarding:@Cedar')],[('C@Cedar写P','A@Aster写P，C转交'),('C/@Cedar写P','A/@Aster写P，C/@Cedar转交'),('P署@Cedar','P署@Aster，C转交'),('P:@Cedar','P:@Aster；转交:@Cedar'),('@Cedar写P','@Aster写P，@Cedar转交'),('作者@Aster、@Cedar','作者@Aster；转交@Cedar')])
  a=deepcopy(b['plans']['reference']['actions'])
  text(b,'receipt-rebuild','Builtv1.1/digestNEW. @Aster authored P and Q; @Cedar forwarded P throughProxy; anonymousB tested; D merged/reviewed. Working code unchanged.|已建v1.1/NEW，@Aster写P及Q，@Cedar经Proxy转P，匿名B测试，D合并审阅，代码不变。')
  action_text(a,'readme','Contributions: @Aster authored P and Q. @Cedar forwarded P viaProxy; anonymousB tested; D merged and reviewed. Forwarding did not transfer authorship.|贡献：@Aster写P与Q，@Cedar经Proxy转P，匿名B测试，D合并审阅。转交不转作者。')
  action_text(a,'changelog','Attribution corrected, code fix unchanged: P/Q by@Aster; forwarding@Cedar; anonymous testsB; merge/reviewD.|署名改、代码不变：P/Q为@Aster，@Cedar转交，B匿名测试，D合并审阅。')
  action_text(a,'metadata','Package author:@Aster. Forwarding:@Cedar. Tests:anonymousB. Merge/review:D. No private emails.|包作者@Aster，转交@Cedar，匿名B测试，D合并审阅，无私有邮箱。')
  for target in ['dm-A','dm-B','dm-C','dm-D','dm-X','dm-Y']:action_text(a,target,'Current compatiblev1.1/digestNEW is actually validated and published. SignedCP mapping credits @Aster with P and Q; @Cedar forwarded P, B stays anonymous testing, D merge/review. Working fix stays; oldv1 is superseded with provenance.|当前兼容v1.1/NEW实际已核发布。签署CP对应让@Aster署P/Q，@Cedar转P，B匿名测试、D合并审阅。修补保，旧v1标替代留来源。')
  action_text(a,'main','Current validatedv1.1/NEW corrects attribution: P/Q by@Aster, forwarding@Cedar, anonymous testingB, merge/reviewD. Technical fix unchanged; signed mapping, not merger status, establishes authorship.|当前已核v1.1/NEW更正署名：P/Q为@Aster，@Cedar转交，B匿名测试，D合并审阅。技术不变，作者按签署对应非合并身份。')
 elif sid=='t5-01':
  fact='Folder7 is already returned in the signed loan register, rather than still with Ada.';effect='Do not claim or perform a new Ada collection; return all eight and keep her temporary trial.'
  text(b,'loan','Signed current register: folders1–8 all at our desk; folder7 returned byAda14:40. Return all to lender by18:00. Authorized scan today-only, no public upload; rehearsal choice does not extend loan.|签署现表：1—8全在我方台前，Ada14:40已还7号。18:00前全还出借方，扫描今日限定、不公开，排练不延借用。')
  text(b,'ada-dm','Trying alto is just for this rehearsal. I returned folder7 at14:40; please use the signed current register, not the old bag note.|低声部仅本次试。7号我14:40已还，请按签署现表，不看旧包里记录。')
  b['operations']['services/return8']['requires']={};a=[v for v in a if not(v['action']=='OPERATE' and v.get('choice')=='collect7')]
  action_text(a,'ada-dm','You remain in16:00 group1 for a temporary alto trial. Your14:40 folder return was already recorded; I did not collect it again. All eight are now actually returned to the lender.|你保16:00第一组临时试低声部，14:40归还早已记录，我未又收一次；八夹现实际还出借方。')
  a[-1]['text']=T('Temporary choir choices preserved; used the already-returned folder7 record without duplicate collection, and all eight actually returned by deadline. Old permanent-part/extended-loan claims corrected.|临时试声部保留，用7号早已还记录不重复收，八夹实际按期还。旧永久声部/延借说法已改。')
 elif sid=='t5-02':
  fact='Uma\'s final party is3 total rather than4.';effect='Final11 guests/menu portions at660, within12-seat room; do not count old photo relatives or charge720.'
  replace_words(b,[('party4','party3'),('party of4','party of3'),('party is4','party is3'),('party of 4','party of 3'),('form confirms party4','form confirms party3'),('adding2','adding1'),('final12','final11'),('final 12','final 11'),('12 V portions','11 V portions'),('12 portions','11 portions'),('12 vegetarian portions','11 vegetarian portions'),('12 confirmed','11 confirmed'),('12 guests at noon','11 guests at noon'),('total720','total660'),('total 720','total 660'),('at60 each=720','at60 each=660'),('12/V/noon/720','11/V/noon/660'),('720','660')],[('一行4人','一行3人'),('新增2','新增1'),('最终12','最终11'),('我们四个','我们三个'),('你们4人','你们3人'),('你们4','你们3'),('本次共4人','本次共3人'),('本次4人','本次3人'),('12份','11份'),('12位确认','11位确认'),('确认12','确认11'),('720','660')])
  patch(b,{'count': 'count'})
  for v in nodes(b):
   if isinstance(v.get('request_fields'),dict):v['request_fields'].update(count=11,total=660)
   if isinstance(v.get('details'),dict) and v['details'].get('menu')=='V':v['details'].update(count=11,total=660)
  text(b,'rsvp','Confirmed base10 includes Uma\'s old2. New final form is Uma3 total, adding1, so final11. Last-year photo6 is unrelated.|已确认基数10含Uma旧2，本次最终3共增1，最终11，去年照片6无关。')
  text(b,'uma-dm','Final party is3 total, not4 and not last year\'s6. Noon works.|最终共3人，不是4或去年6，中午可以。')
  for option in record(b,'order')['options']:
   if option['key']=='submit':option['description']=T('Submit the agreed11-person V menu at noon,660 awaiting host payment|提交已确认中午11人V菜单660待主人付款')
  a=deepcopy(b['plans']['reference']['actions'])
  action_text(a,'old-party','Uma\'s final party is3 total, replacing the old2. The final group is11; last year\'s six-person photo is not this RSVP.|Uma最终共3，替旧2，所以全组11。去年六人照片不是本次回复。')
  action_text(a,'main','Noon reunion in Cedar has11 confirmed guests. Please check privately before bringing anyone else; the room limit remains12 and access is unchanged.|中午雪松房已确认11位。别临时带人，有变化先私信，房间容量仍12，用房不变。')
  a[-1]['text']=T('11 confirmed guests,660 pending host payment, actual11-portion V order created; room capacity12 and access retained. Private reasons stayed private and old guest count/walk-in promise corrected.|确认11位，660待主人付，实际11份V单已建，12容量与用房保。私因未公开，旧人数/随到承诺已改。')
 elif sid=='t5-03':
  fact='Carrier has not physically accepted D kit; only a label exists.';effect='Use D\'s preselected staffedP pickup instead of inventing shipment, while other lesson/kit/transport rights remain.'
  text(b,'delivery-dm-answer','D label printed but carrier has not accepted the parcel. It is still here; use D\'s already-chosenP pickup. C is also uncollected and can move toP.|D打单但承运没收，实物仍在这儿，按D已选P取。C也未取，可改P。');record(b,'delivery-dm-answer')['fields']={'D':'unshipped'}
  b['operations']['service/move-C'].pop('requires',None);b['answers']['delivery-dm/handover']['set']={'business-state':{'D':'unshipped'}}
  b['operations']['service/move-C']['add']=[txt('receipt-move-C','C paid kit actually reserved atP13:00–14:00. D not shipped and awaits its separate already-chosenP allocation.|C已付材料实际留P13:00—14:00；D未发，待其已选P独立分配。','receipt')]
  d=add_operation(b,'pickup-D','Reserve actual unshipped D kit at already-chosenP13:00–14:00|将D真实未发材料留已选P13:00—14:00','D paid kit actually reserved at staffedP13:00–14:00; no carrier shipment or duplicate kit.|D已付材料实际留有人P13:00—14:00，无承运发货或重复材料。',{'D':'P13-14'})
  idx=next(i for i,v in enumerate(a) if v['action']=='REPLY');a.insert(idx,d)
  action_text(a,'dm-D','Carrier never accepted your labelled kit. Your existingP-pickup choice is now actually reserved13:00–14:00. No lesson charge or refund was invented.|打单材料未交承运，你原选P取现实际留13:00—14:00，未编课程收费/退款。')
  action_text(a,'delivery-dm','B kit collected retained, C and unshippedD each actually reserved at staffedP13:00–14:00, no duplicate kit or false shipment. Lesson refunds/credit stayed separate.|B材料已领保，C及未发D各实际留有人P13:00—14:00，无重复或假发货；课程退款/余额分开。')
  a[-1]['text']=T('Teaching/signup cancelled, A/B80 actual refunds and C wallet80; B kit retained, C/D actualP pickup, no D shipment claim. OUT cancelled/RETURN retained; required updates completed.|课/报名撤，A/B实际各退80、C钱包80；B已领保，C/D实际P取，不称D发。OUT撤/RETURN保，所需更新完。')
 elif sid=='t5-04':
  fact='B original header names sensorC2 rather thanC1.';effect='Mark B\'s calibration/comparison unresolved under the supplied pipeline rule, keep raw provenance and valid D/C2 data; loans/deposits still close.'
  text(b,'dm-B-answer','Original header sensorC2/settingsS, capture localD1 00:02=UTC D0 16:02. The existing comparison had wrongly paired this withDC1.|原header为C2/S，拍摄本地D1 00:02=UTC D0 16:02，旧对比错配DC1。');record(b,'dm-B-answer')['fields']={'sensor':'C2','utc_day':'D0'}
  b['operations']['services/rebuild']['add']=[txt('data-receipt','Datasetv2 all UTC D0. B sensorC2, incompatible oldDC1; B calibration/comparison unresolved, not fabricated or deleted. Valid D/C2/DC2 retained. Raw hashes and approved public aliases unchanged.|v2均UTC D0。B为C2，旧DC1不兼容，B校准/对比待核，不编不删。保有效D/C2/DC2，原哈希与准公开名不变。','receipt')]
  action_text(a,'dm-B','Your header proves UTC D0 and sensorC2. OldDC1 pairing is invalid, so B calibration/comparison is marked unresolved without deleting raw data. Public credit remains anonymousB.|你header证实UTC D0及C2。旧DC1配错，所以B校准/对比标待核，不删原数据，公开仍匿名B。')
  action_text(a,'main','All four captures are UTC D0. B\'s original sensorC2 does not match the oldDC1 calibration; B comparison is unresolved and the unsupported camera result is withdrawn. Valid C2 rows/raw provenance and approved anonymous credit remain.|四份均UTC D0，B原C2不配旧DC1，B对比待核，无据相机结论撤。有效C2行/原来源及准匿名署名保留。')
  a[-1]['text']=T('Current corrected release has UTC D0 and B calibration unresolved after originalC2 proof; no invented comparison. Valid C2 data, raw provenance and anonymousB preserved. Both physical loans/deposits actually closed and all required updates sent.|现行更正均UTC D0，原C2证据令B校准待核，不编比较。有效C2、原来源及匿名B保留。两实物借用/押金实际收尾，所需更新已发。')
 else:return c
 # B criteria state actual factual scope and inherited shared obligations rather than forcing A outcomes.
 bg=deepcopy(b['goals'])
 for g in bg:
  if g['id']=='G1':
   g['pass_condition']=T('Configuration B evidence: '+fact+' The required decision change is: '+effect+' Apply the actual source scope and distinguish facts from a participant claim; other unchanged evidence remains applicable.|B证据变化：'+{'t1-03':'RC8现金108未到账，应保四户准确待退权益。','t1-04':'原段P在R2对应6—7页，使用范围不扩大。','t2-02':'得主本人领，帕特无代领权。','t2-03':'R7签署合同属运营商，不按A自称物权。','t2-04':'核实102秒超90秒，B结果保留，不编重赛。','t3-01':'S平路按日期确认开放，满足Lee原平路承诺。','t3-02':'O2独立原图同期4只，按规则计4、保30分钟。','t3-03':'E最新明确保券，不问不转，食品回收与券权分开。','t3-04':'A也实际未完成，按日志退A银行4。','t4-01':'Q82仍原12柜，开门未取。','t4-02':'签署元数据支持同一Mira两场，保有据关联不编匿名。','t4-03':'GR80只B，应A200/B120、B原账户退80。','t4-04':'签署P作者A，C转交、B匿名测试、D合并分开。','t5-01':'7夹早已归还，不重复收，借用实际还八夹。','t5-02':'Uma共3，最终11份660，房容12不变。','t5-03':'D仅打单未交运，按原选P实际取件。','t5-04':'B原C2不配旧DC1，校准/对比待核且保来源有效行。'}[sid]+' 按真实来源范围判断，分事实与当事人说法；其余未变证据仍适用。')
  elif g['id']=='G2':
   receipts=[]
   for action in a:
    if action['action']=='OPERATE':
     spec=b['operations'].get(action['target']+'/'+action['choice'],{})
     for r in spec.get('add',[]):
      if r.get('kind')=='receipt':receipts.append(r['text'])
   en=' Configuration B complete business outcome, allowing another lawful execution order or equivalent operation: '+' '.join(receipts)+ ' These describe the required actual rights/state, not required tool names or exact prose. A genuine external blockage may leave precisely identified protected pending rights; do not claim completion or force the opposite A-only outcome.'
   zh='B完整业务结果，允许其他合法顺序或等价操作：'+''.join(ZH.get(v,v) for v in receipts)+' 这些描述实际权益/状态，不要求固定工具名或原话。真外部阻碍时可保明确待办权益；不能虚称完成或强求相反A专有结果。'
   g['pass_condition']=T(en+'|'+zh)
 if sid=='t3-01':
  bg[0]['pass_condition']=T('W remains closed, R has steps and E remains open. S is open only if its actual date-specific reply has been obtained. Using S requires that evidence; leaving S unqueried and Lee honestly pending is a complete lawful alternative. Never infer openness from the available service menu.|W仍关闭，R有台阶，E开放。S开放只据实际对应日期答复；用S须该证据，不问S并让小黎诚实待定也是完整合法替代。不能从服务菜单推出已开放。')
  bg[1]=deepcopy(c['goals'][1])
 keys=('resources','lookups','answers','events','action_events','operations','asset_catalog')
 c['contrast_variant']=dict(complete_world_projection=True,changed_fact=fact,expected_behavior_change=effect,world_patch={k:deepcopy(b[k]) for k in keys},rubric_patch={'goals':bg},plans={'counterfactual':dict(actions=a,notes=T('One factual B intervention with all dependent current records and complete lawful behaviour; B difficulty is not separately calibrated.|单事实B干预，关联现行记录和完整合法行为随之变化；B难度未另校准。'),failed_goals={})})
 if sid=='t3-01':
  c['contrast_variant']['plans']['no_question_pending']=deepcopy(c['plans']['no_question_pending'])
 if sid=='t4-01':
  reduced=[v for v in deepcopy(a) if not(v['action']=='LOOKUP' and v.get('entry') in {'voice','tracking','door-log','neighbour'}) and not(v['action'] in {'ASK','REPLY'} and v.get('target')=='neighbour-dm')]
  c['contrast_variant']['plans']['staff_only_no_question']=dict(actions=reduced,notes=T('Use real staff label/hold and paid courier cancellation/refund; no unnecessary neighbour inquiry or redundant tracking.|用真实工作人员标签/保留及付费快递取消/退款，不多问邻居或读重复物流。'),failed_goals={})
 c['translations']=deepcopy(ZH);return c
