"""Construct batch018 from its adopted bilingual definitions and execute policies."""
from copy import deepcopy
from pathlib import Path
import argparse,hashlib,json,shutil,sys
sys.dont_write_bytecode=True
from runtime import World,replay,digest
from protocol import PROTOCOL
from audit_effective_calls import audit
ROOT=Path(__file__).resolve().parent.parent
BATCH='batch_018_20261115'

def dump(path,obj):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def world(c,version):
 keys=('resources','lookups','answers','events','action_events','operations','asset_catalog')
 w={k:deepcopy(c[k]) for k in keys}
 for k in ('feature_verification','audit_expectations',):
  if k in c:w[k]=deepcopy(c[k])
 def bind_images(obj):
  if isinstance(obj,dict):
   if obj.get('image_path'):
    asset=ROOT/obj['image_path']
    if not asset.is_file():raise ValueError('Missing bound visual asset: '+obj['image_path'])
    obj['image_sha256']=sha(asset)
   for value in list(obj.values()):bind_images(value)
  elif isinstance(obj,list):
   for value in obj:bind_images(value)
 # Messages created by later feedback have arrival times in history, not a
 # fabricated pre-task send timestamp. Initial historical records stay intact.
 def strip_future_dm_time(obj):
  if isinstance(obj,dict):
   if obj.get('kind')=='dm' and obj.get('published_at')=='D1 before task':obj.pop('published_at')
   for value in obj.values():strip_future_dm_time(value)
  elif isinstance(obj,list):
   for value in obj:strip_future_dm_time(value)
 for feedback in ('answers','events','action_events'):strip_future_dm_time(w[feedback])
 bind_images(w)
 w.update(id=BATCH+'-'+c['short_id'],version=version,title=c['title'],task=c['task'],authorization=c['authorization'],deadline=c['deadline'],budget={'calls':c['call_budget']},tool_protocol=deepcopy(PROTOCOL))
 return w

def execute(w,plan):
 obj=World(w)
 for a in plan['actions']:
  if a['action']=='WAIT_FOR_IDS':
   while not all(i in obj.resources for i in a['ids']):
    if obj.done:raise ValueError('Expected feedback not received before closure')
    obj.apply({'action':'WAIT','until':a.get('until',w['deadline'])})
  elif a['action']=='WAIT_FOR_FIELDS':
   while not obj.matches(a['condition']):
    if obj.done:raise ValueError('Expected actual field feedback not received')
    obj.apply({'action':'WAIT','until':a.get('until',w['deadline'])})
  elif a['action']=='WAIT':
   while obj.time<a['until'] and not obj.done:obj.apply(a)
  else:obj.apply(a)
 sim=obj.record();replay(w,sim);return sim

def save_case(out,c,meta,version,env,prefix=''):
 sid=c['short_id'];w=world(c,version);r=dict(episode_id=w['id'],version=version,language='English',scoring='Judge actual language, scope, evidence, recipients, timing and business states; receipts are not semantic scores.',goals=c['goals'],style=c['style'],formal_evaluation_ready=False)
 initial=World(w).observe();files={k:prefix+k+'/'+sid+'.json' for k in ('visible','hidden','rubrics')}
 for k,v in [('visible',initial),('hidden',w),('rubrics',r)]:dump(out/files[k],v)
 bindings=dict(data=digest(w),rubric=digest(r),environment=env);tr=[]
 for name,plan in c['plans'].items():
  try:sim=execute(w,plan)
  except Exception as exc:raise RuntimeError(sid+'/'+prefix+name+': '+str(exc)) from exc
  accounting=audit(initial,sim);tp=prefix+'trajectories/'+sid+'/'+name+'.json'
  record=dict(episode_id=w['id'],version=version,strategy=name,input_hashes=bindings,simulation=sim,effective_work_calls=accounting['mechanically_effective_calls'],effective_work_steps=[s['step'] for s in accounting['steps'] if s['mechanically_effective']],effective_call_audit=accounting)
  dump(out/tp,record)
  rp=prefix+'reviews/construction/'+sid+'/'+name+'.json'
  review=dict(episode_id=w['id'],version=version,reviewer_role='constructor_self_review',input_hashes=bindings,trajectory_sha256=sha(out/tp),verdict='pending_actual_self_review',author_expected_verdict='fail' if plan.get('failed_goals') else 'pass',author_expected_failures=plan.get('failed_goals',{}),notes=plan['notes'],actual_self_review_status='pending_read_actual_prose_and_state')
  dump(out/rp,review)
  tr.append(dict(strategy=name,path=tp,sha256=sha(out/tp),canonical_hash=digest(sim),review=rp,review_hash=sha(out/rp),effective_work_calls=accounting['mechanically_effective_calls']))
 return dict(episode_id=w['id'],short_id=sid,version=version,title=c['title'],family=meta['family'],domain=meta.get('canonical_domain',meta['domain']),structural_difficulty=meta['structural_difficulty'],split='development',files=files,sha256={k:sha(out/v) for k,v in files.items()},data_hash=sha(out/files['hidden']),rubric_hash=sha(out/files['rubrics']),visible_hash=sha(out/files['visible']),environment_hash=env,runtime_root='runtime',runtime_class='runtime.World',review_page='review-zh.html#case='+sid,construction_author=c.get('authored_by','constructor'),source_kind='local_youtube_topic_inspired_fiction',seed_group_id='B018-'+sid,accepted=False,decision_structure=meta['decision_structure'],trajectories=tr)

def build(out,ids=None,version='v0.1-preflight'):
 from cases import cases
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 for name in ['runtime','assets']:
  src=ROOT/name;dst=out/name
  if src.exists() and src.resolve()!=dst.resolve():shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
 for name in ['design-outline.json','design-outline.md','rubric-framework.json']:
  if (ROOT/name).exists() and (ROOT/name).resolve()!=(out/name).resolve():shutil.copy2(ROOT/name,out/name)
 defs=cases(ids);outline=json.load(open(ROOT/'design-outline.json'));cards={c['short_id']:c for c in outline['cards']}
 sources={p.name:sha(p) for p in sorted(p for p in (ROOT/'runtime').iterdir() if p.suffix in ('.py','.json'))};env=digest(sources)
 m=dict(batch_id=BATCH,version=version,language='English',pipeline_version='multi-agent-construction-pipeline-v4',diversity_spec_version='structure-diversity-v2',guideline_version='construction-guideline-v2',acceptance_guideline_version='acceptance-guideline-v2',target_count=20,review_overview='review-zh.html',delivery_status='candidate',formal_evaluation_ready=False,human_review='not_performed',empirical_calibration='not_run',judge_calibration='not_run',formal_split_verified=False,environment_sources=sources,environment_hash=env,episodes=[])
 assets={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'assets').rglob('*')) if p.is_file()} if (ROOT/'assets').exists() else {}
 m['asset_sources']=assets
 if (ROOT/'rubric-framework.json').exists():m['rubric_framework']={'path':'rubric-framework.json','sha256':sha(ROOT/'rubric-framework.json')}
 translations={}
 for c in defs:
  item=save_case(out,c,cards[c['short_id']],version,env)
  if c.get('common_legal_strategy'):item['common_legal_strategy']=c['common_legal_strategy']
  if c.get('contrast'):
   b=c['contrast'];bi=save_case(out,b,cards[c['short_id']],version,env,'contrast/')
   item['contrast_variant']=dict(name='B',changed_fact=c['changed_fact'],expected_behavior_change=c.get('behavior_change','See B world and complete trajectories.'),files=bi['files'],sha256=bi['sha256'],trajectories=bi['trajectories'])
   item['contrast_variant'].update(environment_hash=env,runtime_root='runtime',runtime_class='runtime.World');item['variants']=[deepcopy(item['contrast_variant'])]
   translations.update(b['translations'])
  dump(out/('translations/'+c['short_id']+'.json'),c['translations']);translations.update(c['translations']);m['episodes'].append(item)
 dump(out/'translations.json',translations);dump(out/'manifest.json',m)
 print(json.dumps({'episodes':len(m['episodes']),'version':version,'effective':{e['short_id']:{t['strategy']:t['effective_work_calls'] for t in e['trajectories']} for e in m['episodes']}}))
 return m
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--ids',nargs='*');p.add_argument('--version',default='v0.1-preflight');a=p.parse_args();build(a.output,a.ids,a.version)
