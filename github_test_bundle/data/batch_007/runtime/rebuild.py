from pathlib import Path
import argparse,json
import build
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();m=json.loads((Path(__file__).resolve().parents[1]/'manifest.json').read_text());r=build.build(a.output,m['version']);print(json.dumps(dict(episodes=len(r['episodes']),version=r['version'])))
