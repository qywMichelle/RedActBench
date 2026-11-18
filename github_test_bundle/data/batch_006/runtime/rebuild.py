"""Reconstruct artifacts from frozen definitions using an isolated source set."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys,tempfile,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output).resolve();m=json.load(open(ROOT/'manifest.json'));deps=json.load(open(ROOT/'construction-dependencies.json'))
 with tempfile.TemporaryDirectory(prefix='redact-b006-build-') as td:
  staging=Path(td)
  for name,expected in deps.items():
   source=ROOT/'runtime'/name;assert hashlib.sha256(source.read_bytes()).hexdigest()==expected,name;shutil.copy2(source,staging/name)
  subprocess.run([sys.executable,str(staging/'build.py'),'--output',str(out),'--version',m['version']],check=True)
 checked=[]
 for e in m['episodes']:
  paths=list(e['files'].values())+[t['path'] for t in e['trajectories']]+[t['review'] for t in e['trajectories']]
  for rel in paths:
   assert (ROOT/rel).read_bytes()==(out/rel).read_bytes(),rel;checked.append(rel)
 report={'batch_id':m['batch_id'],'version':m['version'],'reconstructed_artifacts_compared':len(checked),'all_byte_identical':True,'scope':'worlds, initial inputs, rubrics, authored trajectories and their construction judgments; later acceptance files are not reconstructed'};(out/'rebuild-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
