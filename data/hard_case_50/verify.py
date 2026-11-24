"""Standalone stdlib byte/projection/source-binding and exact-replay verification.
This checks existing data integrity and deterministic replay,not semantic quality.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def local(relative):
    p=Path(relative)
    if p.is_absolute() or '..' in p.parts:raise AssertionError('Nonlocal execution path: '+str(relative))
    p=(ROOT/p).resolve()
    if not p.is_relative_to(ROOT.resolve()):raise AssertionError('Path escapes collection: '+str(relative))
    if not p.is_file():raise AssertionError('Missing collection file: '+str(relative))
    return p

def load_runtime(relative,name):
    path=local(relative+'/runtime.py')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def verify(progress=False):
    started=time.monotonic();manifest=read(local('manifest.json'))
    assert manifest['batch_id']=='hard_case_50'
    entries=manifest['episodes'];assert len(entries)==50
    assert [e['collection_id'] for e in entries]==[f'h{i:03d}' for i in range(1,51)]
    assert len({e['case'] for e in entries})==len({e['episode_id'] for e in entries})==50
    assert all(e['structural_difficulty']=='hard' for e in entries)
    assert manifest['candidate_model_runs']==0 and manifest['new_semantic_review'] is False
    inventory=read(local('file-inventory.json'))['files']
    for rel,expected in inventory.items():assert sha(local(rel))==expected,rel
    sources={};source_bindings=[]
    for source in manifest['source_packages']:
        path=local(source['manifest']);assert sha(path)==source['manifest_sha256']
        data=read(path);assert len(data['episodes'])==source['episode_count']
        sources[source['package']]={e['case']:e for e in data['episodes']}
        source_bindings.append({'package':source['package'],'manifest_sha256':source['manifest_sha256'],'episodes':len(data['episodes'])})
    assert [s['episodes'] for s in source_bindings]==[20,10,20]
    bundles={b['bundle_id']:b for b in manifest['runtime_bundles']};assert len(bundles)==2
    modules={};signatures=set()
    for bid,b in bundles.items():
        normalized={str(Path(k).relative_to(b['runtime_root'])):h for k,h in b['runtime_files'].items()}
        signature=hashlib.sha256(json.dumps(normalized,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert signature==b['content_signature'] and normalized==b['normalized_files']
        assert signature not in signatures;signatures.add(signature)
        for rel,h in b['runtime_files'].items():assert sha(local(rel))==h
        modules[bid]=load_runtime(b['runtime_root'],'hard50_'+bid)
    assert len(manifest['runtime_source_aliases'])==4 # first-package v1/v2 plus02/03
    goals=checks=author_records=reference_calls=0;rows=[];record_hashes=set()
    for i,e in enumerate(entries,1):
        original=sources[e['source_package']][e['source_binding']['source_entry_case']]
        assert e['episode_id']==original['episode_id']
        assert e.get('source_episode_id')==original.get('source_episode_id')
        assert e['version']==original['version'] and e['accepted']==original['accepted']
        assert e['sha256']==original['sha256'] and e['files']==original['files']
        assert e['trajectories']==original['trajectories']
        sb=e['source_binding'];assert sb['source_runtime_files']==original['runtime_files']
        assert sb['source_runtime_root']==original['runtime_root']
        assert sb['source_card']==original['source_card']
        assert sha(local(e['source_card']))==e['source_card_sha256']==sb['source_card_sha256']
        for kind,rel in e['files'].items():assert sha(local(rel))==e['sha256'][kind]
        normalized_source={str(Path(k).relative_to(original['runtime_root'])):v for k,v in original['runtime_files'].items()}
        bundle=bundles[e['runtime_bundle_id']]
        assert normalized_source==bundle['normalized_files']
        assert e['runtime_root']==bundle['runtime_root'] and e['runtime_files']==bundle['runtime_files']
        for descriptor in ([e['public_tool_interface']] if e.get('public_tool_interface') else [])+e.get('additional_tool_descriptors',[]):
            assert sha(local(descriptor['path']))==descriptor['sha256']
        for report in e.get('accepted_review_provenance',[]):assert sha(local(report['path']))==report['sha256']
        runtime=modules[e['runtime_bundle_id']]
        hidden=read(local(e['files']['hidden']));visible=read(local(e['files']['visible']));rubric=read(local(e['files']['rubrics']))
        assert hidden['case']==e['world_case']==e['case']==visible['case']
        assert runtime.World(copy.deepcopy(hidden)).observe()==visible,(e['case'],'initial projection')
        assert rubric.get('case')==hidden['case'],(e['case'],'rubric identity')
        gc=len(rubric['goals']);cc=sum(len(g.get('checks',[])) for g in rubric['goals']);goals+=gc;checks+=cc
        ref_count=0
        for trajectory in e['trajectories']:
            path=local(trajectory['path']);assert sha(path)==trajectory['sha256']
            record=read(path);assert record['case']==hidden['case']
            replay=runtime.replay(hidden,record)
            assert replay['matches'] and replay['exact_record'],(e['case'],trajectory['role'],replay)
            author_records+=1;record_hashes.add(runtime.digest(record))
            if trajectory['role']=='reference':ref_count+=1;reference_calls+=len(record['steps'])
        assert ref_count==1
        rows.append({'collection_id':e['collection_id'],'case':e['case'],'episode_id':e['episode_id'],'runtime_bundle_id':e['runtime_bundle_id'],'source_binding':True,'initial_projection':True,'author_records_exact':len(e['trajectories']),'goals':gc,'rubric_checks':cc})
        if progress:print(f'{i}/50 {e["case"]}: exact {len(e["trajectories"])}',flush=True)
    assert (goals,checks,reference_calls,author_records)==(396,787,2438,355)
    assert (manifest['goal_count'],manifest['rubric_check_count'],manifest['reference_total_calls'],manifest['current_author_record_files'])==(goals,checks,reference_calls,author_records)
    assert manifest['reference_mean_calls']==reference_calls/50==48.76
    mapping=read(local('mapping.json'))['rows'];summary=read(local('case-summary.json'))
    assert [r['collection_id'] for r in mapping]==[e['collection_id'] for e in entries]
    assert [r['episode_id'] for r in mapping]==[e['episode_id'] for e in entries]
    assert summary['goals']==goals and summary['rubric_checks']==checks and summary['author_record_files']==author_records
    return {'passed':True,'collection':'hard_case_50','manifest_sha256':sha(local('manifest.json')),'episodes':50,'initial_projections_exact':50,'author_record_files_exact':author_records,'distinct_author_record_hashes':len(record_hashes),'goals':goals,'rubric_checks':checks,'reference_total_calls':reference_calls,'reference_mean_calls':reference_calls/50,'runtime_content_bundles':len(bundles),'runtime_source_aliases':len(manifest['runtime_source_aliases']),'inventory_files_checked':len(inventory),'source_manifests':source_bindings,'cases':rows,'elapsed_seconds':round(time.monotonic()-started,3),'new_model_runs':0,'new_semantic_reviews':0,'scope':'Existing-byte integrity,local source-manifest binding,initial projection and exact deterministic author-record replay only;not a new semantic review,difficulty calibration or model evaluation.','portable_execution':'All executable/core/record/descriptor/review-provenance paths resolved within this directory;original source directories are unnecessary.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,default=ROOT/'verification.json');parser.add_argument('--progress',action='store_true');args=parser.parse_args()
    report=verify(args.progress);args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=False))
