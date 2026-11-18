"""Deterministic, reviewable bilingual prose edits before candidate freezing."""
from copy import deepcopy
import json
from pathlib import Path
import re

DATA_PATH = Path(__file__).with_name('language_patch_data.json')
NARRATIVE_KEYS = {'text', 'task', 'authorization', 'pass_condition', 'alternatives',
                  'failure', 'failure_boundary', 'notes', 'title', 'description',
                  'label', 'context', 'deadline', 'reason', 'clarification',
                  'changed_fact', 'expected_behavior_change'}
PROTECTED_CONTAINERS = {'translations', 'fields', 'params', 'details', 'param_values',
                        'request_fields', 'param_schema', 'request_schema', 'field_schema',
                        'requires', 'when', 'set'}


def spacing(text):
    """Fix readable prose boundaries without rewriting identifiers or numbers."""
    text = re.sub(r"\b(at|by|for|of|is|to|in|from|within|after|before|under|over|than|the|only|your|their|our|its|my)(?=\d)", r"\1 ", text)
    text = re.sub(r"(?<=\d)(minutes|minute|hours|hour|people|guests|portions|total)\b", r" \1", text)
    text = re.sub(r"(?<=\d)(kg|yuan|seconds|second)\b", r" \1", text)
    text = re.sub(r"('s)(?=\d)", r"\1 ", text)
    text = re.sub(r"\b(row|box|lot|voucher|Deposit|deposit|owner|contributor|Dataset|dataset|sensor|settings|passage|pages|serve|serves|on|paid|refunded|account|captured|refund|Refund|invoice|Invoice|credit|wallet|team|Team|captain|Captain|station|Station|editor|collector|recipient|release)(?=[A-Z0-9@])", r"\1 ", text)
    text = re.sub(r"(?<=[A-Za-z0-9]),(?=[A-Za-z@])", ", ", text)
    text = re.sub(r"\b(is|at|on|to|by|with|for|from|using|compatible)(?=(?:v\d|@))", r"\1 ", text)
    text = re.sub(r"\b(release|version|reissue)(?=v\d)", r"\1 ", text)
    text = re.sub(r"\b(gross|tare|net|pages|page|file|handle|player|key|stock|batch|input|entry|paid|keep|tomorrow|otherwise|then)(?=[A-Z0-9@])", r"\1 ", text)
    text = re.sub(r"\b(through|from|to|for|by|under|within|only)(?=[A-Z@])", r"\1 ", text)
    text = re.sub(r"(?<=[A-Za-z]):(?=[A-Za-z@])", ": ", text)
    return text


def normalize_case_prose(case):
    """Normalize newly generated variant prose without changing business values."""
    result = deepcopy(case)
    translations = result.setdefault('translations', {})
    changes = []
    def visit(value):
        if isinstance(value, dict):
            for key, child in list(value.items()):
                if key in PROTECTED_CONTAINERS:
                    continue
                if key in NARRATIVE_KEYS and isinstance(child, str):
                    revised = spacing(child)
                    if revised != child:
                        value[key] = revised
                        if child in translations:
                            translations[revised] = translations[child]
                        changes.append({'original': child, 'replacement': revised})
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(result)
    result['post_variant_spacing'] = {'scope': 'Narrative typography only; IDs, field values, parameters, schemas and conditions unchanged.', 'edits': changes}
    return result


def apply_language_patches(case):
    """Edit matching delivered prose and keep exact English-to-Chinese coverage."""
    result = deepcopy(case)
    translations = result.setdefault('translations', {})
    patches = [p for p in json.loads(DATA_PATH.read_text())['rows'] if p['short_id'] == result['short_id']]
    index = {(p['action'], p['target'], p['original_english']): p for p in patches}
    normalized_index = {(p['action'], p['target'], spacing(p['original_english'])): p for p in patches}
    applied = deepcopy(result.get('language_patch_metadata', {}).get('applied_action_edits', []))

    task_patch = index.get(('TASK', 'task', result.get('task'))) or normalized_index.get(('TASK', 'task', spacing(result.get('task', ''))))
    if task_patch:
        result['task'] = task_patch['english']
        translations[task_patch['english']] = task_patch['chinese']
        applied.append({'target': 'task', 'original': task_patch['original_english'], 'replacement': task_patch['english']})

    def walk(value):
        if isinstance(value, dict):
            if 'action' in value and 'text' in value:
                patch = index.get((value['action'], value.get('target'), value['text'])) or normalized_index.get((value['action'], value.get('target'), spacing(value['text'])))
                if patch:
                    value['text'] = patch['english']
                    translations[patch['english']] = patch['chinese']
                    applied.append({'target': patch['target'], 'original': patch['original_english'], 'replacement': patch['english']})
            if 'id' in value and 'text' in value and 'action' not in value:
                patch = index.get(('RESOURCE', value['id'], value['text'])) or normalized_index.get(('RESOURCE', value['id'], spacing(value['text'])))
                if patch:
                    value['text'] = patch['english']
                    translations[patch['english']] = patch['chinese']
                    applied.append({'target': patch['target'], 'original': patch['original_english'], 'replacement': patch['english']})
            for key, child in list(value.items()):
                if key in PROTECTED_CONTAINERS:
                    continue
                if key in NARRATIVE_KEYS and isinstance(child, str):
                    revised = spacing(child)
                    if revised != child:
                        if child in translations:
                            translations[revised] = translations[child]
                        value[key] = revised
                else:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(result)
    if result['short_id'] == 't5-01':
        for english, chinese in list(translations.items()):
            if re.search(r'\balto\b', english, re.I) and '低声部' in chinese:
                translations[english] = chinese.replace('低声部', '女低音声部（alto）')
    result['language_patch_metadata'] = {'version': 'prose-patches-v1', 'applied_action_edits': applied,
                                          'scope': 'Exact task/target/text edits and conservative English spacing. Business fields, IDs, conditions and intentional failure claims remain unchanged. Selected outgoing edits also narrow disclosure to the recipient’s authorised scope; those are substantive privacy repairs recorded in the revision history.'}
    return result
