"""Replay every retained construction trajectory with the frozen runtime."""
from pathlib import Path
import argparse,json,hashlib,sys
sys.dont_write_bytecode=True
from runtime import replay,digest
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 m=json.load(open(ROOT/'manifest.json'));results=[]
 for e in m['episodes']:
  world=json.load(open(ROOT/e['files']['hidden']))
  for t in e['trajectories']:
   source=ROOT/t['path'];record=json.load(open(source));actual=replay(world,record['simulation']);assert digest(actual)==t['canonical_hash']
   path=out/e['short_id']/(t['strategy']+'.json');path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(actual,ensure_ascii=False,indent=2)+'\n');results.append({'episode_id':e['episode_id'],'strategy':t['strategy'],'source_sha256':sha(source),'canonical_hash':digest(actual),'steps':len(actual['history']),'done':actual['done']})
 report={'batch_id':m['batch_id'],'version':m['version'],'manifest_sha256':sha(ROOT/'manifest.json'),'kind':'exact_execution_replay_not_semantic_scoring','executions':len(results),'results':results};(out/'replay-summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'replayed':len(results),'summary':str(out/'replay-summary.json')}))
if __name__=='__main__':main()
