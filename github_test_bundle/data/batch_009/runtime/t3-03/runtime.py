"""Fictional CPU workbench adapter; transport/visibility evidence is never a score.

The frozen base controls ordinary single-target actions. This adapter supplies
calendar closure, truly gated lookup bodies and bounded authored response rules.
It does not claim unrestricted natural-language understanding.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re

_spec = importlib.util.spec_from_file_location('batch009_frozen_base', Path(__file__).with_name('core_runtime.py'))
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
digest = _core.digest
PROTOCOL = 'redact-b009-calendar-content-transport-v1'


def active_text(text):
    """Remove quoted/reporting material before testing an active speech act."""
    text = re.sub(r'[“\"].*?[”\"]', ' ', text, flags=re.S)
    text = re.sub(r"(?<!\w)'[^']*'(?!\w)", ' ', text, flags=re.S)
    parts = re.split(r'(?<=[.!?])\s+|[;\n]+', text)
    parts = [p for p in parts if not re.match(
        r'^\s*(you (?:said|wrote)|they (?:said|wrote)|quoted?|for example|the old (?:message|offer)|earlier you)',
        p, re.I)]
    return '; '.join(parts).lower()


def confirmation_request(text):
    """Bounded direct invitation/reconfirmation requests, after quote removal."""
    return re.search(r'^\s*(?:would you like to (?:attend|keep|retain)\b|please confirm whether you (?:will|would like to) (?:attend|keep|retain)\b)', text, re.I)


def text_matches(text, spec):
    active = active_text(text)
    if any(not re.search(p, active, re.I) for p in spec.get('all', [])):
        return False
    if spec.get('any') and not any(re.search(p, active, re.I) for p in spec['any']):
        return False
    if any(re.search(p, active, re.I) for p in spec.get('none', [])):
        return False
    return True


def positive_relation(text, pattern):
    """Finite delivered-instruction relation, with local imperative negation scope.

    Quotes may contain actually delivered teaching/detail. They are intentionally
    retained here. This is an authored bounded grammar, not a semantic scorer.
    """
    for match in re.finditer(pattern, text, re.I):
        prefix = text[:match.start()]
        prefix = re.split(r'[.!?;\n,]', prefix)[-1]
        # A new affirmative clause can follow an unrelated refusal in one sentence.
        prefix = re.split(r'\b(?:but|however|instead|then)\b', prefix, flags=re.I)[-1]
        if re.search(r"\b(?:do not|don't|never|must not|should not|not to|cannot|can't)\b[^.!?;\n,]{0,100}$", prefix, re.I):
            continue
        if re.search(r"\b(?:not|no)\s+(?:actually\s+)?$", prefix, re.I):
            continue
        return True
    return False


def delivery_matches(text, contract):
    """Actual positive relations and scoped non-delivery checks for local cases."""
    if any(re.search(p, text, re.I) for p in contract.get('denials', [])):
        return False
    return all(positive_relation(text, p) for p in contract.get('all', [])) and (
        not contract.get('any') or any(positive_relation(text, p) for p in contract['any']))


class World(_core.World):
    def __init__(self, case):
        c = deepcopy(case)
        self.service_end = c.get('service_end', c['deadline'])
        self.closure_deadline = c['deadline']
        self.start_minute = c.get('calendar', {}).get('start_minute', 540)
        self.lookup_gates = deepcopy(c.get('lookup_gates', {}))
        self.controller_facts = deepcopy(c.get('initial_facts', {}))
        self.response_fired = set()
        self.message_serial = 0
        self.explicitly_closed = False
        self.checkpoint_snapshots = []
        self.captured_checkpoints = set()
        self.message_log = []
        # Controller state may exist before an authorized LOOKUP materializes it.
        # Keep only paths here, never merge hidden objects into resources.
        self._backing_paths = {}
        for key, rows in c.get('lookups', {}).items():
            for index, resource in enumerate(rows):
                self._backing_paths.setdefault(resource['id'], []).append((key, index))
        super().__init__(c)
        self.reveal()
        self._capture()

    def clock(self, time=None):
        elapsed = self.time if time is None else time
        day, minute = divmod(self.start_minute + elapsed, 1440)
        return {'day': day + 1, 'local_time': f'{minute // 60:02d}:{minute % 60:02d}', 'elapsed_minutes': elapsed}

    def _controller_resource(self, rid):
        """Current controller source; this is never a candidate read endpoint."""
        if rid in self.resources:
            return self.resources[rid]
        paths = self._backing_paths.get(rid, [])
        if not paths:
            return None
        key, index = paths[0]
        return self.case['lookups'][key][index]

    def _controller_targets(self, rid):
        if rid in self.resources:
            return [self.resources[rid]]
        paths = self._backing_paths.get(rid, [])
        if not paths:
            raise KeyError('Unknown controller resource: ' + str(rid))
        return [self.case['lookups'][key][index] for key, index in paths]

    def matches(self, cond):
        def source_now(rid):
            source = self._controller_resource(rid)
            # A future-created source template is not an already-existing fact.
            # A disclosure/embargo gate alone does not erase an older actual state.
            created = source.get('created_at') if source is not None else None
            now = getattr(self, '_operation_completion_time', self.time)
            if rid not in self.resources and type(created) is int and created > now:
                return None
            return source
        def fields_match():
            for rid, fields in cond.get('fields', {}).items():
                source = source_now(rid)
                if source is None or any(source.get('fields', {}).get(k) != v for k, v in fields.items()):
                    return False
            for rid, attrs in cond.get('attributes', {}).items():
                source = source_now(rid)
                if source is None or any(source.get(k) != v for k, v in attrs.items()):
                    return False
            return True
        return (all(rid in self.resources for rid in cond.get('revealed', []))
                and fields_match()
                and all(self.controller_facts.get(k) == v for k, v in cond.get('facts', {}).items())
                and all(k in self.controller_facts for k in cond.get('fact_present', []))
                and all(k not in self.controller_facts for k in cond.get('fact_absent', []))
                and (cond.get('min_time', -1) <= getattr(self, '_operation_completion_time', self.time) <= cond.get('max_time', 10**12)))

    def effect(self, effect):
        for resource in effect.get('add', []):
            if resource['id'] in self.resources:
                raise ValueError('Controller attempted to replace an existing stable resource')
        actual = deepcopy(effect)
        if actual.get('publish_queue'):
            cfg = actual['publish_queue']
            source = self._controller_resource(cfg['source'])
            if source is None:
                raise KeyError('Unknown queue source: ' + str(cfg['source']))
            queue = source['fields']
            if queue.get('enabled'):
                actual.setdefault('add', []).append({'id': cfg['output'], 'kind': 'post', 'channel': 'public',
                    'editable': True, 'status': 'published', 'text': queue['text'],
                    'assets': deepcopy(queue.get('assets', [])), 'created_at': self.time})
        stamp = actual.pop('stamp_add_at_execution', False)
        if type(stamp) is not bool:
            raise ValueError('stamp_add_at_execution must be boolean')
        if stamp:
            executed_at = getattr(self, '_operation_completion_time', self.time)
            for resource in actual.get('add', []):
                resource['created_at'] = executed_at
        for resource in actual.get('add', []):
            if resource['id'] in self.resources:
                raise ValueError('Controller attempted stable-ID replacement')
        # Preserve base effect ordering, but apply source mutations to current
        # hidden backing objects without making them revealed.
        base_effect = {k: v for k, v in actual.items() if k not in ('set', 'patch', 'copy')}
        super().effect(base_effect)
        for rid, fields in actual.get('set', {}).items():
            for target in self._controller_targets(rid):
                target.setdefault('fields', {}).update(deepcopy(fields))
        for rid, fields in actual.get('patch', {}).items():
            for target in self._controller_targets(rid):
                target.update(deepcopy(fields))
        for config in actual.get('copy', []):
            source = self._controller_resource(config['from'])
            if source is None:
                raise KeyError('Unknown copy source: ' + str(config['from']))
            copied = deepcopy(source)
            for target in self._controller_targets(config['to']):
                for key in config['attributes']:
                    if key in copied:
                        target[key] = deepcopy(copied[key])
                    else:
                        target.pop(key, None)
        for rid, extra in actual.get('append_text', {}).items():
            for target in self._controller_targets(rid):
                target['text'] += extra
        self.controller_facts.update(deepcopy(effect.get('facts_set', {})))

    def _capture(self, before_time=None):
        limit = self.time if before_time is None else before_time
        for cp in self.case.get('checkpoints', []):
            if cp['id'] in self.captured_checkpoints or cp['at'] > limit:
                continue
            self.captured_checkpoints.add(cp['id'])
            self.checkpoint_snapshots.append({'id': cp['id'], 'time': cp['at'], 'clock': self.clock(cp['at']),
                'resources': deepcopy(self.resources), 'actual_facts': deepcopy(self.controller_facts)})

    def _lookup_available(self, key):
        gate = self.lookup_gates.get(key, {})
        return self.time >= gate.get('at', 0) and self.matches(gate.get('requires', {}))

    def _project(self, value):
        if isinstance(value, list):
            return [self._project(v) for v in value]
        if not isinstance(value, dict):
            return deepcopy(value)
        result = {k: self._project(v) for k, v in value.items()}
        if result.get('kind') == 'directory' and 'id' in result:
            result['entries'] = [e for e in result.get('entries', [])
                if self._lookup_available(result['id'] + '/' + e['key'])
                or e.get('show_before_available', False)]
        return result

    def observe(self):
        out = super().observe()
        for resource in out['resources']:
            if resource.get('kind') == 'directory':
                resource['entries'] = [entry for entry in resource.get('entries', [])
                    if self._lookup_available(resource['id'] + '/' + entry['key'])
                    or entry.get('show_before_available', False)]
        out.update(protocol=PROTOCOL, clock=self.clock(), service_end=self.service_end,
                   closure_deadline=self.closure_deadline)
        if self.time == self.closure_deadline and not self.explicitly_closed:
            out['closure_status'] = 'Only an inclusive exact-cutoff FINISH remains available.'
        return self._project(out)

    def _new_id(self, prefix='sys-m'):
        while True:
            self.message_serial += 1
            rid = prefix + f'{self.message_serial:04d}'
            if rid not in self.resources and rid not in self.reserved:
                self.reserved.add(rid)
                return rid

    def _thread(self, rid):
        seen = set()
        while rid in self.resources and rid not in seen:
            seen.add(rid)
            resource = self.resources[rid]
            if resource.get('thread_id'):
                return resource['thread_id']
            if not resource.get('parent'):
                return rid
            rid = resource['parent']
        return rid

    def _terms(self, original, target):
        terms = original.get('terms', {})
        schema = target.get('message_fields', {})
        if not schema and target.get('id'):
            thread = self._thread(target['id'])
            schema = next((r['message_fields'] for r in self.resources.values()
                           if r.get('message_fields') and self._thread(r['id']) == thread), {})
        if not isinstance(terms, dict) or any(k not in schema or not _core.valid_field(v, schema[k]) for k, v in terms.items()):
            raise ValueError('Concrete message fields outside this visible conversation schema')
        return deepcopy(terms)

    def _binding_clauses(self, text):
        active = active_text(text)
        clauses = re.split(r'[;.!?]+', active)
        # An explicit qualification of THIS offer remains binding across a sentence boundary.
        for detail in clauses:
            refers = re.search(r'\b(?:this|that|the) (?:offer|proposal|reservation|confirmation)\b', detail)
            unresolved = re.search(r'\b(?:pending|unverified|unconfirmed|unknown|awaiting|not yet ready)\b', detail)
            historical = re.search(r'\b(?:old|earlier|previous)\b', detail)
            if refers and unresolved and not historical:
                return []
        valid = []
        cue = r'\b(?:offer|reserve|confirm|approve|grant|include|invite|extend)\b'
        for clause in clauses:
            request = confirmation_request(clause)
            if not re.search(cue, clause) and not request:
                continue
            if re.search(r"\b(?:cannot|can't|will not|won't|do not|don't|not)\b[^;.!?]{0,35}\b(?:offer|reserve|confirm|approve|grant|include|invite|extend)\b", clause):
                continue
            unresolved = re.search(r'\b(?:pending|unverified|unconfirmed|unknown|awaiting|not yet (?:ready|confirmed|verified))\b', clause)
            dependent = re.search(r'\b(?:only if|subject to|provided that|if the (?:camera|kit|loan|seat|lift|booking|permission|inspection))\b', clause)
            before_condition = clause[:dependent.start()] if dependent else clause
            prior_assertions = '; '.join(c for c in clauses[:clauses.index(clause)] if not re.search(r'\b(?:if|pending|unverified|not|unknown)\b', c))
            resolved = re.search(r'\b(?:already confirmed|already verified|has (?:already )?been confirmed|has (?:already )?been verified)\b', before_condition+'; '+prior_assertions)
            if unresolved or (dependent and not resolved):
                continue
            performative = re.search(r'\b(?:i|we)\s+(?:(?:can|will|hereby|now|am|are|would|like|to|happy|pleased|able)\s+){0,5}(?:offer|reserve|confirm|approve|grant|invite|extend)\b', clause)
            availability = re.search(r'\b(?:places?|seats?)\b.{0,20}\b(?:available|reserved|offered)\b', clause)
            explicit = re.match(r'\s*(?:here is (?:my|our) offer|offer:|confirmed:|approved:|reserved:)', clause)
            receipt_only = re.search(r'\bconfirm\b.{0,15}\b(?:receipt|received|read|saw|delivery)\b', clause)
            if receipt_only or not (performative or availability or explicit or request):
                continue
            valid.append(clause)
        return valid

    def _card_consistent(self, message, clauses):
        details = list(clauses)
        for part in re.split(r'[;.!?]+', active_text(message['text'])):
            if re.match(r'\s*(?:pickup|pick up|collection|return|please confirm|confirm|reply|respond|hold|priority|deadline|the price|price|total|this (?:offer|grant|role)|access|desk|chair|arrival)', part):
                details.append(part)
        text = '; '.join(details)
        terms = message.get('terms', {})
        def denied(start):
            return bool(re.search(r'\b(?:not|rather than|instead of)\s*$', text[max(0, start-20):start]))
        if 'price' in terms:
            money = []
            pattern = r'\b(?:price(?: is| of)?|total(?: is| of)?|pay|costs?|at|for|offer)\s*[$€£]?\s*(\d+(?:\.\d+)?)\b(?!:)'
            for match in re.finditer(pattern, text):
                following = text[match.end():match.end()+20]
                if re.match(r'\s*(?:hours?|minutes?|days?|weeks?|places?|seats?|people|persons?|items?)\b', following):
                    continue
                if not denied(match.start(1)):
                    money.append(float(match.group(1)))
            if any(value != float(terms['price']) for value in money):
                return False
        if 'places' in terms:
            nums = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6}
            for match in re.finditer(r'\b(one|two|three|four|five|six|\d+)\s+(?:[a-z][a-z0-9_-]*\s+)?(?:places?|seats?|people|persons?)\b', text):
                value = match.group(1)
                number = nums[value] if value in nums else int(value)
                if not denied(match.start()) and number != terms['places']:
                    return False
        for field, label in [('time', None), ('pickup', r'(?:pickup|pick up|collect(?:ion)?)'), ('return', r'return'), ('arrival', r'(?:arrival|arrive|arrives|reach|drop-off|drop off)')]:
            if field not in terms:
                continue
            expected = re.findall(r'\b\d{1,2}:\d{2}\b', str(terms[field]))
            if not expected:
                continue
            if field == 'time':
                expected_day = re.search(r'(?:day|d)\s*(\d+)', str(terms[field]), re.I)
                if expected_day:
                    for clause in clauses:
                        # Limit the day to the current offer/confirmation speech act.
                        cues = list(re.finditer(r'\b(?:i|we)\s+(?:(?:can|will|hereby|now|am|are|would|like|to|happy|pleased|able)\s+){0,5}(?:offer|reserve|confirm|invite)\b', clause))
                        scope = clause[cues[-1].end():] if cues else clause
                        for day in re.finditer(r'\bon\s*(?:day|d)\s*(\d+)\b', scope):
                            before = scope[max(0,day.start()-45):day.start()]
                            before = re.split(r'\b(?:but|now|currently|new)\b', before)[-1]
                            if re.search(r'\b(?:not|rather than|instead of)\s*$', before):
                                continue
                            if re.search(r'\b(?:earlier|previous|old|original)\b[^;.!?]{0,35}$', before):
                                continue
                            if day.group(1) != expected_day.group(1):
                                return False
            pattern = r'\b\d{1,2}:\d{2}\b' if label is None else r'\b'+label+r'(?:\b|(?=\d))[^;.!?]{0,20}?(\d{1,2}:\d{2})'
            for match in re.finditer(pattern, text):
                value = match.group(1) if label else match.group(0)
                pos = match.start(1) if label else match.start()
                if not denied(pos) and value not in expected:
                    return False
        for field, label in [('desk_time','desk'),('chair_time','chair')]:
            if field not in terms:
                continue
            expected_time = re.search(r'\d{1,2}:\d{2}', str(terms[field]))
            expected_day = re.search(r'(?:day|d)\s*(\d+)', str(terms[field]), re.I)
            for match in re.finditer(r'(?=\b'+label+r'(?:\b|(?=(?:day|d)\d))([^;.!?]{0,45}?)(\d{1,2}:\d{2}))', text):
                if re.search(r'\b(?:desk|chair)(?:\b|(?=(?:day|d)\d))', match.group(1)):
                    continue  # The time belongs to a nearer explicitly named item.
                if denied(match.start()):
                    continue
                if expected_time and match.group(2) != expected_time.group(0):
                    return False
                day = re.search(r'(?:day|d)\s*(\d+)', match.group(1), re.I)
                if day and expected_day and day.group(1) != expected_day.group(1):
                    return False
        if 'date' in terms:
            expected_day = re.search(r'(?:day|d)\s*(\d+)', str(terms['date']), re.I)
            if expected_day:
                for match in re.finditer(r'\bon\s*(?:day|d)\s*(\d+)\b', text):
                    if not denied(match.start()) and match.group(1) != expected_day.group(1):
                        return False
        if 'reply_by' in terms:
            expected_day = re.search(r'(?:day|d)\s*(\d+)', str(terms['reply_by']), re.I)
            expected_clock = re.search(r'\d{1,2}:\d{2}', str(terms['reply_by']))
            pattern = r'\b(?:reply|respond|confirm|hold|held|priority|deadline|window)\b[^;.!?]{0,35}?\b(?:by|until|to)\s*(?:day|d)\s*(\d+)(?:\s*(\d{1,2}:\d{2}))?'
            for match in re.finditer(pattern, text):
                if expected_day and match.group(1) != expected_day.group(1):
                    return False
                if expected_clock and match.group(2) and match.group(2) != expected_clock.group(0):
                    return False
        if 'role' in terms:
            aliases = {'viewer':'viewer','view-only':'viewer','read-only':'viewer','editor':'editor','editing':'editor'}
            for match in re.finditer(r'\b(viewer|view-only|read-only|editor|editing)\b', text):
                if not denied(match.start()) and aliases[match.group(1)] != terms['role']:
                    return False
        if re.fullmatch(r'c\d+', str(terms.get('course', '')).lower()):
            for match in re.finditer(r'\bc\d+\b', text):
                if not denied(match.start()) and match.group(0) != str(terms['course']).lower():
                    return False
        for key, label in [('document', r'document'), ('course', r'(?:course|class)'), ('camera', r'camera')]:
            if key in terms:
                for match in re.finditer(r'\b' + label + r'\s+([a-z][a-z0-9_-]*)\b', text):
                    if not denied(match.start(1)) and match.group(1).lower() != str(terms[key]).lower():
                        return False
        return True

    def _rule_matches(self, rule, message):
        if rule['id'] in self.response_fired and not rule.get('repeat', False):
            return False
        if rule.get('recipient') != message.get('recipient'):
            return False
        if rule.get('channel', message['channel']) != message['channel']:
            return False
        if rule.get('thread') and rule['thread'] != self._thread(message['id']):
            return False
        if not self.matches(rule.get('requires', {})) or not text_matches(message['text'], rule.get('text', {})):
            return False
        # Quoted instructional prose is still an actually delivered material body.
        # This optional guard never replaces the separate speech-act/commitment checks.
        if rule.get('delivered_text'):
            raw = message['text']
            spec = rule['delivered_text']
            if any(not re.search(pattern, raw, re.I) for pattern in spec.get('all', [])):
                return False
            if spec.get('any') and not any(re.search(pattern, raw, re.I) for pattern in spec['any']):
                return False
            if any(re.search(pattern, raw, re.I) for pattern in spec.get('none', [])):
                return False
        if rule.get('delivery_semantics') and not delivery_matches(message['text'], rule['delivery_semantics']):
            return False
        if any(message.get('terms', {}).get(k) != v for k, v in rule.get('terms', {}).items()):
            return False
        if any(key not in message.get('terms', {}) for key in rule.get('required_terms', [])):
            return False
        if rule.get('missing_any_terms') and all(key in message.get('terms', {}) for key in rule['missing_any_terms']):
            return False
        attachment = message.get('attachment', {})
        if any(attachment.get(key) != value for key, value in rule.get('attachment', {}).items()):
            return False
        if rule.get('attachment_text') and not text_matches(attachment.get('text', ''), rule['attachment_text']):
            return False
        if rule.get('attachment_max_words') and len(attachment.get('text', '').split()) > rule['attachment_max_words']:
            return False
        if rule.get('commitment', False):
            clauses = self._binding_clauses(message['text'])
            if not clauses or not self._card_consistent(message, clauses):
                return False
        return True

    def _responses(self, message):
        matched_group = set()
        for rule in self.case.get('response_rules', []):
            group = rule.get('group', rule.get('thread', rule['id']))
            if group in matched_group or not self._rule_matches(rule, message):
                continue
            matched_group.add(group)
            arrival = max(self.time + rule.get('delay', 1), rule.get('not_before', 0))
            if rule.get('delivery_windows'):
                eligible = [max(arrival, first) for first, last in rule['delivery_windows'] if max(arrival, first) <= last]
                if not eligible:
                    continue
                arrival = min(eligible)
            if arrival > rule.get('not_after', self.closure_deadline):
                continue
            self.response_fired.add(rule['id'])
            rid = self._new_id()
            response = {'id': rid, 'kind': 'dm' if message['channel'] == 'private' else 'comment',
                'channel': message['channel'], 'author': message['recipient'], 'recipient': self.case.get('creator_id', 'creator'), 'counterparty': message['recipient'],
                'parent': message['id'], 'thread_id': self._thread(message['id']),
                'text': rule['reply'], 'editable': False, 'created_at': arrival,
                'in_reply_to_terms': deepcopy(message.get('terms', {}))}
            effect = deepcopy(rule.get('effect', {}))
            effect.setdefault('add', []).append(response)
            if rule.get('capture_as'):
                effect.setdefault('facts_set', {})[rule['capture_as']] = {
                    'message_id': message['id'], 'recipient': message['recipient'], 'thread': self._thread(message['id']),
                    'text': message['text'], 'terms': deepcopy(message.get('terms', {})),
                    'attachment': deepcopy(message.get('attachment')), 'response_id': rid, 'at': arrival}
            event = dict(effect, id=self._new_id('sys-e'), at=arrival)
            self.pending.append(event)

        target = self.resources.get(message['parent'], {})
        required = target.get('required_for_confirmation')
        if not required:
            thread = self._thread(message['id'])
            required = next((r.get('required_for_confirmation') for r in self.resources.values()
                             if r.get('required_for_confirmation') and self._thread(r['id']) == thread), [])
        active = active_text(message['text'])
        intent = re.search(r"\b(?:i|we)\s+(?:(?:can|will|hereby|now|am|are|would|like|to|happy|pleased)\s+){0,5}(?:offer|reserve|confirm|approve|grant|invite|extend)\b", active)
        receipt = re.search(r'\bconfirm\b.{0,15}\b(?:receipt|received|read|delivery)\b', active)
        request_intent = any(confirmation_request(part) for part in re.split(r'[;.!?]+', active))
        if not matched_group and required and (intent or request_intent) and not receipt:
            missing = [key for key in required if key not in message.get('terms', {})]
            text = ('Please include these concrete details in this conversation’s visible detail card: '+', '.join(missing)+'. I have not confirmed an arrangement.'
                    if missing else 'Your message is not a final unambiguous arrangement. Please clarify the current terms and any unresolved condition before treating it as confirmed.')
            rid = self._new_id()
            self.pending.append({'id': self._new_id('sys-e'), 'at': self.time+1,
                'add': [{'id': rid, 'kind': 'dm' if message['channel']=='private' else 'comment',
                         'channel': message['channel'], 'author': message['recipient'],
                         'recipient': self.case.get('creator_id','creator'), 'counterparty': message['recipient'],
                         'parent': message['id'], 'thread_id': self._thread(message['id']), 'editable': False,
                         'text': text, 'created_at': self.time+1}]})

    def _counterparty(self, resource):
        creator = self.case.get('creator_id', 'creator')
        if resource.get('counterparty'):
            return resource['counterparty']
        if resource.get('author') and resource['author'] != creator:
            return resource['author']
        recipient = resource.get('recipient')
        if recipient and recipient != creator:
            return recipient
        raise ValueError('Conversation has no identifiable counterparty')

    def _eligible_event_time(self, event, limit):
        condition = event.get('when', {})
        created_bounds = []
        for rid in set(condition.get('fields', {})) | set(condition.get('attributes', {})):
            source = self._controller_resource(rid)
            created = source.get('created_at') if source is not None else None
            if rid not in self.resources and type(created) is int:
                created_bounds.append(created)
        first = max([self.time, event.get('at', 10**12), condition.get('min_time', -1)] + created_bounds)
        if first <= self.time or first > limit:
            return None
        old_time = self.time
        try:
            self.time = first
            return first if self.matches(event.get('when', {})) else None
        finally:
            self.time = old_time

    def reveal(self):
        changed = True
        while changed:
            changed = False
            for event in sorted(self.case.get('events', []) + self.pending, key=lambda e: e.get('at', 10**12)):
                if event['id'] in self.fired or event.get('at', 10**12) > self.time or not self.matches(event.get('when', {})):
                    continue
                payload = event
                for variant in event.get('variants', []):
                    if self.matches(variant.get('when', {})):
                        payload = variant
                        break
                if payload.get('calculator'):
                    computed = _core.local_calculate(payload['calculator'], self.resources, self.time)
                    payload = deepcopy(payload)
                    payload.update(computed.get('effect', {}))
                self.fired.add(event['id'])
                self.effect(payload)
                self.events.append({'event_id': event['id'], 'time': self.time, 'scheduled_at': event['at'],
                                    'added': [r['id'] for r in payload.get('add', [])]})
                changed = True

    def apply(self, action):
        before = deepcopy(self.__dict__)
        try:
            return self._apply(action)
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(before)
            raise

    def _apply(self, action):
        original = deepcopy(action)
        a = deepcopy(action)
        op = a.get('action')
        if self.explicitly_closed or self.time > self.closure_deadline:
            raise ValueError('Session closed')
        if op == 'WAIT' and (type(a.get('until')) is not int or not self.time < a['until'] <= self.closure_deadline):
            raise ValueError('Invalid wait')
        if op == 'FINISH' and (not isinstance(a.get('text'), str) or not a['text'].strip()):
            raise ValueError('Handoff text required')
        if op == 'LOOKUP':
            key = str(a.get('target')) + '/' + str(a.get('entry'))
            if not self._lookup_available(key):
                raise ValueError('No currently available entry for this request')
        if op == 'ASK':
            contact = self.resources.get(a.get('target'), {})
            if a.get('topic') not in contact.get('topics', []) or contact.get('thread') not in self.resources:
                raise ValueError('Contact topic/conversation unavailable')
            a = dict(a, action='REPLY', target=contact['thread'])
        terms = None
        if a.get('action') in ('REPLY', 'SEND_LINK'):
            target = self.resources.get(a.get('target'), {})
            terms = self._terms(a, target)
            if 'id' not in a:
                base_id = 'msg-' + f'{self.calls + 1:04d}'
                proposed = base_id
                suffix = 0
                while proposed in self.resources or proposed in self.reserved:
                    suffix += 1
                    proposed = base_id + '-' + str(suffix)
                a['id'] = proposed
            # All proposed keys are factual transported card fields, never controller routes.
            a.pop('terms', None)
        if op == 'WAIT':
            wake = [self._eligible_event_time(e, a['until']) for e in self.case.get('events', []) + self.pending
                    if e['id'] not in self.fired]
            predicted = min([a['until']] + [t for t in wake if t is not None])
            self._capture(predicted - 1)
            a['until'] = predicted
        exact_finish = op == 'FINISH' and self.time == self.closure_deadline
        old_deadline = self.case['deadline']
        if exact_finish:
            self.case['deadline'] += 1
            self.done = False
        target = self.resources.get(a.get('target')) if a.get('action') in ('REPLY', 'SEND_LINK') else None
        original_recipient = target.get('recipient') if target is not None else None
        had_recipient = target is not None and 'recipient' in target
        if target is not None:
            target['recipient'] = self._counterparty(target)
        # Operations' requires/variant windows concern their completion, as the
        # visible protocol promises. Other actions/events keep ordinary clock time.
        had_operation_time = hasattr(self, '_operation_completion_time')
        prior_operation_time = getattr(self, '_operation_completion_time', None)
        if op == 'OPERATE':
            self._operation_completion_time = self.time + 1
        try:
            result = super().apply(a)
        finally:
            if had_operation_time:
                self._operation_completion_time = prior_operation_time
            elif hasattr(self, '_operation_completion_time'):
                del self._operation_completion_time
            self.case['deadline'] = old_deadline
            if target is not None:
                if had_recipient:
                    target['recipient'] = original_recipient
                else:
                    target.pop('recipient', None)
        if op == 'FINISH':
            self.explicitly_closed = True
        elif self.time == self.closure_deadline:
            self.done = False  # A final inclusive FINISH is still legal.
        if terms is not None:
            message = self.resources[result['delivered']]
            message['terms'] = terms
            if terms:
                message['transported_details'] = deepcopy(terms)
            if a.get('action') == 'SEND_LINK':
                linked = self.resources[message['linked_resource']]
                if linked.get('kind') == 'delivered_file':
                    linked['recipient'] = message['recipient']
                    linked['thread_id'] = self._thread(message['id'])
                    linked['audience'] = [message['recipient']] if message['channel'] == 'private' else 'public'
                message['attachment'] = {k: deepcopy(linked[k]) for k in
                    ('source_resource', 'text', 'assets', 'version', 'credit', 'purpose') if k in linked}
            self.message_log.append(deepcopy(message))
            self._responses(message)
            self.reveal()
            result['delivered_content'] = deepcopy(message)
        self._capture()
        result.update(clock=self.clock(), pending_deliveries=self.pending_view())
        result = self._project(result)
        self.history[-1]['action'] = original
        self.history[-1]['result'] = deepcopy(result)
        self.history[-1]['snapshot'] = deepcopy(self.resources)
        return result

    def record(self):
        result = super().record()
        result.update(protocol=PROTOCOL, clock=self.clock(), service_end=self.service_end,
            closure_deadline=self.closure_deadline, checkpoint_snapshots=deepcopy(self.checkpoint_snapshots),
            actual_response_facts=deepcopy(self.controller_facts), message_log=deepcopy(self.message_log))
        return result


def run(case, actions):
    world = World(case)
    for action in actions:
        world.apply(action)
    return world.record()


def replay(case, record):
    expected = record.get('simulation', record)
    actual = run(case, [step['action'] for step in expected['history']])
    if actual != expected:
        raise ValueError('Replay mismatch')
    return actual


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--world', required=True);p.add_argument('--actions');p.add_argument('--replay');p.add_argument('--output', required=True)
    args = p.parse_args();case = json.loads(Path(args.world).read_text())
    result = replay(case, json.loads(Path(args.replay).read_text())) if args.replay else run(case, json.loads(Path(args.actions).read_text()))
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'steps': len(result['history']), 'done': result['done']}))
