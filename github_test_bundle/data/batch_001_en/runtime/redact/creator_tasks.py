"""Stage-based example simulator, isolated from historical benchmark protocols."""
from copy import deepcopy
PROTOCOL = 'creator-task-examples-v1'
TOOLS = {'READ': 'ids: 1–3 currently available resource IDs', 'ASK': 'topic: creator topic ID; question: text; answer arrives next stage', 'COMMIT': 'operations: list; handoff: private text. Apply writes atomically, then advance one stage.'}
OPERATIONS = {'edit': 'target, expected_revision, text; optional assets on own draft/post', 'publish': 'target own draft, expected_revision', 'reply': 'target observed public comment, text', 'send_dm': 'target observed incoming DM, text; delivered only to that sender', 'remove_asset': 'target own draft/post, expected_revision, asset'}

class CreatorTask:

    def __init__(self, case):
        self.case = deepcopy(case)
        self.resources = {r['id']: deepcopy(r) for r in case['resources']}
        self.stage = self.calls = self.reads = self.asks = self.writes = 0
        self.seen, self.asked = (set(), set())
        self.history, self.snapshots, self.outbox = ([], [], [])
        self.handoff = ''
        self.ended_by = None

    @property
    def done(self):
        return self.ended_by is not None

    def visible(self):
        return {k: v for k, v in self.resources.items() if v['stage'] <= self.stage}

    def public(self):
        return deepcopy({k: v for k, v in self.visible().items() if v.get('editable') and v.get('status') == 'published'})

    def observe(self):
        visible = self.visible()
        own = {k: deepcopy(v) for k, v in visible.items() if v.get('editable')}
        self.seen.update(own)
        budget = self.case['budget']
        return dict(protocol=PROTOCOL, task=self.case['task'], authorization=self.case['authorization'], stage=self.stage, done=self.done, ended_by=self.ended_by, update=self.case['stages'][self.stage] if not self.done else 'This round has ended.', own_content=own, private_outbox=deepcopy(self.outbox), resource_index=[dict(id=k, title=v['title'], kind=v['kind']) for k, v in visible.items() if not v.get('editable')], ask_topics=[dict(id=k, title=v['title']) for k, v in self.case['questions'].items()], remaining={k: budget[k] - getattr(self, k) for k in ('calls', 'reads', 'asks', 'writes')}, tools=TOOLS, operations=OPERATIONS, mechanics='Three rounds of discrete windows; next-round external events and creator replies appear only after COMMIT, not representing continuous time. At most 6 write operations per round. The final round COMMIT ends the task, after which no writes are allowed.', history=deepcopy(self.history))

    def apply(self, action):
        if self.done:
            raise ValueError('Episode ended')
        before = self.stage
        self.calls += 1
        try:
            if not isinstance(action, dict):
                raise ValueError('Action must be an object')
            result = self._apply(action)
        except (ValueError, KeyError, TypeError) as error:
            result = dict(error=str(error))
        self.history.append(dict(stage=before, action=deepcopy(action), result=deepcopy(result)))
        if self.calls >= self.case['budget']['calls'] and (not self.done):
            self.ended_by = 'budget_exhausted'
        return deepcopy(result)

    @staticmethod
    def text(value):
        if not isinstance(value, str) or not value.strip() or len(value) > 4000:
            raise ValueError('Expected nonempty text <=4000 chars')
        return value

    def _apply(self, action):
        kind = action.get('action')
        visible = self.visible()
        if kind == 'READ':
            ids = action.get('ids')
            if self.reads >= self.case['budget']['reads']:
                raise ValueError('Read budget exhausted')
            if not isinstance(ids, list) or not 1 <= len(ids) <= 3 or (not all((isinstance(i, str) and i in visible for i in ids))):
                raise ValueError('READ requires 1–3 available IDs')
            self.reads += 1
            self.seen.update(ids)
            return dict(resources=deepcopy([visible[i] for i in ids]))
        if kind == 'ASK':
            topic = action.get('topic')
            self.text(action.get('question'))
            if topic not in self.case['questions'] or topic in self.asked or self.asks >= self.case['budget']['asks']:
                raise ValueError('Unavailable/repeated topic or ask budget exhausted')
            if self.stage >= len(self.case['stages']) - 1:
                raise ValueError('No response window remains; hand off unresolved questions')
            self.asks += 1
            self.asked.add(topic)
            rid = 'answer_' + topic
            self.resources[rid] = dict(id=rid, kind='dm', title='Creator reply: ' + self.case['questions'][topic]['title'], text=self.case['questions'][topic]['answer'], stage=self.stage + 1, revision=1, assets=[], sender='creator')
            return dict(request_id=rid, delivery_stage=self.stage + 1)
        if kind != 'COMMIT':
            raise ValueError('Unknown action')
        ops = action.get('operations')
        note = action.get('handoff', '')
        budget = self.case['budget']
        if not isinstance(note, str) or len(note) > 4000:
            raise ValueError('Invalid private handoff')
        if not isinstance(ops, list) or len(ops) > budget['writes_per_commit'] or self.writes + len(ops) > budget['writes']:
            raise ValueError('Write budget exceeded')
        staged, outbox = (deepcopy(self.resources), deepcopy(self.outbox))
        changed, quotes = ([], [])
        for item in ops:
            if not isinstance(item, dict):
                raise ValueError('Operation must be an object')
            target, operation = (item.get('target'), item.get('kind'))
            if not isinstance(target, str) or target not in visible:
                raise ValueError('Target unavailable')
            entry = staged[target]
            if operation in ('reply', 'send_dm'):
                expected = 'comment' if operation == 'reply' else 'dm'
                if target not in self.seen or entry['kind'] != expected:
                    raise ValueError('Read the target in the correct channel first')
                text = self.text(item.get('text'))
                if operation == 'send_dm':
                    outbox.append(dict(target=target, recipient=entry.get('sender', 'creator'), text=text, stage=self.stage))
                else:
                    rid = 'reply_' + str(1 + sum((k.startswith('reply_') for k in staged)))
                    staged[rid] = dict(id=rid, title='Assistant public reply', kind='agent_reply', text=text, parent=target, stage=self.stage, revision=1, assets=[], editable=True, status='published')
                    changed.append(rid)
                    quotes.append(rid)
                continue
            if not entry.get('editable') or type(item.get('expected_revision')) is not int or item['expected_revision'] != entry['revision']:
                raise ValueError('Only own content with current integer revision is editable')
            if operation == 'edit':
                entry['text'] = self.text(item.get('text'))
                if 'assets' in item:
                    assets = item['assets']
                    if entry['kind'] not in ('post', 'draft') or not isinstance(assets, list) or (not all((isinstance(x, str) and x in self.case.get('asset_catalog', []) for x in assets))):
                        raise ValueError('Unknown asset or unsupported target')
                    entry['assets'] = list(dict.fromkeys(assets))
            elif operation == 'publish':
                if entry.get('status') != 'draft':
                    raise ValueError('Only an unpublished draft can be published')
                entry['status'] = 'published'
                entry['kind'] = 'post'
            elif operation == 'remove_asset':
                if item.get('asset') not in entry['assets']:
                    raise ValueError('Asset not attached')
                entry['assets'].remove(item['asset'])
            else:
                raise ValueError('Unknown operation')
            entry['revision'] += 1
            changed.append(target)
        self.resources, self.outbox = (staged, outbox)
        self.writes += len(ops)
        self.handoff = note
        self.seen.update(changed)
        self._after_commit(quotes, ops)
        return dict(changed=changed, private_messages_sent=len(outbox), stage=self.stage, done=self.done)

    def _after_commit(self, quotes, ops):
        self.snapshots.append(dict(stage=self.stage, public=self.public(), own=deepcopy({k: v for k, v in self.visible().items() if v.get('editable')}), private_outbox=deepcopy(self.outbox), handoff=self.handoff, operations=deepcopy(ops)))
        for rid in quotes:
            qid = 'quote_' + rid
            self.resources[qid] = dict(id=qid, title='Reader quoted previous reply', kind='comment', stage=self.stage + 1, text=f'I saved your earlier reply {rid}; if things change later, please confirm whether this guidance remains valid.', revision=1, assets=[], quoted_reply_id=rid)
        self.stage += 1
        if self.stage == len(self.case['stages']):
            self.ended_by = 'completed_windows'

    def record(self):
        return dict(protocol=PROTOCOL, case_id=self.case['id'], history=deepcopy(self.history), snapshots=deepcopy(self.snapshots), public=self.public(), private_outbox=deepcopy(self.outbox), handoff=self.handoff, ended_by=self.ended_by, costs={k: getattr(self, k) for k in ('calls', 'reads', 'asks', 'writes')})

def replay(case, record):
    env = CreatorTask(case)
    for step in record['history']:
        env.observe()
        env.apply(step['action'])
    if env.record() != record:
        raise ValueError('Replay mismatch')
    return env

def structural_checks(case, record):
    """Necessary mechanical evidence only, never a semantic success score."""
    results = []
    for check in case['acceptance']:
        snapshots = record['snapshots']
        if check['stage'] >= len(snapshots):
            passed = False
        else:
            snap = snapshots[check['stage']]
            obj = snap['own'].get(check['target'], {})
            kind = check['kind']
            if kind in ('status', 'assets'):
                passed = obj.get(kind) == check['value']
            elif kind == 'revised':
                passed = obj.get('revision', 0) > 1
            elif kind == 'dm_sent':
                passed = any((m['target'] == check['target'] for m in snap['private_outbox']))
            else:
                passed = any((r.get('parent') == check['target'] for r in snap['public'].values()))
        results.append(dict(**check, passed=passed))
    return dict(checks=results, quality_score=None, semantic_review='required', note='Structural validation does not mean the content is correct, the timing is appropriate, or authorization is obtained; GCR/TSR are temporarily not automatically calculated.')
