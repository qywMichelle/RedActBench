"""Prepare or aggregate versioned semantic reviews without changing old scores."""
import argparse
import csv
import json
from pathlib import Path
import sys

import run_current_english_gemini as core
from data_paths import data_roots
from review_current_local import packet
from scoring_v2 import (VERSION, WEIGHTS, SYSTEM_FAILURES, aggregate, cost_row,
                        require, score_episode)


def reference(entry, world, replay):
    """Use the named reference, never silently choose the shortest trajectory."""
    relative = Path(entry['files']['hidden']).parent.parent / 'trajectories' / entry['short_id'] / 'reference.json'
    rubric = json.loads(core.input_path(entry, 'rubrics').read_text())
    for root in data_roots(core.ROOT):
        path = root / relative
        if not path.is_file():
            continue
        record = json.loads(path.read_text())
        binding = record.get('input_hashes', {})
        if 'hidden' in binding:
            if any(binding.get(k) != entry['sha256'][k] for k in ('hidden', 'visible', 'rubrics')):
                continue
        else:
            pair = (binding.get('data'), binding.get('rubric'))
            accepted = {(entry['sha256']['hidden'], entry['sha256']['rubrics']),
                        (core.digest(world), core.digest(rubric))}
            if pair not in accepted:
                continue
        replay(world, record['simulation'])
        count = len(record['simulation']['history'])
        require(count > 0, 'Empty reference trajectory')
        return dict(path=str(path), sha256=core.file_sha(path), calls=count,
                    selection='package reference.json; not a shortest-path claim',
                    input_hashes=entry['sha256'], runtime_files=entry['runtime_files'])
    return None


def template(p):
    return dict(scoring_version=VERSION, case=p['case'],
                trajectory_sha256=p['trajectory_sha256'], input_hashes=p['input_hashes'],
                goals=[dict(id=g['id'], status='undetermined', reason='', evidence=[],
                            is_time_limited=None, timing_reason='', timing_evidence=[],
                            timing_checks=[]) for g in p['criteria']['goals']],
                critical_violations=[dict(criterion_index=i, status='undetermined', reason='', evidence=[])
                                     for i, _ in enumerate(p['criteria']['critical_violations'])],
                dimensions=[dict(id=k, score=None, reason='', evidence=[]) for k in WEIGHTS],
                cq=dict(status='not_scorable', score=None, reason='', evidence=[]),
                needs_primary_review=[])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='New v2 report/review directory, separate from legacy score files')
    parser.add_argument('--case', action='append')
    parser.add_argument('--prepare', action='store_true', help='Write replay-verified review packets and blank templates')
    parser.add_argument('--partial', action='store_true', help='Allow incomplete review coverage; never invent scores')
    args = parser.parse_args()
    require(args.output.resolve() != args.run.resolve(), 'Use a separate v2 output directory')
    manifest_path = core.run_manifest_path(args.run)
    manifest = json.loads(manifest_path.read_text())
    entries = manifest['episodes']
    if args.case:
        entries = [e for e in entries if e['case'] in args.case]
        require({e['case'] for e in entries} == set(args.case), 'Unknown case')
    config = dict(scoring_version=VERSION, run=str(args.run.resolve()),
                  manifest_sha256=core.file_sha(manifest_path), cases=[e['case'] for e in entries],
                  behavior_rubric_sha256=core.file_sha(core.ROOT / 'eval/rubric.json'),
                  implementation_sha256=core.file_sha(Path(__file__)),
                  scoring_sha256=core.file_sha(Path(__file__).with_name('scoring_v2.py')))
    config_path = args.output / 'scoring-config.json'
    if config_path.exists():
        require(json.loads(config_path.read_text()) == config, 'Scoring binding changed; use a new output directory')
    else:
        require(not args.output.exists() or not any(args.output.iterdir()), 'Output directory must be new or v2-bound')
        core.write(config_path, config)
    rows, errors, missing, unreviewed, pending, excluded = [], [], [], [], [], []
    for entry in entries:
        case = entry['case']
        path = args.run / 'trajectories' / (case + '.json')
        if not path.exists():
            missing.append(case)
            continue
        row = None
        try:
            record = json.loads(path.read_text())
            require(record['input_hashes'] == entry['sha256'], 'Trajectory input binding mismatch')
            world = json.loads(core.input_path(entry, 'hidden').read_text())
            core.RUNTIME_CACHE.clear()
            sys.modules.pop('calculators', None)
            unused_cls, replay = core.runtime(entry)
            replay(world, record['simulation'])
            row = dict(case=case, family=entry['family'], difficulty=entry['structural_difficulty'],
                       batch=case.split('/')[0], execution_status=record['status'],
                       trajectory_sha256=core.file_sha(path), reference=None,
                       **cost_row(record))
            rows.append(row)
            ref = reference(entry, world, replay)
            row.update(reference=ref, **cost_row(record, ref['calls'] if ref else None))
            if record['status'] in SYSTEM_FAILURES or record['status'] not in {
                    'complete', 'request_limit', 'action_budget_exhausted'}:
                excluded.append(case)
                continue
            p = packet(entry, args.run)
            p['scoring_version'] = VERSION
            p['behavior_rubric'] = json.loads((core.ROOT / 'eval/rubric.json').read_text())
            p['scoring_instructions'] = (
                'Judge goal status as completion by termination, separately from timeliness. '
                'Do not count expired/infeasible or merely claimed transactions as completed. '
                'Explicitly classify every goal is_time_limited with timing_reason/evidence. '
                'For timed goals enumerate every applicable window in timing_checks: '
                '{id,status,deadline:integer,completion_time:integer|null,inclusive:boolean,reason,evidence}. '
                'Window status describes completion, not punctuality. Resolve relative deadlines '
                'from actual activation evidence; preserve multiple windows and repeated maintenance. '
                'Do not reuse legacy goal status without a new semantic review. '
                'Do not mark obligations N/A solely because the candidate skipped evidence acquisition. '
                'Six dimensions retain the frozen rubric anchors; scores require actual evidence.')
            jp = args.output / 'judgments' / (case + '.json')
            if args.prepare:
                core.write(args.output / 'judge-inputs' / (case + '.json'), p)
                tp = args.output / 'templates' / (case + '.json')
                if not tp.exists():
                    core.write(tp, template(p))
            if not jp.exists():
                unreviewed.append(case)
                continue
            j = json.loads(jp.read_text())
            require(j['case'] == case and j['trajectory_sha256'] == p['trajectory_sha256']
                    and j['input_hashes'] == p['input_hashes'], 'Judgment binding mismatch')
            require(isinstance(j.get('needs_primary_review'), list), 'Review issues list required')
            row.update(score_episode(j, p['criteria']))
            if j['needs_primary_review']:
                pending.append(dict(case=case, issues=j['needs_primary_review']))
        except Exception as exc:
            errors.append(dict(case=case, error=f'{type(exc).__name__}: {exc}'))
        print(json.dumps(dict(case=case, recorded=row is not None), ensure_ascii=False), flush=True)
    complete = not (missing or errors or unreviewed or pending or excluded)
    report = dict(scoring_version=VERSION, status='complete' if complete else 'partial',
                  planned_episodes=len(entries), missing_trajectories=missing, validation_errors=errors,
                  unreviewed=unreviewed, needs_primary_review=pending, quality_excluded=excluded,
                  overall=aggregate(rows),
                  by_family={k: aggregate([r for r in rows if r['family'] == k]) for k in sorted({e['family'] for e in entries})},
                  by_difficulty={k: aggregate([r for r in rows if r['difficulty'] == k]) for k in ('medium', 'hard')},
                  by_batch={k: aggregate([r for r in rows if r['batch'] == k]) for k in sorted({r['batch'] for r in rows})},
                  cost_scope='All replay-verified recorded attempts, regardless of success or review availability; missing references and zero-call efficiency are null with coverage counts.',
                  quality_scope='Explicit v2 semantic judgments only; system failures, input-budget blocks and user-stopped prefixes excluded with coverage reported.',
                  rows=rows)
    core.write(args.output / 'metrics-v2.json', report)
    if rows:
        csv_rows = [{k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                     for k, v in r.items()} for r in rows]
        fields = list(dict.fromkeys(k for r in csv_rows for k in r))
        with (args.output / 'per-episode-v2.csv').open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(csv_rows)
    print(json.dumps(dict(status=report['status'], overall=report['overall'], errors=errors), ensure_ascii=False))
    if errors:
        raise SystemExit('V2 validation failed; see metrics-v2.json')
    if not complete and not (args.partial or args.prepare):
        raise SystemExit('V2 review/trajectory coverage incomplete; see metrics-v2.json')


if __name__ == '__main__':
    main()
