"""Batch020 registry, expanded only after the preflight gate."""
import json
from pathlib import Path
from cases_preflight import REGISTRY
from rubric_details import refine
from cases_more import REGISTRY as MORE
REGISTRY.update(MORE)
from cases_hard import REGISTRY as HARD
REGISTRY.update(HARD)
from cases_primary import REGISTRY as PRIMARY
REGISTRY.update(PRIMARY)
from cases_credit_primary import REGISTRY as CREDIT
REGISTRY.update(CREDIT)
from cases_bird_redesign import REGISTRY as BIRD
REGISTRY.update(BIRD)
from cases_listening_redesign import REGISTRY as LISTENING
REGISTRY.update(LISTENING)
CN=json.loads(Path(__file__).with_name('chinese_overrides.json').read_text())
def project_chinese(c):
 parents={'t4-01':('assets','Switch-control demo: questions and download updates.','开关控制演示：提问及下载更新。'),'t4-03':('programme','Science-fair display: programme and organiser handover.','科展：节目单和组织者交接。'),'t5-02':('objects','Pottery deliveries: finished pieces and packing questions.','陶器送货：成品和包装问题。'),'t5-03':('shots','Cycling shoot: measurement plan and clothing photographs.','骑行拍摄：测量安排和服装照片。')}
 if c['short_id'] in parents:
  entry,en,zh=parents[c['short_id']]
  all_resources=c['resources']+[r for values in c['lookups'].values() for r in values]
  if not any(r['id']=='main' for r in all_resources):
   c['lookups']['card/'+entry].append({'id':'main','kind':'post','channel':'public','author':'creator','editable':False,'status':'published','text':en,'published_at':'D1 before task'})
   c['translations'][en]=zh
 # A published old answer belongs to its real published historical thread,
 # never to the still-unpublished current invitation/stock-board draft.
 historical={'t1-01':('queue','history-coffee','We are trying a borrowed grinder this afternoon. Questions about the beans or the kit can go here.','下午我们试一试借来的磨豆机。想问豆子或设备的来源，就在这条帖里问。','old-credit','D1 15:00','D1 15:20'),'t1-02':('board','history-orchid','Let us keep orchid-swap stock questions and reservations in this thread.','兰花交换会的库存和预留问题都放这条帖里，方便大家查。','old-stock','D0 18:00','D1 12:00')}
 if c['short_id'] in historical:
  entry,pid,en,zh,child,posted,reply_time=historical[c['short_id']]
  c['lookups']['card/'+entry].append({'id':pid,'kind':'post','channel':'public','author':'creator','editable':False,'status':'published','text':en,'published_at':posted,'group_id':'community','group_name':'Community'})
  for r in c['lookups']['card/'+entry]:
   if r['id']==child:r.update(parent=pid,reply_to=pid,published_at=reply_time)
  c['translations'][en]=zh
 # Existing actual public metadata is part of the free observation. These
 # complete short routes do not force a redundant check/preview flag.
 if c['short_id'] in {'t1-04','t2-02','t4-01'}:
  from copy import deepcopy
  sid=c['short_id'];base=c['plans']['lawful_alternative'] if sid=='t1-04' else c['plans']['reference'];plan=deepcopy(base)
  plan['actions']=[a for a in plan['actions'] if not (a.get('action')=='OPERATE' and a.get('choice')=='preview')]
  trigger={'t1-04':('download','upload',['download-state']),'t2-02':('tutorial-editor','export',['published-tutorial-state','public-panel']),'t4-01':('download','replace',['download-state'])}[sid]
  at=next(i for i,a in enumerate(plan['actions']) if a.get('target')==trigger[0] and a.get('choice')==trigger[1])
  plan['actions'].insert(at+1,{'action':'OBSERVE_FREE','ids':trigger[2],'purpose':'Inspect the already revealed actual installed public content; no extra preview work call.'})
  plan['notes']='Complete lawful route reads actual already-revealed public data through free observation. It never equates checked=false with unread content.'
  c['translations'][plan['notes']]='这条完整合法路线通过免费观察读取已经给出的实际公开内容，不把checked=false当成没有读过。'
  c['plans']['strong_simplification']=plan
 c['translations']={en:CN.get(en,zh) for en,zh in c['translations'].items()}
 return c
def cases(ids=None):
 return [project_chinese(refine(fn())) for sid,fn in sorted(REGISTRY.items()) if ids is None or sid in ids]
