"""Versioned deterministic forms; the v2.2 environment remains untouched.

Forms are visible business messages, not semantic classifications of free text.
Only actual rendered deliveries can trigger a structured external receipt.
"""
from copy import deepcopy
from .construction import WorkflowTask as PreviousWorkflowTask
PROTOCOL = 'construction-workflow-v2.3'

class WorkflowTask(PreviousWorkflowTask):

    def observe(self):
        observation = super().observe()
        observation['protocol'] = PROTOCOL
        observation['tool_protocol'] = {
            'call_format': 'One JSON object with top-level action and parameters, using the displayed tools and operations.',
            'budgets': 'Every call, including WAIT, FINISH and invalid calls, consumes one calls unit. A successful READ or ASK consumes one reads or asks unit per call, not per ID/topic. COMMIT consumes one writes unit per operation, within writes_per_commit; failed atomic commits do not consume writes.',
            'clock': 'READ, ASK, COMMIT and CHECK act at the current time, then advance the clock by one minute, capped at the deadline. Invalid calls also consume one minute unless the episode has ended. COMMIT effects and snapshots use the action start time; the returned observation is after this advance. The deadline or exhausted call budget freezes the episode.',
            'READ': 'ids must contain 1–3 currently available resource IDs. New resource notifications expose an index; use READ for their full contents. Own editable content is already observed.',
            'ASK': 'topics must contain 1–3 distinct published topic IDs, each not previously asked, with a nonempty question. Answers arrive after ' + str(self.case['answer_delay']) + ' simulated minutes and then require READ. A request whose answer would arrive at or after the deadline is rejected.',
            'COMMIT': 'operations is a list applied atomically; it does not manually jump to the next stage. Scheduled stages/events follow the clock rules. Editable objects require their current integer expected_revision; revisions increase on edits. Replies and DMs require a READ target in the correct channel. set_record uses only visible field_schema values. A private handoff is optional and may be empty; it does not perform external actions.',
            'text_limits': 'Authored edit, reply, DM, ASK question, CHECK reason and FINISH handoff text must be nonempty and at most 4000 characters. COMMIT handoff may be empty but is also limited to 4000 characters.',
            'WAIT': 'time must be a future integer no later than the deadline. WAIT advances to that time or wakes earlier for a new resource or scheduled reminder; it does not add another minute after waking.',
            'CHECK': 'time must be a future integer no later than the deadline, with a nonempty reason. At most six active reminders are allowed; CHECK itself takes one minute.',
            'FINISH': 'A nonempty private handoff ends work immediately with zero simulated minutes. Early finish does not cancel existing task obligations or turn a handoff into a public delivery.'
        }
        if self.case.get('message_forms'):
            observation['operations']['send_form'] = 'target observed DM, form_id from visible message_forms, fields object; renders and sends the displayed template, one write; no free-text override'
            observation['message_forms'] = deepcopy(self.case['message_forms'])
        return observation

    def _timed_apply(self, action):
        if action.get('action') != 'COMMIT':
            return super()._timed_apply(action)
        normalized = deepcopy(action)
        if not isinstance(normalized.get('operations'), list):
            raise ValueError('operations must be a list')
        staged = deepcopy(self.visible())
        for op in normalized['operations']:
            if not isinstance(op, dict):
                raise ValueError('Each operation must be an object')
            if op.get('kind') == 'set_record' and op.get('target') in staged:
                staged[op['target']].setdefault('fields', {}).update(op.get('fields', {}))
        for op in normalized['operations']:
            if op.get('kind') != 'send_form':
                if op.get('kind') == 'send_dm':
                    op.pop('fields', None)
                continue
            form_id = op.get('form_id')
            form = self.case.get('message_forms', {}).get(form_id)
            if not form or op.get('target') != form['target']:
                raise ValueError('Unknown form or incorrect recipient; message not delivered')
            fields = op.get('fields')
            if not isinstance(fields, dict) or set(fields) != set(form['field_schema']):
                raise ValueError('Form requires exactly its visible fields')
            if any((value not in form['field_schema'][key] for key, value in fields.items())):
                raise ValueError('Form field outside visible schema')
            if 'text' in op:
                raise ValueError('Form text is rendered from fields; free-text override forbidden')
            if form.get('requires_current_pickup_authorization'):
                rule = self.case['pickup_form_authorizations'][fields['order']]
                grant = rule['grant'] in self.visible()
                revoked = rule.get('revocation') in self.visible()
                record = staged[rule['record']]['fields']
                if not grant or revoked or record['proxy'] != 'W' or (record['pickup_state'] != 'reserved') or (fields['item'] != rule['item']):
                    raise ValueError('No matching current owner authorization and reservation; message not delivered')
            text = form['template'].format(**fields)
            op.clear()
            op.update(kind='send_dm', target=form['target'], text=text, fields=dict(fields, form_id=form_id))
        return super()._timed_apply(normalized)

    def record(self):
        result = super().record()
        result['protocol'] = PROTOCOL
        return result

def replay(case, record):
    env = WorkflowTask(case)
    for step in record['history']:
        env.observe()
        env.apply(step['action'])
    if env.record() != record:
        raise ValueError('v2.3 workflow replay mismatch')
    return env

def run_actions(case, actions, allow_errors=False):
    env = WorkflowTask(case)
    for action in actions:
        env.observe()
        result = env.apply(deepcopy(action))
        if 'error' in result and (not allow_errors):
            raise AssertionError((env.now, action, result))
    record = env.record()
    replay(case, record)
    return record

def run_plan(case, plans):
    env = WorkflowTask(case)

    def call(action):
        env.observe()
        result = env.apply(action)
        if 'error' in result:
            raise AssertionError((env.now, action, result))
    for plan in plans:
        while env.now < plan['at'] and (not env.done):
            call(dict(action='WAIT', time=plan['at']))
        for i in range(0, len(plan.get('read', [])), 3):
            call(dict(action='READ', ids=plan['read'][i:i + 3]))
        if plan.get('ask'):
            call(dict(action='ASK', topics=plan['ask'], question=plan['question']))
        if plan.get('ops') or plan.get('handoff'):
            ops = deepcopy(plan.get('ops', []))
            revisions = {k: r['revision'] for k, r in env.resources.items()}
            for op in ops:
                if op['kind'] in ('edit', 'publish', 'remove_asset', 'set_record'):
                    op['expected_revision'] = revisions[op['target']]
                    revisions[op['target']] += 1
            call(dict(action='COMMIT', operations=ops, handoff=plan.get('handoff', env.handoff)))
    while not env.done:
        call(dict(action='WAIT', time=case['deadline']))
    result = env.record()
    replay(case, result)
    return result
