"""Portable fictional workbench with request cards and concurrent field edits.

The immutable base supplies resource projection and ordinary tools. Structured
cards represent terms actually delivered to counterparties; they are not a
semantic score for the accompanying prose. All social text still needs review.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import re

_spec = importlib.util.spec_from_file_location('batch012_core', Path(__file__).with_name('core_runtime.py'))
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
digest = _core.digest
valid_field = _core.valid_field
PROTOCOL = 'redact-b012-explicit-interface-content-approval-v2'


def content_snapshot(document):
    """Bind every content/scope attribute, excluding only lifecycle counters.

    Channel, recipient, privacy/permission fields and any later scope metadata
    therefore cannot inherit approval after being changed. Empty assets have
    the same meaning whether omitted or explicitly supplied by WRITE.
    """
    snapshot = {key: deepcopy(value) for key, value in document.items()
                if key not in {'revision', 'status'}}
    snapshot.setdefault('assets', [])
    return snapshot


def visible_schema_error(key, schema):
    """Explain only the already-visible field contract, never hidden terms."""
    if isinstance(schema, list):
        description = 'one of ' + repr(schema)
    else:
        description = schema.get('type', 'declared value')
        if schema.get('enum'):
            description += ' from ' + repr(schema['enum'])
        if schema.get('type') == 'array':
            item = schema.get('items', {})
            description += ' of ' + item.get('type', 'declared items')
            if item.get('enum'):
                description += ' from ' + repr(item['enum'])
        if 'minimum' in schema:
            description += ', minimum ' + str(schema['minimum'])
        if 'maximum' in schema:
            description += ', maximum ' + str(schema['maximum'])
    return ValueError('Invalid visible field ' + repr(key) + ': expected ' + description)


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
            raise ValueError('Unknown visible field ' + repr(key) + '; allowed fields: ' + ', '.join(schema))
        spec=deepcopy(schema[key])
        if isinstance(spec,list):
            spec=[normalized_time_term(key,v) for v in spec]
        elif isinstance(spec,dict) and spec.get('enum'):
            spec['enum']=[normalized_time_term(key,v) for v in spec['enum']]
        if not valid_field(normalized_time_term(key,value),spec):
            raise visible_schema_error(key, spec)


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
        for item in effect.get('backend_add', []):
            self._unrevealed[item['id']] = deepcopy(item)
            self.reserved.add(item['id'])
        visible=set(self.resources)
        exposed=visible | {r['id'] for key in ('reveal','add') for r in effect.get(key,[])}
        combined={**self._unrevealed,**self.resources}
        changed = set(effect.get('set', {})) | set(effect.get('patch', {})) | {c['to'] for c in effect.get('copy', [])}
        old = {rid: combined[rid].get('revision') for rid in changed if rid in combined}
        self.resources=combined
        super().effect(effect)
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

    def apply(self, action):
        # All rejected calls are atomic, including dependency/parameter checks.
        if not isinstance(action, dict):
            raise ValueError('Action must be a JSON object')
        saved = deepcopy(self.__dict__)
        try:
            # Fixed automatic events due at successful completion have priority
            # over a newly completed edit, cancellation or hold at that instant.
            if action.get('action') not in ('WAIT', 'FINISH'):
                previous_time = self.time
                self.time += 1
                self.reveal()
                self.time = previous_time
            result=self._apply(action)
            parent=self.resources.get(action.get('target'),{})
            delivered=result.get('delivered')
            if delivered and delivered in self.resources and parent.get('write_guard'):
                self.resources[delivered]['write_guard']=deepcopy(parent['write_guard'])
                self.history[-1]['snapshot']=deepcopy(self.resources)
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
        if not isinstance(op, str):
            raise ValueError('action must name one visible tool as a string')
        if self.done or self.time >= self.case['deadline']:
            raise ValueError('Session ended')
        if self.calls >= self.case['budget']['calls']:
            raise ValueError('Budget exhausted')
        before = self.time
        target = action.get('target')
        if target is not None and not isinstance(target, str):
            raise ValueError('target must be a visible resource ID string')
        resource = self.resources.get(target, {})

        # Resolve only against the current projection. A guessed future ID is
        # indistinguishable from an unknown ID, and hidden topics stay hidden.
        targeted = {'LOOKUP', 'ASK', 'OPERATE', 'WRITE', 'SET', 'PATCH', 'REPLY', 'SEND_LINK'}
        if op in targeted and not resource:
            raise ValueError('Unknown or unrevealed target; use a currently visible resource or directory')
        if op == 'ASK':
            if action.get('topic') not in resource.get('topics', []):
                raise ValueError('Topic not listed for visible target; allowed topics: ' + ', '.join(resource.get('topics', [])))
            details = action.get('details', {})
            if not isinstance(details, dict):
                raise ValueError('Concrete request card must be an object')
            schema = resource.get('request_schema', {})
            if schema:
                validate_card(details, schema)
            elif details:
                raise ValueError('This visible contact accepts no request-card fields')
        if op == 'OPERATE':
            choices = [item['key'] for item in resource.get('options', [])]
            if action.get('choice') not in choices:
                raise ValueError('Operation choice not listed for visible target; allowed choices: ' + ', '.join(choices))
            if not isinstance(action.get('params', {}), dict):
                raise ValueError('Operation params must be an object')

        # A service role is checked at the actual successful operation time.
        # Reading a record never grants the right to speak through its account.
        guard = resource.get('write_guard')
        if guard and op in ('WRITE', 'SET', 'PATCH', 'REPLY', 'SEND_LINK'):
            self._condition_time = self.time + 1
            allowed = self.matches(guard)
            self.__dict__.pop('_condition_time', None)
            if not allowed:
                raise ValueError('Current account role does not permit this write/channel')

        if op == 'ASK':
            answer_key = resource.get('id', '') + '/' + str(action.get('topic'))
            configured = self.case.get('answers', {}).get(answer_key, {})
            if 'not_before' in configured and not configured.get('bind_snapshot'):
                prepared=deepcopy(configured)
                prepared['delay']=max(0, prepared.pop('not_before')-(self.time+1))+prepared.get('delay', 0)
                self.case['answers'][answer_key]=prepared
                try:
                    return self._apply(action)
                finally:
                    self.case['answers'][answer_key]=configured
            binding = configured.get('bind_snapshot')
            if binding:
                document = self.resources.get(binding['document'], {})
                snapshot = content_snapshot(document)
                fingerprint = digest(snapshot)
                approval_id = binding['approval_id']
                if self.resources.get(approval_id, {}).get('snapshot_hash') == fingerprint:
                    raise ValueError('This exact content/scope snapshot is already approved; lifecycle-only changes need no new review')
                if any(event.get('review_snapshot_hash') == fingerprint
                       and event.get('review_answer_key') == answer_key
                       and event['id'] not in self.fired for event in self.pending):
                    raise ValueError('Review already pending for this exact content/scope snapshot')
                previous = binding.get('previous_approval')
                if previous and self.resources.get(previous, {}).get('snapshot_hash') != fingerprint:
                    raise ValueError('Previous reviewer has not approved this exact current snapshot')
                if action.get('details', {}).get('revision') != document.get('revision'):
                    raise ValueError('Review request must name the actual current document revision')
                modified = deepcopy(configured)
                duration=configured.get('delay', 0)
                received=self.time + 1
                earliest=configured.get('not_before', received)
                starts=[max(received, earliest, left) for left,right in configured.get('review_windows', [[received, self.case['deadline']]])
                        if max(received, earliest, left) + duration <= right]
                if not starts:
                    raise ValueError('No complete review window remains; preserve the draft and hand off actual unapproved status')
                modified['delay']=min(starts)+duration-received
                modified.pop('not_before', None)
                modified['add'] = [dict(id=approval_id, kind='approval', channel='private', editable=False,
                    text=binding.get('receipt_text', 'Approved this submitted snapshot only; later edits need new review.'),
                    document=binding['document'], snapshot=deepcopy(snapshot), snapshot_hash=fingerprint,
                    requested_at=self.time + 1, reviewer=resource.get('recipient'))]
                modified['review_snapshot_hash'] = fingerprint
                modified['review_answer_key'] = answer_key
                # Re-review changed content through the actual same office.
                # Each request gets a new event identity; old approvals never
                # authorize changed content while a new review is pending.
                modified['request_instance'] = str(self.calls + 1)
                self.asked.discard(answer_key)
                self.case['answers'][answer_key] = modified
                try:
                    return self._apply_without_binding(action, answer_key, configured)
                finally:
                    self.case['answers'][answer_key] = configured

        if op == 'OPERATE':
            operation_key = resource.get('id', '') + '/' + str(action.get('choice'))
            configured = self.case.get('operations', {}).get(operation_key, {})
            exposing = configured.get('expose_backend')
            if exposing:
                if any(rid not in self._unrevealed and rid not in self.resources for rid in exposing):
                    raise ValueError(configured.get('missing_backend_message',
                        'Actual service record is not available yet. Check the documented service window and visible prerequisites; this is not evidence of completion.'))
                modified = deepcopy(configured)
                modified.pop('expose_backend', None)
                modified.setdefault('add', []).extend(deepcopy(self._unrevealed.get(rid, self.resources.get(rid))) for rid in exposing)
                modified['facts'] = {'inspected_actual_objects': exposing}
                self.case['operations'][operation_key] = modified
                try:
                    return self._apply(action)
                finally:
                    self.case['operations'][operation_key] = configured
            publishing = configured.get('bind_publication')
            if publishing:
                document = self.resources.get(publishing['document'], {})
                snapshot = content_snapshot(document)
                fingerprint = digest(snapshot)
                if any(self.resources.get(rid, {}).get('snapshot_hash') != fingerprint
                       for rid in publishing['approvals']):
                    raise ValueError('Every named publisher must have approved this exact current snapshot')
                modified = deepcopy(configured)
                target = publishing['public_id']
                self.reserved.add(target)
                public = dict(id=target, kind='post', channel='public', editable=True,
                    text=document.get('text', ''), assets=deepcopy(document.get('assets', [])),
                    status='published', source_snapshot_hash=fingerprint,
                    source_revision=document.get('revision'), created_at=publishing.get('at', self.time + 1))
                if publishing.get('write_guard'):
                    public['write_guard']=deepcopy(publishing['write_guard'])
                if 'at' in publishing:
                    modified.setdefault('set', {}).setdefault(publishing['queue'], {})['status'] = 'enabled'
                    unique = 'publication-' + target + '-' + str(self.calls + 1)
                    self.pending.append(dict(id=unique, at=publishing['at'],
                        when={'fields': {publishing['queue']: {'status': 'enabled'}}}, backend_add=[public],
                        # The local scheduler observes dispatch to the renderer,
                        # not a read of the independently served public page.
                        set={publishing['queue']: {'status': 'dispatched', 'reserved_public_id': target}}))
                else:
                    modified.setdefault('add', []).append(public)
                modified['facts'] = dict(snapshot_hash=fingerprint, source_revision=document.get('revision'),
                    publication='scheduled_renderer_job' if 'at' in publishing else 'actual_publication')
                modified['facts']['reserved_public_id' if 'at' in publishing else 'public_id']=target
                self.case['operations'][operation_key] = modified
                try:
                    return self._apply_without_binding(action, operation_key, configured, operation=True)
                finally:
                    self.case['operations'][operation_key] = configured

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
            complete = not answer or request_matches(details, answer.get('request_fields', {}))
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
                    unique = '-' + answer['request_instance'] if answer.get('request_instance') else (
                        '-' + str(self.calls + 1) if topic in resource.get('repeatable_topics', []) else '')
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

    def _apply_without_binding(self, action, key, original, operation=False):
        """Re-enter ordinary protocol with the one prepared business binding."""
        collection = self.case['operations' if operation else 'answers']
        prepared = deepcopy(collection[key])
        prepared.pop('bind_publication' if operation else 'bind_snapshot', None)
        collection[key] = prepared
        try:
            return self._apply(action)
        finally:
            collection[key] = original

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
