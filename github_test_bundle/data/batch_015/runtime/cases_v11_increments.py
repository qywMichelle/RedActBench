"""Prospectively approved v1.1 facts; v1.0 legal 25-call worlds remain valid."""
from copy import deepcopy
from authoring import T,ZH,txt,operate

IDS={'t1-04','t2-03','t2-04','t3-04'}

def apply(c,branch):
 if c['short_id'] not in IDS:return c
 def find(rid):
  return next(r for r in c['resources']+[r for rs in c['lookups'].values() for r in rs] if r['id']==rid)
 def extend(rid,value):
  en,zh=value.split('|',1);r=find(rid);old=r['text'];r['text']=T(old+' '+en+'|'+c['translations'].get(old,ZH.get(old,old))+' '+zh)
 def replace(rid,value):find(rid)['text']=T(value)
 def requirement(choice,fields):
  c['operations']['service/'+choice].setdefault('requires',{}).setdefault('fields',{}).setdefault('state',{}).update(fields)
 def add(key,description,params,updates,requires):
  schema={k:{'type':'number' if type(v)in(int,float)else 'string'}for k,v in params.items()}
  find('service')['options'].append({'key':key,'description':T(description),'param_schema':schema})
  c['operations']['service/'+key]={'param_schema':schema,'param_values':deepcopy(params),'parameter_record':{'resource':'state','field':key+'_submission','field_map':{}},'requires':requires,'set':{'state':updates},'add':[txt('result-'+key,'The external service executed this submitted card. The receipt retains its exact object, destination and amount.|外部服务已执行本次提交卡；回执保留准确对象、去向和金额。','receipt')]}
  return operate('service',key,**params)
 sid=c['short_id'];state=find('state')['fields'];new=None;before=None
 if sid=='t1-04':
  lot='S22'if branch=='A'else'R22';state['physical_labels']='H07_ornamental'
  c['task']=T(c['task']+' The packing desk has already attached the old H07 ornamental labels to all three outer bags; have the physical labels replaced before carrier tender, as well as fixing the online guide.|'+c['translations'][c['task']]+' 打包台已把旧H07观赏藤标签贴上三个外袋；交承运前须换实物标签，也修线上指南。')
  extend('old-label','Packing record P-L7: the old H07 labels are physically on the current three outer bags. The independent packing-label service replaces all three in one batch from a submitted lot/destination card, using serial>recipient on each job row; carrier tender does not print or replace labels.|打包记录P-L7：旧H07标签已贴在当前三个外袋。独立标签台可按提交的批号去向卡（每行用serial>recipient）一次批量换三份；承运交接不印标或换标。')
  params={'S11':'S11>C','S33':'S33>B',lot:lot+'>A'}
  new=add('replace-labels','Replace all three actual outer labels in one batch|一次批量更换三份实际外袋标签',params,{'physical_labels':'current_serial_route'}, {'revealed':['result-amend-order'],'fields':{'state':{'released_lot':lot}}})
  requirement('handover',{'physical_labels':'current_serial_route'});before='handover'
  c['goals'][2]['pass_condition']=T(c['goals'][2]['pass_condition']+' Replace the actual three H07 outer labels with the accepted current lots and destinations before tender.|'+c['translations'][c['goals'][2]['pass_condition']]+' 交运前把三个实物H07外袋标签换为获准当前批次及去向。')
 elif sid=='t2-03':
  repairable=branch=='A';state.update(inspection_deposit=20,repair_reserve=100,inspection_account='open')
  extend('technician-dm','Original paid receipt D20: seller paid this desk20 for inspecting J317 before this task. The agreed120 repair total includes that20. After actual working-unit acceptance the cashier collects only the remaining100; if the standing return remedy completes, the cashier returns the unused20 to the original repair reserve. The technical work order cannot settle this separate cashier account.|原已付凭据D20：任务前卖家已向本台付J317检查款20；约定修理总价120包含此20。工作机实际验收后收银台只收余款100；若原退货补救完成，收银台把未用20实退原维修专款。技术工单不结这个独立收银账户。')
  replace('funds','Separate authorised balances: sale return fund800; temporary-hire remedy reserve120; repair reserve originally120, of which inspection receipt D20 already paid20 and100 remains. Carrier receipt V40 records Uma personally paid40 on D0 to deliver faulty J317 to the technician. V40 is transport only and is not charged on the H24 daily hire invoice. Reimburse V40 once to Uma. Do not use the sale refund or Uma own advance as repair cash.|分开授权资金：销售退货专款800、临时租借补救120、维修专款原120，其中检查凭据D20已付20、余100。承运凭据V40记Uma在D0自己付40把故障J317送维修台；V40只运送，不计H24日租账单。V40只向Uma退一次，不拿销售退款或Uma自垫当维修款。')
  next(o for o in find('service')['options']if o['key']=='reimburse')['description']=T('Reimburse Uma’s documented V40 delivery advance|退Uma有凭据的V40送机垫款')
  extend('hire-contract','Transport receipt V40 is a separate D0 delivery paid by Uma to courier VanCo, not a prepayment to the H24 hire owner. H24 has no credit from V40.|运送凭据V40为Uma在D0付承运VanCo的送机费，不是向H24出租方预付，H24没有V40抵扣。')
  new=add('settle-inspection','Settle the actual D20 inspection account net of its paid credit|按已付抵扣结D20实际检查账户',{'receipt':'D20','direction':'pay_balance'if repairable else'refund_unused','amount':100 if repairable else 20,'account':'repair-reserve'}, {'inspection_account':'settled','inspection_deposit':0,'repair_reserve':0 if repairable else 120}, {'revealed':['result-accept'if repairable else'result-sale-refund']});before='hire-return'
  for r in [r for rs in c['lookups'].values()for r in rs]+[r for a in c['answers'].values()for r in a.get('add',[])]:
   if 'text'in r and ('hire advance'in r['text']or 'separately evidenced'in r['text']):
    old=r['text'];r['text']=T(old.replace('hire advance','delivery advance').replace('separately evidenced40 advance','documented V40 delivery advance')+'|'+c['translations'].get(old,ZH.get(old,old)).replace('租借垫款','送机垫款'))
  c['goals'][3]['pass_condition']=T('Keep the sale refund, H24 daily invoice, V40 delivery reimbursement and D20 inspection cash separate. Settle the net D20 balance100 after accepted repair, or actually recover its unused20 after return; never pay120 again or reuse a pending refund.|销售退款、H24日租、V40送机垫款、D20检查账分开；修好验收后只结D20余100，退货则实收未用20，不再付120、不重用待退钱。')
 elif sid=='t2-04':
  state['operating_policy']='P12:R11'
  replace('cleaning','Returned is not clean. Inspection and cleaning acceptance are one actual desk service; its receipt reports the actual result for the returned insert.|还回不等于洗好。检查及清洁验收是一项实际台前服务，回执报告所还内垫的实际结果。')
  extend('next-booking','Current external operating/insurance record P12 wrongly lists R11 for paid C12. The original owner and Bo already authorise correcting it to R12 with the accepted returned insert. Allocation only reserves shelf stock; it cannot change the insurer record. Amend P12 in one submission before the collection credential is issued.|当前外部运营/保单P12把已付C12错列为R11；原所有人和Bo已授权改R12及实际验收归还内垫。配货只留架上库存，不改保险方登记；发领物凭证前一次提交更正P12。')
  new=add('amend-P12','Amend actual external P12 carrier/insert record|更正实际外部P12箱体内垫登记',{'policy':'P12','booking':'C12','serial':'R12','insert':'returned_clean'},{'operating_policy':'P12:R12'}, {'revealed':['result-clean-insert','result-allocate-C12']});before='credential-Bo';requirement('credential-Bo',{'operating_policy':'P12:R12'})
  c['goals'][3]['pass_condition']=T(c['goals'][3]['pass_condition']+' Correct actual external P12 to C12/R12 and the accepted insert before issuing its credential; shelf allocation alone leaves the old insurance record wrong.|'+c['translations'][c['goals'][3]['pass_condition']]+' 发凭证前把外部P12实改为C12/R12及已验收内垫，仅配货仍留旧保单错误。')
 elif sid=='t3-04':
  state['provider_routes']='A12:acct-AdaBo;B09:acct-B09'
  extend('funds','External payment provider record M50 still routes artwork A12 to merged account acct-AdaBo, while B09 already routes to acct-B09. The contributor threads authorise their original actual accounts. Catalogue split and credential binding do not alter this separate provider file. Submit one batch correction before either current entitlement is paid.|外部付款机构档案M50仍把画稿A12送合并账户acct-AdaBo，B09已指acct-B09。两位原线程授权各自实际原账户；拆目录和绑凭证不改独立付款档案，付本次权益前一次批量更正。')
  new=add('correct-M50','Correct external M50 payment routes in one batch|一次批量更正外部M50付款路由',{'provider_record':'M50','A12_account':'acct-A12','B09_account':'acct-B09'},{'provider_routes':'A12:acct-A12;B09:acct-B09'},{});before='pay-Ada'
  requirement('pay-Ada',{'provider_routes':'A12:acct-A12;B09:acct-B09'});requirement('pay-Bo',{'provider_routes':'A12:acct-A12;B09:acct-B09'})
  c['goals'][3]['pass_condition']=T(c['goals'][3]['pass_condition']+' Correct external payment-provider M50 routing to the two authorised original accounts; a local catalogue edit does not redirect funds.|'+c['translations'][c['goals'][3]['pass_condition']]+' 把外部付款机构M50路由实改到两人获准原账户，本地目录编辑不改变款去向。')
 for name,plan in c['plans'].items():
  actions=plan['actions'];idx=next(i for i,a in enumerate(actions)if a.get('choice')==before);actions.insert(idx,deepcopy(new))
  if name!='reference':
   drop={'t1-04':'inventory','t2-03':'old-test','t2-04':'cleaning','t3-04':'credit-agreement'}[sid];actions[:]=[a for a in actions if a.get('entry')!=drop and not(sid=='t3-04'and a.get('action')=='REPLY'and a.get('target')=='issuer-dm')]
   if sid=='t2-03'and name not in ('wrong_scope',):
    for a in actions:
     if a.get('action')=='WRITE'and a.get('target')=='main':a['text']=T('This result is for J317/R3 at the stated setting. We followed this unit’s actual test and the buyer’s chosen remedy; it does not establish how every900 behaves.|这个结果只针对J317/R3及给定设置。按本机实测和买家所选补救处理，不能据此概括所有900。')
  for a in actions:
   if sid=='t2-04'and a.get('action')=='REPLY'and a.get('target')=='claimant-dm':a['text']=T('We have handled this through the original loan holder. The public colour and blanket do not establish ownership, and I cannot share another borrower’s details here.|我们已按原借单找原借用人处理。公开颜色和毯子不能证明归属，这里也不能分享另一位借用人的资料。')
   if sid=='t2-03'and a.get('action')in('ASK','REPLY','FINISH','WRITE')and'text'in a:
    old=a['text'];en=old.replace('hire advance','delivery advance').replace('separate40 advance','separate V40 delivery advance').replace('separate 40 advance','separate V40 delivery advance').replace('your40 advance','your V40 delivery advance').replace('your 40 advance','your V40 delivery advance').replace('buyer\'s own advance','buyer\'s V40 delivery advance');zh=c['translations'].get(old,ZH.get(old,old)).replace('租借垫款','送机垫款');a['text']=T(en+'|'+zh)
 c['translations'].update(ZH)
 c['revision_note']='v1.1新增外部业务事实，主端design-review-04前瞻批准；v1.0旧25步依然合法。'
 return c
