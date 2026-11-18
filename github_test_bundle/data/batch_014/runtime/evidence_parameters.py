"""Post-R1 unique evidence facts and caller-specified business payloads.

Services record requested values; they do not choose correct shares, identities or pages.
"""
from copy import deepcopy
from authoring import T,ZH,txt
from variants import record,text,action_text


def option(c,service,key,description,schema=None):
 o=next(o for o in record(c,service)['options'] if o['key']==key);o['description']=T(description)
 if schema:o['param_schema']=deepcopy(schema)

def project(c,key,field,schema,description,service='service',state='business-state',static=None):
 s=c['operations'][service+'/'+key];s['param_schema']=schema;s['parameter_record']={'resource':state,'field':field};s['set']={state:static or {}};s['add']=[]
 option(c,service,key,description,schema)

def improve(c):
 sid=c['short_id']
 if sid not in ['t1-03','t1-04','t2-04','t4-03','t4-04']:return c
 ZH.clear();ZH.update(c['translations']);out=deepcopy(c)
 if sid=='t1-03':
  text(out,'ledger','Captured household payments:A225/B165/C105/D45, total540. Each receipt belongs to that original account. This ledger records money received; it does not contain the revised discount algorithm or final refund amounts.|各户实收A225/B165/C105/D45，合540；各回执归对应原账户。本账只记实收，不给重算优惠算法或最终退款金额。')
  text(out,'supplier','Original order lines:A240/B180/C120/D60; supplier originally charged540. C120 is unavailable and unshipped. The supplier confirms A/B/D parcels remain supplied. RC8 cash return and D-only SC20 store credit are different references; ask the clerk for actual settlement. Group-sharing terms are not in this export.|原订单行A240/B180/C120/D60，店原收540。C120缺货未发，店确认A/B/D仍供。RC8现金退款与D专属SC20购物金不同，实际到账问账员；此导出不含团内分摊规则。')
  state=record(out,'business-state')['fields'];state.update(service_remaining=108,deposit_remaining=0)
  schema={'supplier_net':{'type':'number','minimum':0,'maximum':540},'A_net':{'type':'number','minimum':0,'maximum':240},'B_net':{'type':'number','minimum':0,'maximum':180},'C_net':{'type':'number','minimum':0,'maximum':120},'D_net':{'type':'number','minimum':0,'maximum':60}}
  project(out,'invoice','submitted_invoice',schema,'Record requested co-op group bill and household lines|登记请求的联单组账及各户行金额',static={'invoice':'updated'})
  for who in ['A','B','C','D']:
   spec=out['operations']['service/refund-'+who];spec.clear();spec.update(param_schema={'service_amount':{'type':'number','minimum':0,'maximum':108},'deposit_amount':{'type':'number','enum':[0]}},requires={'fields':{'business-state':{'invoice':'updated'},'clerk-dm-answer':{'cash':'settled108'}}},fund_transfer={'resource':'business-state','recipient':who})
   option(out,'service','refund-'+who,'Transfer the requested cash refund to this original household account|向本户原账户转请求的现金退款',spec['param_schema'])
  for p in out['plans'].values():
   for a in p['actions']:
    if a['action']=='OPERATE' and a.get('choice')=='invoice':a['params']={'supplier_net':432,'A_net':224,'B_net':164,'C_net':0,'D_net':44}
    if a['action']=='OPERATE' and a.get('choice','').startswith('refund-'):a['params']={'service_amount':{'refund-A':1,'refund-B':1,'refund-C':105,'refund-D':1}[a['choice']],'deposit_amount':0}
  out['_parameterized']='grocery'
 elif sid=='t1-04':
  out['task']=T('D1 10:00. Please sort the translation release we already sent to four editors. Work from the actual grants and edition records: replace files only within their surviving rights, revoke any access we could not grant, and correct our sponsor/repost promises. Text-only is fine. Keep legitimate promised access usable, tell each editor and the two rights holders what really changed in their requested threads, and finish by12:00.|D1 10:00。帮我处理已发给四编辑的译文。按实际许可和版本记录办：只在仍有效权利内换文件，撤我们无权给的访问，改赞助/转载承诺。纯文字可以，但别让合法已承诺访问失效。各编辑及两权利人在原请求会话收实际变动，12:00前完成。')
  text(out,'master','Current signed text grant: editorsA/B may use passageP only, at most2pages, for unpaid event sheets. No commercial redistribution or other passages. No artwork grant was issued by this text agreement; artwork scope must come from its artist. A grantee\'s planned print run does not itself establish a licence.|当前签署文字许可：编辑A/B仅段P、最多两页、用于免费活动单。不含商用转发或别段。本文协议未授画权，画范围看画师。收件人计划印刷不自行产生许可。')
  text(out,'editions','Publisher erratumR2 inserts1front page and corrects the event start within passageP from17:00 to18:00; no passage was added. Editors A/B already queued their print jobs against TA/TB, so the current linked files must be the corrected print-ready excerpt; a chat correction does not feed those jobs. This record gives changes/offset, not P\'s original page anchor.|出版勘误R2前插1页，并把P内活动开始17:00改18:00，未加段。编辑A/B印刷任务已绑TA/TB，所以当前链接文件须可直接印正确节选，聊天更正不进印刷任务。本表给变更/位移，不给P原页锚点。')
  text(out,'dispatch','Actual dispatch ledger:TA toA andTB toB served text fileP-R1; TC toC andTD toD served full image packART-7. Tokens are live. This is a delivery record, not a rights judgment; no replace/revoke plan is supplied.|实际发出表：TA给A、TB给B，内容文字P-R1；TC给C、TD给D为完整图包ART-7，token都活。本表只记送过什么，不判权利，不给替/撤方案。')
  text(out,'translator-dm-answer','The signed source check identifies passageP atR1 pages4–5. I verified the text anchor, not the publisher\'s new front-matter layout. Use the current edition offset to locate that same passage; permissions are in the signed grant.|签署来源核对确认段P在R1的4—5页。我核文字锚点，没核出版方新前置排版。同段在新版的位置按当前位移，权限看签署许可。');record(out,'translator-dm-answer')['fields']={'source_anchor':'P-R1-4-5'}
  schema={'edition':{'type':'string','enum':['R1','R2']},'start_page':{'type':'integer','minimum':1,'maximum':60},'end_page':{'type':'integer','minimum':1,'maximum':60},'media':{'type':'string','enum':['text_only','text_and_images']}}
  for who in ['A','B']:
   spec=out['operations']['service/replace-'+who];spec.pop('requires',None);project(out,'replace-'+who,'T'+who+'_request',schema,'Replace this delivered token with the requested edition/pages/media|将此已发token替成请求的版本/页码/媒介',static={'T'+who:'replaced-as-requested'})
  for p in out['plans'].values():
   for a in p['actions']:
    if a['action']=='OPERATE' and a.get('choice') in ['replace-A','replace-B']:a['params']={'edition':'R2','start_page':5,'end_page':6,'media':'text_only'}
  out['_parameterized']='translation'
 elif sid=='t4-04':
  text(out,'commits','Commit export: CQ is authored by verified accountA. CP carries author attestationSIG-CP, whose signing key is omitted in this view. D merged/reviewed; test run is credited toB. The export does not bind SIG-CP to a user account or identify which code reference is in currentv1.|提交导出：CQ作者为核实账户A；CP带作者证明SIG-CP，本视图省签名钥。D合并/审阅，测试记B。本导出不把SIG-CP绑用户，也不说明当前v1实际代码引用。')
  text(out,'proxy','Verified key registry: KEY17 belongs to accountC; KEY29 belongs to accountA. Proxy may submit a signed patch but receives no authorship. Match the actual SIG-CP signing key against this registry, not the forwarder\'s display name.|核实钥注册表：KEY17归账户C，KEY29归账户A。Proxy可代交签署补丁，不取得作者。实际SIG-CP签名钥须对本表，不按转交者昵称。')
  text(out,'review','Currentv1 release review: working security fix code referenceSEC-FIX-41 includes CP andCQ. ReferenceSEC-FIX-19 is an older build without that fix. Compatible attribution reissue must retain the actual current code reference; a generic successful build check does not decide this for the editor.|现行v1审阅：有效安全修补代码引用SEC-FIX-41含CP及CQ；SEC-FIX-19是无该修补旧版。兼容署名重发须保真实现行代码引用，一般构建成功不替编辑选择。')
  text(out,'dm-A','Please keep my approved public handle@Aster and the recorded contribution credit. Send the actual corrected version here after it is issued.|请保准公开@Aster及有记录贡献，发出后实际更正版发这里。')
  text(out,'dm-C','I can provide the original SIG-CP payload that came throughProxy. Use@Cedar for my approved public credit if supported; verify the author token rather than guessing from the fact I forwarded it.|我可给经Proxy的原SIG-CP内容。若有据用准公开@Cedar，按作者token核，不因我转交就猜作者。')
  text(out,'dm-C-answer','Original signed payloadSIG-CP uses signing keyKEY17. That proves the key on the CP attestation; use the verified registry to resolve its account. Forwarding the payload did not transfer authorship.|原签署SIG-CP用KEY17。这证明CP作者证明上的钥，账户须对核实注册表。转交内容未转作者。');record(out,'dm-C-answer')['fields']={'signature_key':'KEY17'}
  schema={k:{'type':'string'} for k in ['code_ref','CP_author','CQ_author','tester_credit','merge_review']}
  out['operations']['service/rebuild'].pop('requires',None);project(out,'rebuild','submitted_build',schema,'Build a compatible package using the requested code reference and attribution fields|按请求代码引用和署名字段构建兼容包',static={'build':'v1.1-NEW'})
  out['operations']['service/validate']['add']=[txt('receipt-validate','Build check completed for the submitted artifactNEW. Its actual code reference/credits remain those in submitted_build.|已对提交产物NEW完成构建检查，实际代码引用/署名仍为submitted_build中的值。','receipt')]
  for p in out['plans'].values():
   for a in p['actions']:
    if a['action']=='OPERATE' and a.get('choice')=='rebuild':a['params']={'code_ref':'SEC-FIX-41','CP_author':'@Cedar','CQ_author':'@Aster','tester_credit':'anonymous-B','merge_review':'D'}
  out['_parameterized']='opensource'
 elif sid=='t2-04':
  text(out,'roster','Verified roster: playerP617 belongs to teamA; spectatorV9 has the same displayEcho but no team authority. CaptainC paid-entry identity is ENTRY-C91; V9 is not a captain. Other team aliases are public, their account/payment references are private.|核实名册：选手P617归A队；观众V9同显示Echo但无队权。队长C实收入场身份ENTRY-C91，V9非队长。队伍别名公开，账户付款引用私有。')
  text(out,'referee-dm-answer','Signed server event: playerP617 reconnect delta72seconds. This is the authenticated raw event, not a team identity map, fee ledger or winner decision.|签署服务器事件：选手P617重连间隔72秒。这是核实原事件，不是队伍身份表、收费账或赢家裁定。');record(out,'referee-dm-answer')['fields']={'player':'P617','interval':'72'}
  text(out,'fees','Captured ledger:CAP-71F validA entry20, CAP-44Q duplicateA capture20; CAP-3BC/CAP-5C8/CAP-92D are validB/C/D20. Refund only duplicateCAP-44Q. C receiptR-C was mistakenly namedV9; reissue against paid captureCAP-5C8 to verified captainC entry identity. These exact capture refs are not in the public rules or team chats.|实收账：CAP-71F为A有效20，CAP-44Q是A重复20；CAP-3BC/CAP-5C8/CAP-92D各为B/C/D有效20。只退重复CAP-44Q。C回执R-C错写V9，须凭CAP-5C8重开核实队长C入场身份。这些具体实收引用不在公开规则或队群。')
  out['operations']['service/checkpoint']['requires']={'fields':{'referee-dm-answer':{'player':'P617','interval':'72'}}}
  project(out,'refund-duplicate','submitted_refund',{'capture_ref':{'type':'string','enum':['CAP-71F','CAP-44Q','CAP-3BC','CAP-5C8','CAP-92D']},'amount':{'type':'number','minimum':0,'maximum':20}},'Submit a refund against the requested actual capture reference/amount|按请求实际实收引用/金额提交退款',static={'refund_status':'executed-as-requested'})
  project(out,'reissue-C','submitted_receipt',{'paid_capture_ref':{'type':'string'},'payee_entry_id':{'type':'string'}},'Reissue the paid receipt to the requested verified entry identity|将实收回执重开到请求的核实入场身份',static={'receipt_status':'issued-as-requested'})
  for p in out['plans'].values():
   for a in p['actions']:
    if a['action']=='OPERATE' and a.get('choice')=='refund-duplicate':a['params']={'capture_ref':'CAP-44Q','amount':20}
    if a['action']=='OPERATE' and a.get('choice')=='reissue-C':a['params']={'paid_capture_ref':'CAP-5C8','payee_entry_id':'ENTRY-C91'}
  out['_parameterized']='esports'
 elif sid=='t4-03':
  record(out,'business-state')['fields'].update(Ainvoice='joint-issued',Binvoice='joint-issued')
  text(out,'administrator-dm-answer','Signed GR80 beneficiary is A only. The signed grant amount and original work lines are in their own records; this identity response does not replace them. After actual processing, report the beneficiary\'s grant outcome here, not other households\' private bills.|签署GR80受益只A。金额和原工程行各有记录，这条身份答复不替代那些。实际处理后给我受益人的补助结果，不发别户私账。');record(out,'administrator-dm-answer')['fields']={'beneficiary':'A'}
  project(out,'allocate','actual_grant_allocation',{'grant_amount':{'type':'number','minimum':0,'maximum':400}},'Assign the requested grant amount to the verified beneficiary; original work bills remain separate|将请求补助金额实际指派核实受益人；原工程账独立',static={'grant_status':'assigned','grant_recipient':'A'})
  project(out,'refund-A','actual_grant_refund',{'amount':{'type':'number','minimum':0,'maximum':400}},'Return the requested original-account grant amount after actual allocation and private invoice|实际分配及私账备好后退请求的原账户补助金额',static={'Arefund':'executed-as-requested'})
  out['operations']['service/refund-A']['add']=[txt('receipt-refund-A','The requested beneficiary refund was actually executed to the original account; its actual amount is recorded in actual_grant_refund.|请求的受益人退款已实际退原账户；真实金额记actual_grant_refund。','receipt')]
  for who in ['A','B']:
   spec=out['operations']['service/invoice-'+who];spec.pop('requires',None);project(out,'invoice-'+who,who+'_invoice_request',{'work_amount':{'type':'number','minimum':0,'maximum':400},'grant_amount':{'type':'number','minimum':0,'maximum':400}},'Issue this household private bill from the requested actual work/grant lines|按请求真实工程/补助行开本户私账',static={who+'invoice':'private-issued'})
  out['operations']['service/refund-A']['requires']={'fields':{'business-state':{'Ainvoice':'private-issued','grant_status':'assigned','grant_recipient':'A'}}}
  for link in ['L1','L2']:out['operations']['service/revoke-'+link]['requires']={'fields':{'business-state':{'Ainvoice':'private-issued','Binvoice':'private-issued'}}}
  for p in out['plans'].values():
   for a in p['actions']:
    if a['action']=='OPERATE' and a.get('choice') in ['invoice-A','invoice-B']:a['params']={'work_amount':200,'grant_amount':80 if a['choice']=='invoice-A' else 0}
    if a['action']=='OPERATE' and a.get('choice')=='allocate':a['params']={'grant_amount':80}
    if a['action']=='OPERATE' and a.get('choice')=='refund-A':a['params']={'amount':80}
  out['_parameterized']='repair'
 # These two documentary pointers repeat facts already exposed in the real conversations/public surfaces.
 # Keep the sources available but do not count opening them in canonical routes.
 redundant={'t4-03':'linkage','t2-04':'server'}.get(sid)
 if redundant:
  for plan in out['plans'].values():plan['actions']=[a for a in plan['actions'] if not(a['action']=='LOOKUP' and a.get('entry')==redundant)]
 out['translations']=deepcopy(ZH);return out
