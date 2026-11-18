"""Build immutable English artifacts and execute authored controls."""
import argparse,hashlib,html,json,sys,shutil
from pathlib import Path
sys.dont_write_bytecode=True
import definition as d
import scenarios
from self_review import FINDINGS,G4_FAILURES
from plan_guard import check_authored_plans
from runtime import World,digest,replay
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def build(out,version='v1.0'):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 if (out/'manifest.json').exists():raise ValueError('Refusing to overwrite frozen data')
 d.VERSION=version
 (out/'runtime').mkdir(exist_ok=True)
 for p in HERE.glob('*.py'):
  if p.resolve()!=(out/'runtime'/p.name).resolve():shutil.copy2(p,out/'runtime'/p.name)
 env={'runtime.py':sha(out/'runtime/runtime.py')};eh=digest(env);entries=[]
 write(out/'construction-dependencies.json',{p.name:sha(p) for p in sorted((out/'runtime').glob('*.py'))})
 for c in d.CASES:
  sid=c['id'];plan_checks=check_authored_plans(c);w=d.world(c);r=d.rubric(c);paths={k:f'{k}/{sid}.json' for k in ('visible','hidden','rubrics')}
  for k,x in [('visible',World(w).observe()),('hidden',w),('rubrics',r)]:write(out/paths[k],x)
  hashes=dict(data=sha(out/paths['hidden']),rubric=sha(out/paths['rubrics']),environment=eh);ts=[]
  for mode in ('reference','failure_initial','failure_near','alternative','style_mismatch',*c.get('additional_plans',{})):
   sim=d.execute(c,mode);assert replay(w,sim)==sim
   tp=f'trajectories/{sid}/{mode}.json';write(out/tp,dict(episode_id=w['id'],version=version,strategy=mode,input_hashes=hashes,execution=dict(kind='actual_cpu_execution',exit_status=0,semantic_scoring='not performed by runtime'),simulation=sim))
   failed=[]
   if mode.startswith('failure_'):
    failed=['G1'] if mode=='failure_initial' else ['G3']
    if sid in G4_FAILURES.get(mode,set()):failed+=['G4']
   goals=[]
   for g in r['goals']:
    evidence=[dict(step=s['step'],time=s['time'],action=s['action']) for s in sim['history'] if s['action'].get('target') in g['objects'] or g['id'] in ('G2','G4')]
    goals.append(dict(goal_id=g['id'],verdict='fail' if g['id'] in failed else 'pass',reason=(c[mode]['reason']+' Additional G4 violation where listed: unsupported commitment, permission expansion, or invented outcome is visible in the actual action.' if g['id'] in failed else FINDINGS[sid]),evidence=evidence,actual_checkpoint_text={k: v.get('text') for k,v in sim['final_state'].items() if k in g['objects']},semantic_review_basis='Constructor inspected actual text and state; the case-specific finding distinguishes reference and alternative and identifies the single-error control.'))
   rp=f'reviews/construction/{sid}/{mode}.json';write(out/rp,dict(episode_id=w['id'],version=version,reviewer='constructor_agent',independence='author_self_review',input_hashes=hashes,trajectory_hash=sha(out/tp),goals=goals,task_success=not failed,style=dict(score=0 if mode=='style_mismatch' else 2,reason='Patronizing opening conflicts with the supplied expression evidence.' if mode=='style_mismatch' else c['style'],evidence_ids=['h1','h2','h3']),case_finding=FINDINGS[sid],limits='Author judgments are uncalibrated semantic reviews, not independent acceptance or automated quality scores.'))
   ts.append(dict(strategy=mode,path=tp,sha256=sha(out/tp),canonical_hash=digest(sim),review=rp,review_hash=sha(out/rp)))
  decision=dict(c['decision']);decision['legal_branches']=c['legal_branches'];decision['notification_support']={'level':decision['notification_support'],'reason':'Notices supply operational constraints and scope. Candidate must integrate affected objects, timing and the available branches; no candidate action sequence or computed plan is supplied.'}
  entries.append(dict(episode_id=w['id'],short_id=sid,version=version,title=c['title'],family=sid[:2].upper(),domain=c['domain'],structural_difficulty=c['difficulty'],main_conflict=c.get('main_conflict','C05' if sid.startswith('t3') else 'C08'),secondary_conflicts=c.get('secondary_conflicts',['C09','C10']),template_group=c['template'],group_id=w['id'],split='development',source_kind='local_topic_or_interaction_motif_with_entirely_synthetic_operational_facts_profiles_and_dialogue',decision_structure=decision,profile_checkpoint='Three authored history samples across contexts; actual task expression only, explicit diagnostic not collected.',data_hash=hashes['data'],visible_hash=sha(out/paths['visible']),rubric_hash=hashes['rubric'],environment_hash=eh,files=paths,trajectories=ts,trajectory_count=len(ts),semantic_review_count=len(ts),authored_plan_integrity=plan_checks,construction_review_status='self_reviewed',independent_review_status='pending',status='construction_complete',issues=[]))
 m=dict(batch_id=d.BATCH,version=version,data_version=version,guideline_version='construction-guideline-v2',acceptance_guideline_version='acceptance-guideline-v2',target_count=20,submitted_count=len(entries),self_reviewed_count=len(entries),independently_accepted_count=0,formal_evaluation_ready=False,formal_split_verified=False,empirical_calibration='not_run',split='development',path_base='manifest_directory',environment_entry='runtime.runtime.World',environment_sources=env,environment_hash=eh,episodes=entries)
 write(out/'manifest.json',m);write(out/'manifest.construction-complete.json',m)
 links=[]
 for e in entries:
  sections=[]
  for title,p in [('Initial input',e['files']['visible']),('Hidden events and world',e['files']['hidden']),('Rubric',e['files']['rubrics'])]+[(t['strategy'],t['path']) for t in e['trajectories']]:sections.append('<details><summary>'+title+'</summary><pre>'+html.escape((out/p).read_text())+'</pre></details>')
  p=out/'review'/f"{e['short_id']}.html";p.parent.mkdir(exist_ok=True);p.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Episode review</title><style>body{max-width:1100px;margin:2em auto;font:16px system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{padding:1em;background:#eee}</style><a href="index.html">Index</a><h1>'+html.escape(e['title'])+'</h1><p>Offline answer-visible review. Never supply to blind candidates.</p>'+''.join(sections));links.append(f'<li><a href="{p.name}">{e["short_id"]}: {html.escape(e["title"])}</a></li>')
 (out/'review/index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Batch006</title><h1>Batch006 English development review</h1><p>'+str(len(entries))+' episodes, '+version+'. Answer-visible fictional materials. Construction review only; independent acceptance pending. Not a blind model input.</p><ul>'+''.join(links)+'</ul>')
 return m
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--version',default='v1.0');a=p.parse_args();m=build(a.output,a.version);print(json.dumps({'episodes':len(m['episodes']),'trajectories':sum(e['trajectory_count'] for e in m['episodes'])}))
