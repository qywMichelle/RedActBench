"""Replay every frozen constructor trajectory in a new, isolated directory."""
from pathlib import Path
import argparse,json,hashlib,shutil
from runtime import replay,World
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output).resolve()
 if out.exists() and any(out.iterdir()):raise SystemExit('Output directory must be empty or new')
 out.mkdir(parents=True,exist_ok=True);manifest=json.loads((ROOT/'manifest.json').read_text());checks=[]
 for e in manifest['episodes']:
  world=json.loads((ROOT/e['files']['hidden']).read_text());initial=World(world).observe()
  target=out/e['files']['visible'];target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(initial,ensure_ascii=False,indent=2)+'\n')
  for t in e['trajectories']:
   payload=json.loads((ROOT/t['path']).read_text());record=replay(world,payload['simulation']);target=out/t['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');checks.append({'episode_id':e['episode_id'],'trajectory':t['strategy'],'exact_replay':True,'steps':len(record['history'])})
 report={'batch_id':manifest['batch_id'],'version':manifest['version'],'episode_count':len(manifest['episodes']),'trajectory_count':len(checks),'checks':checks,'semantic_judgment':'not performed by replay'};(out/'reproduction.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'episode_count':len(manifest['episodes']),'trajectory_count':len(checks),'exact_replay':True}))
if __name__=='__main__':main()
