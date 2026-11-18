"""Second prospectively reviewed v1.1 increments after legal R1 pruning."""
from copy import deepcopy
from itertools import permutations
from authoring import T,ZH,txt,operate
IDS={'t3-03','t4-03','t4-04','t5-04'}
def apply(c,branch):
 if c['short_id']not in IDS:return c
 def find(rid):return next(r for r in c['resources']+[r for rs in c['lookups'].values()for r in rs]if r['id']==rid)
 def extend(rid,value):
  en,zh=value.split('|',1);r=find(rid);old=r['text'];r['text']=T(old+' '+en+'|'+c['translations'].get(old,ZH.get(old,old))+' '+zh)
 def goal(i,value):
  en,zh=value.split('|',1);old=c['goals'][i]['pass_condition'];c['goals'][i]['pass_condition']=T(old+' '+en+'|'+c['translations'].get(old,ZH.get(old,old))+' '+zh)
 def require(choice,fs):c['operations']['service/'+choice].setdefault('requires',{}).setdefault('fields',{}).setdefault('state',{}).update(fs)
 def add(key,title,params,updates,requires):
  schema={k:{'type':'number'if type(v)in(int,float)else'string'}for k,v in params.items()};find('service')['options'].append({'key':key,'description':T(title),'param_schema':schema})
  c['operations']['service/'+key]={'param_schema':schema,'param_values':deepcopy(params),'parameter_record':{'resource':'state','field':key+'_submission','field_map':{}},'requires':requires,'set':{'state':updates},'add':[txt('result-'+key,'The external service completed the submitted transaction. Its exact order, object and destination remain in this receipt.|外部服务已完成所提交交易，回执保留准确订单、对象和去向。','receipt')]};return operate('service',key,**params)
 sid=c['short_id'];state=find('state')['fields'];pickup='13:50'if branch=='A'else'14:50'
 if sid=='t3-03':
  pickup='13:50'if branch=='A'else'14:50';state['S21']='13:00_old_pier'
  c['answers']['support-dm/confirm']['not_before']=20 if branch=='A'else 40
  _log=find('lock-log');_old=_log['text'];_log['text']=T("A lock beep was logged, but the app has not produced a closed-ride receipt. Support will verify the actual dock-return event; a beep is not its timestamp.|A锁响已有记录，应用还没出结束回执。客服将核实实际还桩事件，锁响不等于其时刻。")
  extend('transfer','A also already paid shuttle operator ShoreVan for S21, a separate feeder booking, originally13:00 to West Pier. The verified bike return is later than13:00, so this pickup is no longer usable. Existing no-fee rebooking permits13:50 to East Pier for H21 at14:00, or 14:50 to East Pier for H21 at15:00. The operator issues an actual amended S21 record; the ferry issuer cannot change it. R21 remains separate.|A还已向接驳运营ShoreVan付S21，原13:00到West Pier，是另一张接驳单。核实还车晚于13:00，原接车不可用。既有免费改约允许H21 14:00配13:50到East Pier，或H21 15:00配14:50到East Pier。接驳方给实际改约S21回执，轮渡出票方不改这单；R21另保留。')
  extend('traveller-dm','My existing instruction authorises the matching no-fee S21 feeder change to East Pier once I accept H21. Send me the actual amended pickup, not a promise; please leave R21 alone.|我原有指示授权在接受H21后，免费改对应S21到East Pier。发实际已改的接车时段，别只承诺；R21不动。')
  new=add('amend-S21','Amend actual prepaid feeder S21 with ShoreVan|向ShoreVan实改已付接驳S21',{'booking':'S21','passenger':'A','pickup':pickup,'destination':'East Pier','extra_cost':0},{'S21':pickup+'_East_Pier'}, {'revealed':['result-issue-H21'],'fields':{'traveller-dm-answer':{'confirmed':True}}});before='compensate';drop=['lock-log'];omit_reply='carrier-dm'
  goal(1,'Actually amend the separate prepaid feeder S21 to the accepted H21 time and East Pier; a ferry ticket does not update another operator’s booking.|按所选H21时刻与East Pier实改独立已付接驳S21，轮渡票不更新另一运营方预约。')
  c['goals'][4]['pass_condition']=T('Repair the main post and two original answers, and privately give each traveller their own actual result without publishing account or payment details. The carrier’s issue/refund receipts already transact its outcome; a separate courtesy acknowledgment is optional.|修主帖及两条旧答复，私下各给旅客实际结果，不公开账户付款细节；承运方出票退款回执已传达业务结果，另发礼节确认可省。')
 elif sid=='t4-04':
  state['X7_public_export']='live'
  extend('cloud','Export record X7 is a separate complete copy of that memory material already exported to our own public archive. It remains publicly served when M7 is revoked. We own the archive and may delete X7 directly by its record ID without opening any content; P8 must remain. The token service does not control this separate archive object.|导出记录X7是存储内容已另行导出到我方公开存储的完整副本，撤M7仍会公开服务。存储归我方，可按记录ID直接删X7，不必打开内容；P8保留。令牌服务不控制这个独立存储对象。')
  new=add('delete-X7','Delete actual public-archive export X7 without opening it|不开内容即实删公开存储导出X7',{'archive':'our-public-archive','export':'X7'},{'X7_public_export':'deleted'},{});before='seal-camera';drop=['chronology','photo-chain'];omit_reply=None
  goal(2,'Actually delete independent public-archive copy X7 without opening memory content. Revoking token M7 alone leaves X7 public; retain licensed P8.|不开存储内容而实删独立公开副本X7，只撤M7仍留X7公开，获准P8保留。')
 elif sid=='t4-03':
  state['D31_reservations']='A01,B01,C01_locked'
  extend('orders','Existing deal D31 still holds platform reservations on A01, B01 and C01, even if the physical cards return. These are the original deal’s reservations, not a new trade. All owners’ accepted exit terms require actual closure and one batch release after restoration; the platform record is independent of the return desks and escrow bank.|原交易D31仍在平台锁定A01、B01、C01，实物还回不自动解预留。这是原交易预留，不是新交换。三人的已接受退场条件要求全恢复后真实关闭并一次批量解锁；平台记录独立于归还台和托管银行。')
  new=add('close-D31','Close original D31 and release its three reservations in one batch|关闭原D31并一次释放三份预留',{'deal':'D31','release':'A01,B01,C01'},{'D31_reservations':'closed_all_released'},{'fields':{'state':{'A_restored':True,'B_restored':True,'C_restored':True}}});before='refund-A';drop=['postal','locker'];omit_reply=None
  _close=c['operations']['service/close-D31'];_close['param_values'].pop('release');_close['param_variants']=[{'param_values':{'release':','.join(order)}}for order in permutations(['A01','B01','C01'])]
  for name in ['refund-A','refund-B','refund-C']:require(name,{'D31_reservations':'closed_all_released'})
  goal(3,'After all physical restorations, actually close original platform deal D31 and release all three reservations in one batch, then settle escrow. Physical receipt does not release the independent trading locks.|实物全恢复后实关原平台交易D31，一次释放三预留，再结托管；实物签收不会释放独立交易锁。')
 elif sid=='t5-04':
  state['G82']='warehouse_inbound'
  extend('orders','Paid T82 is the tent-and-groundsheet bundle. The tent is at our counter, but its already-paid groundsheet G82 is still inbound separately from warehouse consignment W82. No new purchase is needed. Our counter must actually receive and inspect G82 in one service before handing the complete T82 bundle to its authorised collector; the tent credential or tent scan does not prove a warehouse receipt.|已付T82为帐篷加地布整套。帐篷已在台前，已付地布G82仍由仓库W82独立送来，不需新采购。柜台须一次服务实收查验G82后才把完整T82交获准领取人，帐篷码或帐篷扫码不证明仓库收件。')
  new=add('receive-W82','Receive and inspect actual paid G82 from warehouse W82 once|一次实收查验仓库W82已付G82',{'consignment':'W82','order':'T82','item':'G82','quantity':1},{'G82':'counter_accepted'},{});before='T82-scan';drop=['old-authority'];omit_reply=None
  require('T82-scan',{'G82':'counter_accepted'});c['operations']['service/T82-scan']['set']['state']['G82']='delivered_with_T82'
  goal(2,'T82 completion means the paid tent and G82 groundsheet actually handed over together. Obtain the independent W82 warehouse receipt/inspection before the bundle scan; do not call tent-only collection complete.|T82完成须已付帐篷与G82地布实交整套，整套扫码前取得独立W82实收查验，不把仅领帐篷当完成。')
 for name,p in c['plans'].items():
  actions=p['actions'];idx=next(i for i,a in enumerate(actions)if a.get('choice')==before);actions.insert(idx,deepcopy(new))
  if name!='reference':actions[:]=[a for a in actions if a.get('entry')not in drop and not(omit_reply and a.get('action')=='REPLY'and a.get('target')==omit_reply)]
  if sid=='t3-03'and name=='strong_simplification':actions[:]=[a for a in actions if a.get('entry')!='duplicate']
  for a in actions:
   if a.get('action')=='REPLY'and a.get('target')=={'t3-03':'traveller-dm','t4-04':'desk-dm','t4-03':'a-dm','t5-04':'buyer-dm'}[sid]:
    en,zh={'t3-03':('Your prepaid S21 is amended to '+pickup+' pickup to East Pier.','你的已付S21已改为'+pickup+'接车、送至East Pier。'),'t4-04':('The independent public export X7 is deleted.','独立公开副本X7已删除。'),'t4-03':('D31 is closed and the three platform reservations are released.','D31已关闭，三份平台预留已释放。'),'t5-04':('The T82 handover included its paid G82 groundsheet received under W82.','T82实交包含已按W82实收的已付G82地布。')}[sid];old=a['text'];a['text']=T(old+' '+en+'|'+c['translations'].get(old,ZH.get(old,old))+' '+zh)
 c['translations'].update(ZH);c['v11_followup_note']='新增业务事实；旧世界R1合法25/26步仍保留。';return c
