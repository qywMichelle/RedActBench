"""Timed construction sandbox with private editable workflow records.

Record schemas describe operation syntax, never the semantically correct answer.
The evaluator separately checks identity, authorization and deadline evidence.
"""
from copy import deepcopy
from .creator_challenge import TimedCreatorTask
PROTOCOL = 'construction-workflow-v2.0'

class WorkflowTask(TimedCreatorTask):

    def __init__(self, case):
        super().__init__(case)
        self.triggered = set()

    def observe(self):
        observation = super().observe()
        observation['protocol'] = PROTOCOL
        observation['operations'] = deepcopy(observation['operations'])
        observation['operations']['set_record'] = 'target private record, expected_revision, fields object; values must fit its visible field_schema'
        return observation

    def _timed_apply(self, action):
        if action.get('action') != 'COMMIT':
            return super()._timed_apply(action)
        ops = action.get('operations')
        if not isinstance(ops, list):
            raise ValueError('operations must be a list')
        if len(ops) > self.case['budget']['writes_per_commit'] or self.writes + len(ops) > self.case['budget']['writes']:
            raise ValueError('Write budget exceeded')
        trial = deepcopy(self)
        normal = []
        changed = []
        for op in ops:
            if not isinstance(op, dict):
                raise ValueError('Each operation must be an object')
            target = op.get('target')
            if not isinstance(target, str):
                raise ValueError('Operation target must be a resource ID')
            item = trial.visible().get(target)
            if op.get('kind') != 'set_record':
                if item and item['kind'] == 'record':
                    raise ValueError('Records require set_record; text cannot change workflow state')
                normal.append(op)
                continue
            if not item or item['kind'] != 'record' or (not item.get('editable')):
                raise ValueError('Only an available own record can be changed')
            if type(op.get('expected_revision')) is not int or op['expected_revision'] != item['revision']:
                raise ValueError('Record revision mismatch')
            fields = op.get('fields')
            if not isinstance(fields, dict) or not fields:
                raise ValueError('Nonempty fields required')
            for key, value in fields.items():
                if key not in item['field_schema'] or value not in item['field_schema'][key]:
                    raise ValueError('Field or value outside visible schema')
            item['fields'].update(deepcopy(fields))
            item['revision'] += 1
            changed.append(target)
        normal_call = deepcopy(action)
        normal_call['operations'] = normal
        result = super(WorkflowTask, trial)._timed_apply(normal_call)
        trial.writes += len(changed)
        result['changed'] += changed
        trial.snapshots[-1]['operations'] = deepcopy(ops)
        for rule in trial.case.get('workflow_events', []):
            if rule['event_id'] in trial.triggered:
                continue
            trigger = rule['trigger']
            matched = any((o.get('kind') == trigger['kind'] and o.get('target') == trigger['target'] and all((o.get('fields', {}).get(k) == v for k, v in trigger.get('fields', {}).items())) for o in ops))
            if not matched:
                continue
            trial.triggered.add(rule['event_id'])
            for spec in rule['resources']:
                entry = deepcopy(spec)
                if entry['id'] in trial.resources:
                    raise ValueError('Event resource ID collision')
                entry['at'] = max(trial.now + rule['delay'], rule.get('not_before', 0))
                trial.resources[entry['id']] = entry
        self.__dict__.update(trial.__dict__)
        return result

    def record(self):
        record = super().record()
        record['protocol'] = PROTOCOL
        record['workflow_records'] = deepcopy({k: v for k, v in self.visible().items() if v['kind'] == 'record'})
        record['triggered_events'] = sorted(self.triggered)
        return record

def replay(case, record):
    env = WorkflowTask(case)
    for step in record['history']:
        env.observe()
        env.apply(step['action'])
    if env.record() != record:
        raise ValueError('Workflow replay mismatch')
    return env

def run_plan(case, plans):
    env = WorkflowTask(case)

    def call(action):
        env.observe()
        result = env.apply(action)
        if 'error' in result:
            raise AssertionError((env.now, action, result))
    for plan in plans:
        while env.now < plan['at'] and (not env.done):
            call({'action': 'WAIT', 'time': plan['at']})
        for i in range(0, len(plan.get('read', [])), 3):
            call({'action': 'READ', 'ids': plan['read'][i:i + 3]})
        if plan.get('ask'):
            call({'action': 'ASK', 'topics': plan['ask'], 'question': plan['question']})
        if plan.get('ops') or plan.get('handoff'):
            ops = deepcopy(plan.get('ops', []))
            revisions = {k: r['revision'] for k, r in env.resources.items()}
            for op in ops:
                if op['kind'] in ('edit', 'publish', 'remove_asset', 'set_record'):
                    op['expected_revision'] = revisions[op['target']]
                    revisions[op['target']] += 1
            call({'action': 'COMMIT', 'operations': ops, 'handoff': plan.get('handoff', env.handoff)})
    while not env.done:
        call({'action': 'WAIT', 'time': case['deadline']})
    replay(case, env.record())
    return env.record()
