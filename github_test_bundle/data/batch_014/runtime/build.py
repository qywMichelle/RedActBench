"""Build the batch in a new directory and execute actual deterministic trajectories."""
from pathlib import Path
from copy import deepcopy
import argparse,hashlib,json,sys,shutil
sys.dont_write_bytecode=True
from runtime import World,run,replay,digest
from protocol import PROTOCOL
BATCH='batch_014_20261113'
SOURCE=Path(__file__).resolve().parent

def dump(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def merge(base,patch):
 out=deepcopy(base)
 for key,value in patch.items():
  if key=='resource_overrides':
   def visit(x):
    if isinstance(x,dict):
     if x.get('id') in value:x.update(deepcopy(value[x['id']]))
     for v in list(x.values()):visit(v)
    elif isinstance(x,list):
     for v in x:visit(v)
   visit(out)
  elif isinstance(value,dict) and isinstance(out.get(key),dict):out[key]=merge(out[key],value)
  else:out[key]=deepcopy(value)
 return out

def world(c,version):
 keys=('resources','lookups','answers','events','action_events','operations','asset_catalog')
 out={k:deepcopy(c[k]) for k in keys}
 out.update(id=BATCH+'-'+c['short_id'],version=version,title=c['title'],task=c['task'],authorization=c['authorization'],deadline=c['deadline'],budget={'calls':c['call_budget']},tool_protocol=deepcopy(PROTOCOL))
 out['tool_protocol']['clock']='One successful non-WAIT/FINISH tool takes one virtual minute. Time zero is the clock in the task. Observe is free; initial input contains only the task card. Fixed events at a completion instant apply before the action. Private and public channels are distinct. All data and services are fictional.'
 return out

def rubric(c,version):return dict(episode_id=BATCH+'-'+c['short_id'],version=version,language='English',scoring='Judge actual language, evidence, permissions and business state. Deterministic service state is not a language score.',goals=c['goals'],style=c['style'],formal_evaluation_ready=False)

def calls(sim):
 seen=set();result=[]
 for step in sim['history']:
  a=step['action'];op=a['action'];effective=op not in ('WAIT','FINISH','READ') and step['result'].get('applied',True)
  if op=='LOOKUP':
   key=(a['target'],a['entry']);effective=effective and key not in seen;seen.add(key)
  if effective:result.append(step['step'])
 return result

def execute(out,sid,plans,w,r,env,prefix=''):
 bindings=dict(data=digest(w),rubric=digest(r),environment=env);entries=[]
 for name,p in plans.items():
  try:
   policy=World(w)
   for action in p['actions']:
    if action['action']=='WAIT_FOR_IDS':
     # Author policy waits only on currently visible observations, then emits ordinary WAIT tools.
     while not all(rid in policy.resources for rid in action['ids']):
      if policy.done:raise ValueError('Required reply not visible before closure')
      policy.apply({'action':'WAIT','until':action.get('until',w['deadline'])})
    elif action['action']=='WAIT':
     # Author policy observes every early wake and continues toward its explicit horizon.
     while policy.time<action['until'] and not policy.done:policy.apply(action)
    else:policy.apply(action)
   sim=policy.record();replay(w,sim)
  except Exception as e:raise RuntimeError(sid+'/'+name+': '+str(e)) from e
  trace=dict(episode_id=w['id'],version=w['version'],strategy=name,input_hashes=bindings,simulation=sim,effective_work_steps=calls(sim),effective_work_calls=len(calls(sim)))
  relative=prefix+'trajectories/'+sid+'/'+name+'.json';dump(out/relative,trace)
  findings=[dict(goal_id=g['id'],verdict='fail' if g['id'] in p.get('failed_goals',{}) else 'pass',reason=p.get('failed_goals',{}).get(g['id'],'Constructor self-review: verify actual text and state against '+g['pass_condition']),evidence_targets=g['objects']) for g in r['goals']]
  relreview=prefix+'reviews/construction/'+sid+'/'+name+'.json';dump(out/relreview,dict(episode_id=w['id'],version=w['version'],reviewer_role='constructor_self_review',input_hashes=bindings,trajectory_sha256=sha(out/relative),verdict='pending_actual_self_review',expected_verdict='fail' if p.get('failed_goals') else 'pass',notes=p['notes'],author_expected_findings=findings,actual_self_review_status='pending_actual_text_inspection'))
  entries.append(dict(strategy=name,path=relative,sha256=sha(out/relative),canonical_hash=digest(sim),review=relreview,review_hash=sha(out/relreview),effective_work_calls=len(calls(sim))))
 return entries

def build(out,cases,version='v0.1-preflight',frozen_input=None):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 (out/'runtime').mkdir(exist_ok=True)
 for source in [*SOURCE.glob('*.py'),*SOURCE.glob('*.json')]:
  target=out/'runtime'/source.name
  if source.resolve()!=target.resolve():shutil.copy2(source,target)
 if (SOURCE.parent/'design-outline.json').exists() and (SOURCE.parent/'design-outline.json').resolve()!=(out/'design-outline.json').resolve():shutil.copy2(SOURCE.parent/'design-outline.json',out/'design-outline.json')
 env={name:sha(SOURCE/name) for name in ('runtime.py','core_runtime.py','protocol.py')};eh=digest(env)
 manifest=dict(batch_id=BATCH,version=version,language='English',pipeline_version='multi-agent-construction-pipeline-v4',diversity_spec_version='structure-diversity-v2',guideline_version='construction-guideline-v2',acceptance_guideline_version='acceptance-guideline-v2',target_count=20,delivery_status='candidate',formal_evaluation_ready=False,human_review='not_performed',empirical_calibration='not_run',judge_calibration='not_run',formal_split_verified=False,environment_sources=env,environment_hash=eh,episodes=[])
 outline=json.loads((SOURCE.parent/'design-outline.json').read_text());cards={c['short_id']:c for c in outline['cards']}
 allzh={}
 for original_case in cases:
  from language_patches import apply_language_patches,normalize_case_prose
  from rubric_enrichment import enrich
  from evidence_parameters import improve
  c=apply_language_patches(improve(enrich(original_case)))
  if frozen_input:
   fw=json.loads((Path(frozen_input)/'hidden'/(c['short_id']+'.json')).read_text());fr=json.loads((Path(frozen_input)/'rubrics'/(c['short_id']+'.json')).read_text())
   for key in ('resources','lookups','answers','events','action_events','operations','asset_catalog'):c[key]=deepcopy(fw[key])
   c['goals']=deepcopy(fr['goals']);c['style']=deepcopy(fr['style'])
  from variants import branch
  c=branch(c)
  from oral_delivery import extend_oral
  from network_balance import balance_network
  c=extend_oral(balance_network(c))
  c=normalize_case_prose(c)
  from prose_projection import normalize
  c=apply_language_patches(normalize(c))
  sid=c['short_id'];meta=cards[sid];w=deepcopy(fw) if frozen_input else world(c,version);r=deepcopy(fr) if frozen_input else rubric(c,version);visible=World(w).observe();files=dict(visible='visible/'+sid+'.json',hidden='hidden/'+sid+'.json',rubrics='rubrics/'+sid+'.json')
  for kind,v in [('visible',visible),('hidden',w),('rubrics',r)]:dump(out/files[kind],v)
  tr=execute(out,sid,c['plans'],w,r,eh)
  item=dict(episode_id=w['id'],short_id=sid,version=version,title=c['title'],family=meta['family'],domain=meta['domain'],structural_difficulty=meta['structural_difficulty'],split='development',files=files,sha256={k:sha(out/v) for k,v in files.items()},data_hash=sha(out/files['hidden']),rubric_hash=sha(out/files['rubrics']),visible_hash=sha(out/files['visible']),environment_hash=eh,runtime_root='runtime',runtime_class='runtime.World',source_kind='reddit_inspired_fiction',seed_group_id='B014-'+sid,accepted=False,trajectories=tr)
  if c.get('contrast_variant'):
   cfg=c['contrast_variant'];bw=deepcopy(w)
   if cfg.get('complete_world_projection'):bw.update(deepcopy(cfg['world_patch']))
   else:bw=merge(w,cfg['world_patch'])
   br=merge(r,cfg.get('rubric_patch',{}));bfiles=dict(visible='contrast/'+sid+'/visible.json',hidden='contrast/'+sid+'/hidden.json',rubrics='contrast/'+sid+'/rubrics.json')
   for k,v in [('visible',World(bw).observe()),('hidden',bw),('rubrics',br)]:dump(out/bfiles[k],v)
   btr=execute(out,sid,cfg['plans'],bw,br,eh,prefix='contrast/')
   item['contrast_variant']=dict(name='B',changed_fact=cfg['changed_fact'],expected_behavior_change=cfg.get('expected_behavior_change','See actual B trajectory and rubric.'),files=bfiles,sha256={k:sha(out/v) for k,v in bfiles.items()},trajectories=btr)
   item['variants']=[deepcopy(item['contrast_variant'])]
  dump(out/('translations/'+sid+'.json'),c['translations']);allzh.update(c['translations']);manifest['episodes'].append(item)
 for p in (SOURCE.parent/'translations'/'zh').glob('*.json'):
  extra=json.loads(p.read_text())
  allzh.update({k:v for k,v in extra.items() if isinstance(v,str)})
  target=out/'translations'/'zh'/p.name
  if p.resolve()!=target.resolve():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
 framework=SOURCE.parent/'rubric-framework.json'
 if framework.exists() and framework.resolve()!=(out/'rubric-framework.json').resolve():shutil.copy2(framework,out/'rubric-framework.json')
 dump(out/'manifest.json',manifest);dump(out/'translations.json',allzh)
 print(json.dumps({'out':str(out),'episodes':len(cases),'effective':{e['short_id']:{p['strategy']:p['effective_work_calls'] for p in e['trajectories']} for e in manifest['episodes']}}))
 return manifest

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--output',required=True);a.add_argument('--version',default='v0.1-preflight');a.add_argument('--ids',nargs='*');a.add_argument('--frozen-input');args=a.parse_args()
 from cases_anchor import group_buy,seat_swap,ride
 cases=[f() for f in (group_buy,seat_swap,ride)]
 try:
  from cases_other import other_cases
  cases+=other_cases()
 except ImportError:pass
 if args.ids:cases=[c for c in cases if c['short_id'] in args.ids]
 build(args.output,cases,args.version,args.frozen_input)
