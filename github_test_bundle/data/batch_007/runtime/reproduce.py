from pathlib import Path
import argparse,json,sys
sys.dont_write_bytecode=True
from runtime import replay,digest
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True);m=json.loads((ROOT/'manifest.json').read_text());rows=[]
for e in m['episodes']:
 w=json.loads((ROOT/e['files']['hidden']).read_text())
 for t in e['trajectories']:
  sim=replay(w,json.loads((ROOT/t['path']).read_text())['simulation']);assert digest(sim)==t['canonical_hash'];dest=out/e['short_id']/(t['strategy']+'.json');dest.parent.mkdir(exist_ok=True);dest.write_text(json.dumps(sim,ensure_ascii=False,indent=2)+'\n');rows.append(dict(episode_id=e['episode_id'],strategy=t['strategy'],canonical_hash=digest(sim)))
(out/'replay-summary.json').write_text(json.dumps(dict(executions=len(rows),results=rows),indent=2)+'\n');print(json.dumps(dict(replayed=len(rows))))
