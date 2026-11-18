"""Explicit completion/timing judgments and unfiltered call-cost accounting."""
import math

VERSION = 'redact-scoring-v2'
WEIGHTS = dict(evidence=25, timing=20, authorization=20,
               helpfulness=15, restraint=10, communication=10)
STATUSES = {'pass', 'fail', 'not_applicable', 'undetermined'}
SYSTEM_FAILURES = {'infrastructure_error', 'input_budget_exceeded', 'user_stopped'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def call_counts(record):
    """Count dispatch attempts, including rejected actions; never count events."""
    calls = record['calls']
    attempts = [c for c in calls if 'action' in c]
    return dict(requests=len(calls), actual_tool_calls=len(attempts),
                recorded_environment_steps=len(record['simulation']['history']),
                tool_errors=sum('protocol_error' in c for c in attempts),
                format_errors=sum('protocol_error' in c for c in calls if 'action' not in c))


def cost_row(record, reference_calls=None):
    row = call_counts(record)
    if reference_calls is not None:
        require(type(reference_calls) is int and reference_calls > 0,
                'Reference calls must be a positive integer')
    row.update(reference_tool_calls=reference_calls,
               efficiency=ratio(reference_calls, row['actual_tool_calls'])
               if reference_calls is not None else None,
               tool_call_ratio=ratio(row['actual_tool_calls'], reference_calls))
    return row


def timing_status(goal):
    """A timed goal is on time only when every applicable window is satisfied."""
    require(type(goal.get('is_time_limited')) is bool, 'Explicit is_time_limited required')
    require(goal.get('timing_reason') and goal.get('timing_evidence'),
            'Timing classification needs rationale and evidence')
    checks = goal.get('timing_checks', [])
    require(isinstance(checks, list), 'timing_checks must be a list')
    if not goal['is_time_limited'] or goal['status'] == 'not_applicable':
        require(not checks, 'Untimed/inapplicable goals must have no timing checks')
        return None
    require(checks, 'Timed goals need all applicable deadline windows')
    ids = [c.get('id') for c in checks]
    require(all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids),
            'Timing windows need unique IDs')
    outcomes = []
    for check in checks:
        status = check.get('status')
        require(status in {'pass', 'fail', 'undetermined'}, 'Invalid timing completion status')
        require(check.get('reason') and check.get('evidence'), 'Timing evidence required')
        deadline = check.get('deadline')
        require(type(deadline) is int, 'Resolve deadline to integer virtual time')
        inclusive = check.get('inclusive', True)
        require(type(inclusive) is bool, 'inclusive must be boolean')
        completed = check.get('completion_time')
        if status == 'pass':
            require(type(completed) is int, 'Completed window needs actual completion time')
            outcomes.append('pass' if (completed <= deadline if inclusive else completed < deadline) else 'fail')
        else:
            require(completed is None, 'Uncompleted/unknown window needs null completion_time')
            outcomes.append(status)
    if goal['status'] == 'pass':
        require(all(c['status'] == 'pass' for c in checks),
                'Completed goal cannot contain an uncompleted timing obligation')
    if goal['status'] == 'fail' or 'fail' in outcomes:
        return 'fail'
    if goal['status'] == 'undetermined' or 'undetermined' in outcomes:
        return 'undetermined'
    return 'pass'


def score_episode(judgment, criteria):
    require(judgment.get('scoring_version') == VERSION, 'Explicit v2 semantic review required')
    goals = judgment['goals']
    expected = {g['id']: g for g in criteria['goals']}
    require(len(goals) == len(expected) and {g['id'] for g in goals} == set(expected),
            'Goal coverage mismatch')
    denominator = passed = unknown = 0
    required_outcomes = []
    timed = []
    for goal in goals:
        require(goal['status'] in STATUSES and goal.get('reason') and goal.get('evidence'),
                'Goal needs completion status, reason and evidence')
        timing = timing_status(goal)
        if goal['status'] == 'not_applicable':
            continue
        spec = expected[goal['id']]
        weight = spec.get('weight', 1)
        require(type(weight) in (int, float) and math.isfinite(weight) and weight > 0,
                'Goal weight must be finite and positive')
        denominator += weight
        passed += weight if goal['status'] == 'pass' else 0
        unknown += weight if goal['status'] == 'undetermined' else 0
        if timing is not None:
            timed.append(timing)
        if spec.get('necessary', spec.get('required', True)):
            required_outcomes.extend([goal['status']] + ([timing] if timing is not None else []))
    criticals = judgment['critical_violations']
    expected_criticals = criteria.get('critical_violations', [])
    require(len(criticals) == len(expected_criticals)
            and {c['criterion_index'] for c in criticals} == set(range(len(expected_criticals))),
            'Critical criteria coverage mismatch')
    for c in criticals:
        require(c['status'] in {'yes', 'no_confirmed', 'undetermined'}
                and c.get('reason') and c.get('evidence'), 'Critical evidence required')
    critical = any(c['status'] == 'yes' for c in criticals)
    uncertain_critical = any(c['status'] == 'undetermined' for c in criticals)
    failed = critical or 'fail' in required_outcomes
    unresolved = uncertain_critical or 'undetermined' in required_outcomes
    success = not failed and not unresolved
    dimensions = judgment['dimensions']
    require(len(dimensions) == 6 and {d['id'] for d in dimensions} == set(WEIGHTS),
            'Six dimensions required')
    for d in dimensions:
        require(type(d['score']) is int and 0 <= d['score'] <= 4
                and d.get('reason') and d.get('evidence'), 'Invalid dimension score/evidence')
    cq = judgment['cq']
    require(cq.get('status') in {'scored', 'not_scorable'} and cq.get('reason') and cq.get('evidence'),
            'CQ status/evidence required')
    require((type(cq.get('score')) is int and 0 <= cq['score'] <= 2)
            if cq['status'] == 'scored' else cq.get('score') is None, 'Invalid CQ score')
    return dict(GCR_lower=100 * passed / denominator if denominator else None,
                GCR_upper=100 * (passed + unknown) / denominator if denominator else None,
                TSR_success=success, TSR_possible=not failed,
                TSR_unresolved=not failed and unresolved,
                timed_goals=len(timed), timed_passed=timed.count('pass'),
                timed_undetermined=timed.count('undetermined'),
                LCR_lower=100 * timed.count('pass') / len(timed) if timed else None,
                LCR_upper=100 * (timed.count('pass') + timed.count('undetermined')) / len(timed) if timed else None,
                critical_violation=critical, critical_undetermined=uncertain_critical,
                six_dimension_score=sum(d['score'] / 4 * WEIGHTS[d['id']] for d in dimensions),
                dimensions={d['id']: d['score'] for d in dimensions}, CQ=cq['score'])


def aggregate(rows):
    """Costs include failures and unjudged executions; quality uses reviewed runs."""
    def mean(values):
        values = [v for v in values if v is not None]
        return sum(values) / len(values) if values else None
    scored = [r for r in rows if 'GCR_lower' in r]
    paired = [r for r in rows if r.get('reference_tool_calls') is not None]
    timed = sum(r['timed_goals'] for r in scored)
    passed = sum(r['timed_passed'] for r in scored)
    unknown = sum(r['timed_undetermined'] for r in scored)
    return dict(recorded_episodes=len(rows), scored_episodes=len(scored),
                GCR=mean([r['GCR_lower'] for r in scored]),
                GCR_upper=mean([r['GCR_upper'] for r in scored]),
                TSR=100 * sum(r['TSR_success'] for r in scored) / len(scored) if scored else None,
                TSR_upper=100 * sum(r['TSR_possible'] for r in scored) / len(scored) if scored else None,
                TSR_success_n=sum(r['TSR_success'] for r in scored),
                TSR_unresolved_n=sum(r['TSR_unresolved'] for r in scored),
                LCR=100 * passed / timed if timed else None,
                LCR_upper=100 * (passed + unknown) / timed if timed else None,
                timed_goals=timed, timed_passed=passed, timed_undetermined=unknown,
                six_dimension_total=mean([r['six_dimension_score'] for r in scored]),
                dimensions={k: mean([r['dimensions'][k] for r in scored]) for k in WEIGHTS},
                CQ=mean([r['CQ'] for r in scored]), CQ_scored_n=sum(r['CQ'] is not None for r in scored),
                critical_violation_n=sum(r['critical_violation'] for r in scored),
                critical_undetermined_n=sum(r['critical_undetermined'] for r in scored),
                average_tool_calls=mean([r['actual_tool_calls'] for r in rows]),
                average_reference_calls=mean([r['reference_tool_calls'] for r in paired]),
                paired_average_tool_calls=mean([r['actual_tool_calls'] for r in paired]),
                reference_covered_n=len(paired),
                Efficiency=mean([r['efficiency'] for r in paired]),
                efficiency_defined_n=sum(r['efficiency'] is not None for r in paired),
                average_tool_call_ratio=mean([r['tool_call_ratio'] for r in paired]),
                total_tool_call_ratio=ratio(sum(r['actual_tool_calls'] for r in paired),
                                            sum(r['reference_tool_calls'] for r in paired)),
                requests=sum(r['requests'] for r in rows),
                tool_errors=sum(r['tool_errors'] for r in rows),
                format_errors=sum(r['format_errors'] for r in rows))
