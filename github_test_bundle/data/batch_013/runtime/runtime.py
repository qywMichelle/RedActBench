"""Portable fictional workbench with request cards and concurrent field edits.

The immutable base supplies resource projection and ordinary tools. Structured
cards represent terms actually delivered to counterparties; they are not a
semantic score for the accompanying prose. All social text still needs review.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import re

_spec = importlib.util.spec_from_file_location('batch013_core', Path(__file__).with_name('core_runtime.py'))
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
digest = _core.digest
valid_field = _core.valid_field
PROTOCOL = 'redact-b013-request-cards-versioned-fields-v1'


def normalized_time_term(key,value):
    """Accept ordinary clock-range typography without rewriting business IDs."""
    time_key=key in {'window','first','second','observing','table_window','sessions','blocks','arrival','late_arrival'} or key.endswith(('_window','_interval'))
    if not time_key or not isinstance(value,str):
        return value
    if not re.search(r'(?:\bt\d+|\b\d{1,2}:\d{2})\s*[-\u2010-\u2015]\s*(?:t?\d+|\d{1,2}:\d{2})',value):
        return value
    result=re.sub(r'(?<=\d)\s*[-\u2010-\u2015]\s*(?=t?\d)','-',value)
    return re.sub(r'\s*;\s*',';',result).strip()


def request_matches(actual, expected):
    """Match frozen concrete terms, allowing additional declared card fields."""
    return isinstance(actual, dict) and all(normalized_time_term(k,actual.get(k)) == normalized_time_term(k,v) for k, v in expected.items())


def validate_card(card, schema):
    if not isinstance(card, dict):
        raise ValueError('Concrete request card must be an object')
    for key,value in card.items():
        if key not in schema:
            raise ValueError('Request card outside visible schema')
        spec=deepcopy(schema[key])
        if isinstance(spec,list):
            spec=[normalized_time_term(key,v) for v in spec]
        elif isinstance(spec,dict) and spec.get('enum'):
            spec['enum']=[normalized_time_term(key,v) for v in spec['enum']]
        if not valid_field(normalized_time_term(key,value),spec):
            raise ValueError('Request card outside visible schema')


class World(_core.World):
    def __init__(self, case):
        super().__init__(case)
        # Lookup entities exist in the fictional world before the agent views
        # them. Future messages/events are deliberately not initialized here.
        # Generated approval evidence owns a reserved ID before any request.
        if any(a.get('assemble_approval') for a in self.case.get('answers', {}).values()):
            self.reserved.add('current-approval')
        self._unrevealed={}
        for resources in self.case.get('lookups',{}).values():
            for resource in resources:
                if resource['id'] not in self.resources:
                    self._unrevealed.setdefault(resource['id'],deepcopy(resource))
        # Interactive use and action-only replay start from the same projection.
        self.reveal()

    def matches(self, condition):
        state={**self._unrevealed,**self.resources}
        if not (all(rid in self.resources for rid in condition.get('revealed',[]))
                and all(state.get(rid,{}).get('fields',{}).get(k)==value
                        for rid,fields in condition.get('fields',{}).items() for k,value in fields.items())
                and all(state.get(rid,{}).get(k)==value
                        for rid,fields in condition.get('attributes',{}).items() for k,value in fields.items())):
            return False
        window=condition.get('time',{})
        now=getattr(self,'_condition_time',self.time)
        if window and not window.get('minimum',float('-inf')) <= now <= window.get('maximum',float('inf')):
            return False
        return all(self.matches(c) for c in condition.get('all', [])) and (
            not condition.get('any') or any(self.matches(c) for c in condition['any'])) and (
            not condition.get('not') or not self.matches(condition['not']))

    def effect(self, effect):
        visible=set(self.resources)
        exposed=visible | {r['id'] for key in ('reveal','add') for r in effect.get(key,[])}
        combined={**self._unrevealed,**self.resources}
        changed = set(effect.get('set', {})) | set(effect.get('patch', {})) | {c['to'] for c in effect.get('copy', [])}
        old = {rid: combined[rid].get('revision') for rid in changed if rid in combined}
        self.resources=combined
        super().effect(effect)
        for rid,rows in effect.get('append_rows',{}).items():
            self.resources[rid].setdefault('rows',[]).extend(deepcopy(rows))
        for rid, revision in old.items():
            if revision is not None and 'revision' not in effect.get('patch', {}).get(rid, {}):
                self.resources[rid]['revision'] = revision + 1
        self._unrevealed={rid:r for rid,r in self.resources.items() if rid not in exposed}
        self.resources={rid:r for rid,r in self.resources.items() if rid in exposed}

    def reveal(self):
        # Dependencies introduced by one same-time event are visible to the next.
        while True:
            before = len(self.fired)
            super().reveal()
            if len(self.fired) == before:
                break

    def observe(self):
        view = super().observe()
        view['protocol'] = PROTOCOL
        return view

    def _record_step(self, action, before, result):
        self.calls += 1
        for event in self.case.get('action_events', []):
            if result.get('applied') is False or result.get('clarification_required'):
                continue
            if event['id'] in self.fired or any(e['id'] == event['id'] for e in self.pending):
                continue
            if all(action.get(k) == v for k, v in event['trigger'].items()) and self.matches(event.get('requires', {})):
                pending = deepcopy(event)
                pending['at'] = self.time + event.get('delay', 0)
                self.pending.append(pending)
        self.reveal()
        if self.time >= self.case['deadline']:
            self.done = True
        result['pending_deliveries'] = self.pending_view()
        self.history.append(dict(step=self.calls, time_before=before, time=self.time,
                                 action=deepcopy(action), result=deepcopy(result),
                                 snapshot=deepcopy(self.resources), pending_deliveries=self.pending_view()))
        return result

    def pending_view(self):
        # Due times are private external scheduler state, not revealed estimates.
        return [{'delivery_token':'pending-'+str(i+1),'status':'scheduled'}
                for i,e in enumerate(self.pending) if e['id'] not in self.fired]

    def apply(self, action):
        # All rejected calls are atomic, including dependency/parameter checks.
        saved = deepcopy(self.__dict__)
        try:
            # Fixed external events at successful completion precede that action.
            # The saved transaction also rolls these effects back on rejection.
            if action.get('action') not in ('WAIT','FINISH'):
                start=self.time
                self.time=start+1
                self.reveal()
                self.time=start
            result=self._apply(action)
            if self.history:
                self.history[-1]['backend_snapshot']=deepcopy(self._unrevealed)
            return result
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(saved)
            raise

    def _apply(self, original):
        action = deepcopy(original)
        op = action.get('action')
        if self.done or self.time >= self.case['deadline']:
            raise ValueError('Session ended')
        if self.calls >= self.case['budget']['calls']:
            raise ValueError('Budget exhausted')
        before = self.time
        resource = self.resources.get(action.get('target'), {})

        if op=='LOOKUP':
            entry=action.get('entry')
            if entry not in [item['key'] for item in resource.get('entries',[])]:
                raise ValueError('Entry not in visible directory')
            found=self.case.get('lookups',{}).get(resource['id']+'/'+entry)
            if found is None:
                raise ValueError('Missing directory configuration')
            for item in found:
                rid=item['id']
                if rid not in self.resources:
                    self.resources[rid]=self._unrevealed.pop(rid,deepcopy(item))
            result={'resources':[deepcopy(self.resources[item['id']]) for item in found]}
            self.time+=1
            return self._record_step(action,before,result)

        if op == 'WAIT':
            target=action.get('until')
            if type(target) is not int or not self.time < target <= self.case['deadline']:
                raise ValueError('Invalid wait')
            wake=target
            for candidate in range(self.time+1,target+1):
                self._condition_time=candidate
                ready=any(e['id'] not in self.fired and e.get('at',10**9)<=candidate
                          and self.matches(e.get('when',{}))
                          for e in self.case.get('events',[])+self.pending)
                self.__dict__.pop('_condition_time',None)
                if ready:
                    wake=candidate
                    break
            self.time=wake
            return self._record_step(action,before,dict(requested_until=target,waited_until=wake))

        if op in ('WRITE', 'SET', 'PATCH') and 'revision' in resource:
            if type(action.get('expected_revision')) is not int:
                raise ValueError('expected_revision is required for versioned content')
            if action['expected_revision'] != resource['revision']:
                self.time += 1
                return self._record_step(action, before, dict(conflict=True, applied=False,
                    target=resource['id'], current_revision=resource['revision']))

        if op in ('PATCH', 'SET', 'WRITE'):
            if not resource.get('editable'):
                raise ValueError('Not owned editable content')
            if op in ('PATCH', 'SET'):
                fields = action.get('fields')
                schema = resource.get('field_schema', {})
                if not isinstance(fields, dict) or not fields or any(
                        k not in schema or not valid_field(v, schema[k]) for k, v in fields.items()):
                    raise ValueError('Fields outside visible schema')
                resource.setdefault('fields', {}).update(deepcopy(fields))
            else:
                if not isinstance(action.get('text'), str):
                    raise ValueError('Text required')
                status = action.get('status', resource.get('status', 'published'))
                assets = action.get('assets', resource.get('assets', []))
                if status not in ('draft', 'published', 'withdrawn'):
                    raise ValueError('Invalid status')
                if not isinstance(assets, list) or any(a not in self.case.get('asset_catalog', []) for a in assets):
                    raise ValueError('Unknown asset')
                resource.update(text=action['text'], status=status, assets=deepcopy(assets))
            if 'revision' in resource:
                resource['revision'] += 1
            self.time += 1
            return self._record_step(action, before, dict(updated=resource['id'],
                applied=True, revision=resource.get('revision'), fields=deepcopy(resource.get('fields', {}))))

        if op == 'ASK':
            topic = action.get('topic')
            key = resource.get('id', '') + '/' + str(topic)
            if topic not in resource.get('topics', []):
                raise ValueError('Topic not listed')
            if not isinstance(action.get('text'), str) or not action['text'].strip():
                raise ValueError('Question required')
            if key in self.asked and topic not in resource.get('repeatable_topics', []):
                raise ValueError('Request already sent')
            details = action.get('details', {})
            schema = resource.get('request_schema', {})
            if schema:
                validate_card(details, schema)
            elif details:
                raise ValueError('This contact has no request-card fields')
            answer = deepcopy(self.case.get('answers', {}).get(key))
            if answer:
                for variant in answer.get('variants', []):
                    if self.matches(variant.get('when', {})) and request_matches(details, variant.get('request_fields', {})):
                        answer.update(deepcopy(variant))
                        break
            self.time += 1
            complete = not answer or (request_matches(details, answer.get('request_fields', {})) and all(k in details and (not isinstance(details[k],str) or bool(details[k].strip())) for k in answer.get('required_fields',[])))
            if answer and complete:
                for check in answer.get('request_checks', []):
                    value = details.get(check['field'])
                    if check['kind'] == 'future_deadline':
                        complete = complete and type(value) is int and self.time < value <= check['maximum']
                    elif check['kind'] == 'state_condition':
                        complete = complete and self.matches(check['condition'])
                    elif check['kind'] == 'set_equals':
                        complete = complete and isinstance(value, list) and len(value) == len(set(value)) and set(value) == set(check['values'])
                    elif check['kind'] == 'current_roster':
                        expected = [k for k, v in self.resources[check['resource']]['fields'].items()
                                    if v == check.get('status', 'confirmed')]
                        complete = complete and isinstance(value, list) and len(value) == len(set(value)) and set(value) == set(expected)
                    else:
                        raise ValueError('Unknown visible business request check')
            result = dict(request_sent=key, channel='private', recipient=resource.get('recipient'),
                          detail_card=deepcopy(details), request_text=action['text'], reply_guaranteed=False)
            if not complete:
                # A malformed proposal does not consume the sole business topic.
                result.update(clarification_required=True, consent_created=False,
                              message=answer.get('clarification', 'Please state the concrete arrangement using the visible request card.'))
            else:
                self.asked.add(key)
                if answer:
                    if answer.get('assemble_approval'):
                        cfg = answer['assemble_approval']
                        roster = deepcopy(details[cfg['roster_field']])
                        source = self.resources[cfg['register']]
                        revision = source.get('revision', 0)
                        answer['add'] = [dict(id='current-approval', kind='evidence', channel='private', editable=False,
                            text='Approved only this submitted snapshot: ' + ', '.join(roster) + '. Register revision ' + str(revision) + '. Later changes require a new review.',
                            approved_roster=roster, approved_register_revision=revision, requested_at=self.time)]
                        answer.setdefault('set', {})[cfg['approval_state']] = dict(approved=True, roster=roster, register_revision=revision)
                    deadline_field=answer.get('reply_deadline_field')
                    if deadline_field and self.time+answer.get('delay',0)>details[deadline_field]:
                        expiry=deepcopy(answer['expiration_effect'])
                        expiry['delay']=max(0,details[deadline_field]-self.time)
                        answer=expiry
                    unique = '-' + str(self.calls + 1) if topic in resource.get('repeatable_topics', []) else ''
                    answer.update(id='answer-' + key + unique, at=self.time + answer.get('delay', 0))
                    self.pending.append(answer)
            return self._record_step(action, before, result)

        if op == 'OPERATE':
            choice = action.get('choice')
            if choice not in [x['key'] for x in resource.get('options', [])]:
                raise ValueError('Operation choice not listed')
            operation_key = resource['id'] + '/' + choice
            original_spec = self.case['operations'][operation_key]
            spec = deepcopy(original_spec)
            params = action.get('params', {})
            schema = spec.get('param_schema', resource.get('param_schema', {}))
            if schema:
                validate_card(params, schema)
            elif params:
                raise ValueError('This operation accepts no parameters')
            if not request_matches(params, spec.get('param_values', {})):
                raise ValueError(spec.get('parameter_message', 'Parameters do not match the visible service terms'))
            # Service grants/windows apply at successful completion, not launch.
            self._condition_time=self.time+1
            if spec.get('param_variants'):
                variant = next((v for v in spec['param_variants']
                                if request_matches(params, v.get('param_values', {}))), None)
                if variant is None:
                    raise ValueError(spec.get('parameter_message', 'Requested arrangement unavailable under current service terms'))
                if not self.matches(variant.get('requires', {})):
                    raise ValueError(variant.get('requirement_message', 'Requested arrangement lacks the required actual consent or resource state'))
                # Preserve global requirements as well as this arrangement's.
                if not self.matches(original_spec.get('requires', {})):
                    raise ValueError(original_spec.get('requirement_message', 'Required actual record unavailable'))
                spec.update(deepcopy(variant))
            # Ordinary base execution checks actual state and emits its receipt.
            self.case['operations'][operation_key] = spec
            try:
                result = super().apply(action)
            finally:
                self.case['operations'][operation_key] = original_spec
                self.__dict__.pop('_condition_time',None)
            result['submitted_params'] = deepcopy(params)
            self.history[-1]['result'] = deepcopy(result)
            return result

        result = super().apply(action)
        return result

    def record(self):
        record = super().record()
        record['protocol'] = PROTOCOL
        record['unrevealed_state']=deepcopy(self._unrevealed)
        return record


def run(case, actions):
    world = World(case)
    for action in actions:
        world.apply(action)
    return world.record()


def replay(case, record):
    expected = record.get('simulation', record)
    actual = run(case, [s['action'] for s in expected['history']])
    if actual != expected:
        raise ValueError('Replay mismatch')
    return actual


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', required=True)
    parser.add_argument('--actions')
    parser.add_argument('--replay')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    case = json.loads(Path(args.world).read_text())
    result = replay(case, json.loads(Path(args.replay).read_text())) if args.replay else run(case, json.loads(Path(args.actions).read_text()))
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'steps': len(result['history']), 'done': result['done']}))
