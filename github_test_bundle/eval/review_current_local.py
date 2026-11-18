"""Prepare replay-verified packets for direct primary-assistant judgment.

This script performs no semantic grading. Judgments must be written after the
assistant reads the packet's real deliveries, evidence, state and frozen goals.
"""
import argparse
import hashlib
import json
import itertools
from pathlib import Path
import sys

import run_current_english_gemini as core
from checkpoint_replay import context_args, restore


def critical_criteria(rubric):
    """Read both frozen rubric spellings without inventing new conditions."""
    if 'critical_violations' in rubric:
        return rubric['critical_violations']
    return rubric.get('critical_failures', [])


def goals(rubric):
    result=[]
    for g in rubric.get('goals',rubric.get('rubric',[])):
        identity=g.get('id',g.get('goal_id',g.get('checkpoint_id')))
        if not identity: raise ValueError('Frozen goal has no identifier')
        result.append(dict(g,id=identity))
    return result


def packet(entry, run):
    path = run / 'trajectories' / (entry['case'] + '.json')
    record = json.loads(path.read_text())
    world = json.loads(core.input_path(entry, 'hidden').read_text())
    rubric = json.loads(core.input_path(entry, 'rubrics').read_text())
    core.RUNTIME_CACHE.clear()
    sys.modules.pop('calculators', None)
    config = json.loads((run / 'run_config.json').read_text())
    env, interactions, error = restore(entry, record, context_args(config))
    rows = []
    for index, (call, interaction) in enumerate(zip(record['calls'], interactions), 1):
        observation = interaction['observation']
        row = {'request': index, 'observation': observation,
               'candidate_text': call['response']['text']}
        for key in ('action', 'result', 'protocol_error'):
            if key in call:
                row[key] = call[key]
        row['image_inputs'] = call['response'].get('image_inputs', [])
        rows.append(row)
    if env.record() != record['simulation']:
        raise ValueError('Simulation mismatch')
    return {'case': entry['case'], 'family': entry['family'],
        'difficulty': entry['structural_difficulty'],
        'trajectory_sha256': core.file_sha(path), 'input_hashes': record['input_hashes'],
        'execution_status': record['status'], 'criteria': {**rubric, 'goals': goals(rubric),
            'critical_violations': critical_criteria(rubric)},
        'world_facts_for_offline_judge': world, 'calls': rows,
        'actual_final_record': record['simulation'],
        'judge_scope': 'Primary assistant semantic review; no model identity, old scores or reference trajectory. Actual model identity is already known to the primary assistant from user instructions; do not claim independent identity blinding.'}


def review_text(p):
    out = [p['case'] + ' ' + p['execution_status']]
    world = p['world_facts_for_offline_judge']
    for key in ('task', 'authorization', 'deadline', 'profiles'):
        if key in world:
            out.append(key + ': ' + json.dumps(world[key], ensure_ascii=False))
    out.append('GOALS ' + json.dumps(p['criteria']['goals'], ensure_ascii=False))
    out.append('CRITICAL ' + json.dumps(p['criteria'].get('critical_violations', []), ensure_ascii=False))
    seen = {}

    def evidence(resource):
        # Keep all prose, factual fields, identity/channel/time and state.
        # Menus/syntax remain available in the full JSON packet.
        omitted = {'field_schema', 'request_schema', 'param_schema', 'options', 'topics',
                   'repeatable_topics', 'entries', 'editable', 'tool_protocol'}
        r = {k: v for k, v in resource.items() if k not in omitted}
        key = r.get('id', core.digest(r))
        if seen.get(key) == r:
            return
        seen[key] = r
        out.append('E ' + json.dumps(r, ensure_ascii=False, separators=(',', ':')))

    def same_call(row):
        return core.digest({k:v for k,v in row.items() if k!='request'})

    for unused_key, group in itertools.groupby(p['calls'], key=same_call):
        repeated=list(group)
        row=repeated[0]
        if len(repeated)>1:
            out.append('EXACT IDENTICAL CALLS '+str(row['request'])+'–'+str(repeated[-1]['request'])+
                ': '+str(len(repeated))+' repetitions including identical observation/action/result/error; rendered once below. Full originals remain in JSON packet.')
        obs = row['observation']
        out.append('t' + str(obs.get('time')))
        for r in obs.get('resources', []):
            evidence(r)
        for r in obs.get('own_content', {}).values():
            evidence(r)
        out.append('A' + str(row['request']) + ' ' + json.dumps(row.get('action', row['candidate_text']), ensure_ascii=False))
        result = row.get('result', {})
        if isinstance(result, dict):
            for r in result.get('resources', []):
                evidence(r)
            if result.get('items'):
                for r in result['items']:
                    if isinstance(r, dict): evidence(r)
            reduced = {k: v for k, v in result.items() if k not in {'resources', 'items'}}
            if reduced: out.append('R ' + json.dumps(reduced, ensure_ascii=False, separators=(',', ':')))
        if row.get('protocol_error'):
            out.append('ERROR ' + row['protocol_error'])
    final = p['actual_final_record']
    state = final.get('final_state', {})
    for r in state.values():
        evidence(r)
    for key in ('time', 'done', 'ended_by', 'handoff', 'handoff_time', 'workflow_records', 'private_outbox', 'pending_events'):
        if key in final:
            out.append('FINAL ' + key + ' ' + json.dumps(final[key], ensure_ascii=False))
    return '\n'.join(out) + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--case', action='append')
    p.add_argument('--show', action='store_true')
    args = p.parse_args()
    entries = json.loads(core.run_manifest_path(args.run).read_text())['episodes']
    for entry in entries:
        if args.case and entry['case'] not in args.case:
            continue
        source = args.run / 'trajectories' / (entry['case'] + '.json')
        if not source.exists(): continue
        record = json.loads(source.read_text())
        if record['status'] not in ('complete', 'request_limit', 'action_budget_exhausted', 'input_budget_exceeded'): continue
        target = args.run / 'assistant-judge-inputs' / (entry['case'] + '.json')
        review = args.run / 'assistant-review' / (entry['case'] + '.txt')
        if target.exists() and json.loads(target.read_text())['trajectory_sha256'] == core.file_sha(source):
            cached=json.loads(target.read_text())
            normalized=goals(cached['criteria'])
            critical=critical_criteria(cached['criteria'])
            if cached['criteria']['goals'] != normalized or cached['criteria'].get('critical_violations') != critical:
                cached['criteria']['goals']=normalized
                cached['criteria']['critical_violations']=critical
                core.write(target,cached)
                review.write_text(review_text(cached))
            if args.show: print(review.read_text())
            continue
        value = packet(entry, args.run)
        core.write(target, value)
        review.parent.mkdir(parents=True, exist_ok=True)
        review.write_text(review_text(value))
        if args.show: print(review.read_text())
        else: print(entry['case'], 'packet_ready', flush=True)


if __name__ == '__main__':
    main()
