"""Execute selected fictional travel programmes; never choose the route for an actor."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re

_spec = importlib.util.spec_from_file_location('project_delivered_relations', Path(__file__).with_name('reply_relations.py'))
_relations = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_relations)


def calculate(kind, resources, at, context):
    facts, state = deepcopy(context['facts']), deepcopy(context['state'])
    effect, schedules, added = {}, [], []

    def current_collection_instruction():
        """Read actual delivered snapshots, never an edited draft/current reply."""
        latest = None
        messages = context.get('deliveries', []) + state.get('auto_deliveries', [])
        for message in sorted(messages, key=lambda r: (r.get('created_at', -1), r.get('id', ''))):
            if (message.get('recipient') != 'Faye' or message.get('channel') != 'private'
                    or not 0 <= message.get('created_at', -1) <= at):
                continue
            material = _relations.active_material(message.get('text', ''))
            if not re.search(r'\b(?:C|trolley)\b', material, re.I):
                continue
            for part in _relations.clauses(material):
                if _relations.historical(part):
                    continue
                cue = re.search(r'\b(?:collect|pick\s+up|get|take)\b', part)
                if not cue:
                    continue
                prefix = part[:cue.start()]
                if (re.search(r"\b(?:do not|don't|never|must not|cannot|can't|not yet)\s*$", prefix)
                        or re.search(r"\b(?:cannot|can't|will not|won't)\s+(?:confirm|instruct|authorize)\b", prefix)):
                    latest = None
                    continue
                if not re.search(r'\b(?:c|trolley)\b', part[cue.end():]):
                    continue
                if _relations.unresolved_condition(part):
                    old_timing_condition = (re.search(r'\bif\b', part) and re.search(r'\b(?:home|carrying)\b', part)
                        and re.search(r'\b(?:cannot|no longer|fails?|incompatible)\b', part))
                    fits = max(state['X_arrival'] + facts['routes']['X_to_H'], facts['F_ready']) + facts['routes']['H_to_gate'] + facts['combined_minutes'] <= state['F_cutoff']
                    if not old_timing_condition or fits:
                        latest = None
                        continue
                if not re.search(r'(?:home\s*h|\bh\b).{0,25}closet|closet.{0,40}(?:home\s*h|\bh\b)', part):
                    continue
                times = re.findall(r'(?<!\d)(\d{1,2}):(\d{2})(?!\d)', part[cue.end():])
                if not times:
                    continue
                days = re.findall(r'\bday\s*(\d+)\b', part)
                if days and any(int(day) != 2 for day in days):
                    latest = None
                    continue
                hour, minute = map(int, times[0])
                due = 1440 + hour * 60 + minute - facts['start_minute']
                if facts['C_window'][0] <= due <= facts['C_window'][1]:
                    latest = {'due': due, 'message_id': message['id']}
        return latest

    def clock(elapsed):
        day, minute = divmod(facts['start_minute'] + elapsed, 1440)
        return 'Day' + str(day + 1) + ' ' + str(minute // 60).zfill(2) + ':' + str(minute % 60).zfill(2)

    def receipt(prefix, text, **data):
        state['serial'] += 1
        obj = {'id': 'project-' + prefix + '-' + str(state['serial']), 'kind': 'receipt',
               'channel': 'private', 'editable': False, 'created_at': at, 'text': text}
        obj.update(data)
        added.append(obj)

    def queue(phase, due, generation=False, require_J_H=False):
        if due < at:
            raise ValueError('Selected future processing cannot begin in the past')
        state['serial'] += 1
        event = {'id': 'project-event-' + str(state['serial']), 'at': due,
                 'calculator': 'project_event/' + phase, 'stamp_add_at_execution': True}
        if generation:
            event['when'] = {'facts': {'project_generation': state['generation']}}
        if require_J_H:
            event.setdefault('when', {})['fact_present'] = ['project_J_at_H']
        schedules.append(event)

    def value(source, offset):
        return {'fixed': 0, 'X_arrival': state['X_arrival'], 'F_cutoff': state['F_cutoff'],
                'F_ready': facts['F_ready']}[source] + offset

    def matching_plan():
        for row in state['branches']:
            if row['operator'] == 'always':
                return deepcopy(row)
            left, right = value(row['left_source'], row['left_offset']), value(row['right_source'], row['right_offset'])
            if (left <= right if row['operator'] == '<=' else left > right):
                return deepcopy(row)
        return None

    def notify(person, text):
        state['serial'] += 1
        message = {'id': 'project-plan-message-' + str(state['serial']), 'kind': 'service_message',
                      'channel': 'private', 'editable': False, 'created_at': at,
                      'author': 'project_service', 'recipient': person, 'parent': 'dm_' + person,
                      'text': text, 'actual_delivery': True}
        added.append(message)
        state.setdefault('auto_deliveries', []).append(deepcopy(message))

    def choose_current():
        selected = matching_plan()
        if selected is None:
            state['selected'] = None
            return
        departure = value(selected['F_depart_source'], selected['F_depart_offset'])
        if selected == state.get('selected') and departure == state.get('selected_departure'):
            return
        if state['case_departed'] and any(selected[k] != state['selected'][k] for k in
            ['F_mode', 'F_depart_source', 'F_depart_offset']):
            raise ValueError('A selected amendment cannot rewrite an already started case journey')
        if state['J_left_terminal'] and selected['J_via'] != state['J_destination']:
            raise ValueError('No actual mid-route diversion is supplied for the already started leg')
        state['selected'] = selected
        state['selected_departure'] = departure
        state['generation'] += 1
        state['C_reserved'] = selected['C_for']
        effect.setdefault('facts_set', {})['project_generation'] = state['generation']
        effect.setdefault('set', {}).setdefault('C_actual', {})['reserved_to'] = selected['C_for']
        if selected['C_for'] == 'Faye' and state['C_holder'] == 'home_H_closet':
            queue('collect_F', selected['C_collect_at'], True)
        if not state['case_departed']:
            queue('F_depart', departure, True, selected['F_mode'] == 'two_person')
        if state['notify']:
            meeting = 'home H' if selected['A_meet'] == 'H' else 'the landside Ferry Gate F counter'
            carrying = 'trolley C' if selected['F_mode'] == 'C' else 'the accepted two-person carry with Jules'
            collection = (' Collect C at ' + clock(selected['C_collect_at']) + ' from the home H closet within06:30–06:45.'
                          if selected['F_mode'] == 'C' else '')
            final_handling = (' The case must actually be accepted under your original F ticket before you carry A with the empty folded C.'
                              if selected['F_mode'] == 'C' else
                              ' Keep the selected two-person case handling and the actual adapter transfer distinct from the carrier intake.')
            notify('Faye', 'Your current selected case plan leaves home H at ' + clock(departure) +
                   ' using ' + carrying + '. The project adapter meeting is at ' + meeting + '.' + collection +
                   final_handling + ' A selected plan is not a collection or completed cargo/adapter receipt.')
            route = ('walk from the X terminal to home H,12minutes' if selected['J_via'] == 'H' else
                     'walk directly from the X terminal to the landside Ferry Gate F counter,10minutes')
            optional = 'stays at home' if selected['tripod'] == 'leave_home' else 'is included in the selected load'
            notify('Jules', 'Your current selected project plan uses ' + selected['J_container'] +
                   ' for your required kit including the boxed adapter' +
                   '. The optional tripod ' + optional + '. After actual X terminal arrival, ' + route +
                   '. The adapter meeting is at ' + meeting +
                   '. Keep A until its actual accepted transfer. X origin is still unresolved; this route concerns the known destination side only.')

    def maybe_counter():
        selected = state.get('selected')
        if not selected or state['case_location'] != 'gate_counter':
            return
        if selected['counter_mode'] == 'separate':
            if not state['case_intake_started']:
                state['case_intake_started'] = True
                queue('case_intake_complete', at + facts['combined_minutes'])
            if (state['case_custodian'] == 'F_carrier' and state['A_holder'] == 'Jules'
                    and state['J_location'] == 'gate_counter' and selected['A_meet'] == 'gate_counter'
                    and not state['A_transfer_started']):
                state['A_transfer_started'] = True
                queue('A_gate_transfer_complete', at + facts['combined_minutes'])
            return
        if state['counter_started']:
            return
        if selected['A_meet'] == 'gate_counter' and (state['J_location'] != 'gate_counter' or state['A_holder'] != 'Jules'):
            return
        if selected['A_meet'] == 'H' and state['A_holder'] != 'Faye':
            return
        state['counter_started'] = True
        queue('counter_complete', at + facts['combined_minutes'])

    def validate(rows):
        required = {'left_source', 'left_offset', 'operator', 'right_source', 'right_offset',
                    'C_for', 'C_collect_at', 'J_container', 'tripod', 'J_via', 'F_mode',
                    'F_depart_source', 'F_depart_offset', 'A_meet', 'counter_mode'}
        if not isinstance(rows, list) or not 1 <= len(rows) <= 4:
            raise ValueError('Supply one to four selected programme branches')
        for row in rows:
            if not isinstance(row, dict) or set(row) != required:
                raise ValueError('Programme branch fields do not match the documented schema')
            for name in ['left_source', 'right_source', 'F_depart_source']:
                if row[name] not in ['fixed', 'X_arrival', 'F_cutoff', 'F_ready']:
                    raise ValueError('Unknown current-source arithmetic reference')
            if any(type(row[k]) is not int for k in ['left_offset', 'right_offset', 'F_depart_offset', 'C_collect_at']):
                raise ValueError('Programme offsets and collection time must be integers')
            enums = {'operator': ['always', '<=', '>'], 'C_for': ['Jules', 'Faye'],
                     'J_container': ['B', 'C'], 'tripod': ['keep', 'leave_home'],
                     'J_via': ['H', 'gate_counter'], 'F_mode': ['C', 'two_person'],
                     'A_meet': ['H', 'gate_counter'], 'counter_mode': ['combined', 'separate']}
            if any(row[key] not in options for key, options in enums.items()):
                raise ValueError('Unknown selected programme field value')

    result = {'processed': kind, 'actual_time': at}
    if kind == 'project_submit':
        if 'project_draft' not in resources:
            raise ValueError('No current selected programme draft')
        submitted = resources['project_draft']['fields']
        if type(submitted['notify']) is not bool:
            raise ValueError('notify must be an actual boolean')
        rows = json.loads(submitted['branches_json'])
        validate(rows)
        state['branches'] = rows
        state['notify'] = submitted['notify']
        # Current selection uses only the actually published state. No future
        # vehicle outcome is used to validate or preview the submitted request.
        choose_current()
        receipt('submitted', 'Actual selected programme registered. Future travel, cargo acceptance and adapter delivery remain unperformed.',
                selected_branch_count=len(rows))
        result['registered_branch_count'] = len(rows)
    elif kind == 'project_publish_F':
        state['F_cutoff'] = facts['F_publication']['cutoff']
        choose_current()
    elif kind == 'project_publish_X':
        state['X_arrival'] = facts['X_publication']['arrival']
        choose_current()
    elif kind == 'project_instruction_observed':
        instruction = current_collection_instruction()
        if (instruction and state['C_holder'] == 'home_H_closet' and state['C_reserved'] == 'Faye'
                and at <= facts['C_window'][1]):
            queue('collect_F', max(at, instruction['due']))
    elif kind == 'project_J_depart':
        plan = state.get('selected') or facts['old_operational_plan']
        container = plan['J_container']
        weight = facts['J_other_kit'] + facts['A_weight'] + (facts['tripod_weight'] if plan['tripod'] == 'keep' else 0)
        available = container == 'B' or state['C_holder'] in ['home_H_closet', 'Jules'] and state['C_reserved'] == 'Jules'
        if available and weight <= facts['capacities'][container]:
            if container == 'C':
                state['C_holder'] = 'Jules'
                state['C_load'] = weight
                effect.setdefault('set', {}).setdefault('C_actual', {})['holder'] = 'Jules'
            state.update(J_departed=True, J_location='on_X', J_container=container, J_tripod=plan['tripod'], J_load=weight)
            receipt('J_departure', 'Actual group witness: Jules left for the X workshop with the selected contained required kit, including A. This does not establish terminal arrival.',
                    container=container, actual_kit_weight=weight)
        else:
            receipt('J_packing_incomplete', 'No Jules workshop-departure receipt: selected container is not available or its actual packed weight exceeds its rating. Jules and A remain known atH.',
                    selected_container=container, selected_load=weight)
    elif kind == 'project_X_actual_arrival':
        if state['J_departed']:
            state['J_location'] = 'X_terminal'
            state['X_actually_arrived'] = True
            selected = state.get('selected') or facts['old_operational_plan']
            state['J_left_terminal'] = True
            state['J_destination'] = selected['J_via']
            duration = facts['routes']['X_to_H' if selected['J_via'] == 'H' else 'X_to_gate']
            queue('J_arrive_' + selected['J_via'], at + duration)
            receipt('X_terminal', 'Actual X destination witness: Jules arrived with A and the recorded kit. The origin pickup field is not established by this receipt.')
    elif kind.startswith('project_event/'):
        phase = kind.split('/', 1)[1]
        selected = state.get('selected') or facts['old_operational_plan']
        if phase == 'collect_F' and state['C_holder'] == 'Faye':
            pass
        elif phase == 'collect_F':
            earliest_home_help = max(state['X_arrival'] + facts['routes']['X_to_H'], facts['F_ready']) + facts['routes']['H_to_gate'] + facts['combined_minutes']
            scope_applies = (facts['Faye_C_scope'] == 'unconditional_assignment' or
                             facts['Faye_C_scope'] == 'if_home_help_infeasible' and earliest_home_help > state['F_cutoff'])
            instruction = current_collection_instruction()
            if (facts['C_window'][0] <= at <= facts['C_window'][1] and state['C_holder'] == 'home_H_closet'
                    and state['C_reserved'] == 'Faye' and scope_applies and instruction and instruction['due'] <= at):
                state['C_holder'] = 'Faye'
                effect.setdefault('set', {}).setdefault('C_actual', {})['holder'] = 'Faye'
                effect.setdefault('facts_set', {})['project_C_with_Faye'] = True
                receipt('C_Faye', 'Actual closet witness: C physically handed toFaye within the old accepted window after actual delivered practical directions. No terminal or gate arrival is established.', instruction_message=instruction['message_id'])
            else:
                receipt('C_not_collected', 'No new Faye closet handover occurred: actual received directions, accepted condition, window or custody did not support this attempt. Current C holder remains ' + state['C_holder'] + '.')
        elif phase in ['J_arrive_H', 'J_arrive_gate_counter']:
            destination = phase[len('J_arrive_'):]
            state['J_location'] = destination
            effect.setdefault('facts_set', {})['project_J_at_' + destination] = True
            receipt('J_location', 'Actual destination-side witness: Jules and his retained equipment reached ' + destination + '.', actual_location=destination)
            if destination == 'H' and selected['A_meet'] == 'H' and state['case_location'] == 'H':
                queue('H_transfer_complete', at + facts['combined_minutes'])
            maybe_counter()
        elif phase == 'H_transfer_complete':
            if state['J_location'] == 'H' and state['case_location'] == 'H' and state['A_holder'] == 'Jules':
                state['A_holder'] = 'Faye'
                receipt('A_at_H', 'Actual project witness atH: A physically transferred fromJules toFaye after X use. This is not case intake or proof that the chosen later carrying load is feasible.')
        elif phase == 'F_depart':
            if at < facts['F_ready'] or state['case_departed']:
                receipt('F_not_departed', 'No new case departure: the case is not ready or its journey already started.')
            else:
                mode = selected['F_mode']
                if mode == 'C':
                    feasible = state['C_holder'] == 'Faye' and facts['case_weight'] <= facts['capacities']['C'] and state['A_holder'] != 'Faye'
                else:
                    feasible = state['J_location'] == 'H'
                if feasible:
                    state.update(case_departed=True, case_location='H_to_gate', case_mode=mode)
                    if mode == 'C':
                        state['C_load'] = facts['case_weight']
                    if mode == 'two_person':
                        state['J_location'] = 'H_to_gate'
                    queue('F_gate_arrival', at + facts['routes']['H_to_gate'])
                    receipt('F_case_departure', 'Actual H witness: the case journey started using ' + mode + '. This is neither gate arrival nor carrier acceptance.')
                else:
                    receipt('F_carrying_incomplete', 'No supported case departure: actual helper/C/hands are not available for the selected carrying mode. The case remains withFaye atH.')
        elif phase == 'F_gate_arrival':
            state['case_location'] = 'gate_counter'
            if state['case_mode'] == 'two_person':
                state['J_location'] = 'gate_counter'
            receipt('case_counter_arrival', 'Actual gate-side witness: Faye case arrived at the landside counter. It has not yet been accepted asF cargo and no adapter transfer is inferred.')
            maybe_counter()
        elif phase == 'case_intake_complete':
            if state['case_location'] == 'gate_counter' and at <= state['F_cutoff']:
                state['case_custodian'] = 'F_carrier'
                if state['case_mode'] == 'C':
                    state['C_load'] = 0
                if state['A_holder'] == 'Faye':
                    state['counter_complete'] = True
                receipt('case_accepted', 'Actual separate original-ticket cargo receipt: F accepted the11kg case, still owned byFaye. This receipt alone does not transfer A or prove the complete project load is ready.',
                        actual_case_custodian='F_carrier', actual_case_owner='Faye')
                maybe_counter()
            else:
                receipt('case_not_accepted', 'The separate case intake did not complete within the actual cutoff. Its known custody remains unchanged.')
        elif phase == 'A_gate_transfer_complete':
            if (state['case_custodian'] == 'F_carrier' and state['J_location'] == 'gate_counter'
                    and state['A_holder'] == 'Jules' and at <= state['F_cutoff']):
                state['A_holder'] = 'Faye'
                state['J_load'] -= facts['A_weight']
                state['counter_complete'] = True
                receipt('A_counter_accepted', 'Actual separate gate-side project receipt: A physically transferred toFaye after the case had already been accepted. Earlier case acceptance remains a separate actual fact; no ferry departure is claimed.', actual_A_holder='Faye')
            else:
                receipt('A_not_transferred', 'The separate adapter handover did not complete within the actual cutoff/prerequisites. Earlier real case intake remains valid; A stays with its known actual custodian.')
        elif phase == 'counter_complete':
            ready = state['case_location'] == 'gate_counter' and (state['A_holder'] == 'Faye' or state['J_location'] == 'gate_counter' and state['A_holder'] == 'Jules')
            if ready and at <= state['F_cutoff']:
                old_A = state['A_holder']
                state.update(case_custodian='F_carrier', A_holder='Faye', counter_complete=True)
                if old_A == 'Jules':
                    state['J_load'] -= facts['A_weight']
                if state['case_mode'] == 'C':
                    state['C_load'] = 0
                receipt('counter_accepted', 'Actual original-ticket counter transaction completed: F accepted the11kg case as cargo; ownership remainsFaye. A is physically held byFaye after the recorded project transfer. '
                        + ('C is now empty/folded and remains withFaye for the permitted cabin carriage.' if state['case_mode'] == 'C' else 'C, if used for Jules kit, remains withJules; no C transfer toFaye occurred.')
                        + ' No ferry departure or exhibition attendance is claimed.',
                        actual_case_custodian='F_carrier', actual_case_owner='Faye', actual_A_holder='Faye',
                        new_A_transfer=old_A == 'Jules')
            else:
                receipt('counter_not_accepted', 'The selected counter transaction did not complete within actual F cutoff or its real goods/person prerequisites. Known case and adapter custodians remain unchanged.')
        else:
            raise ValueError('Unknown project processing phase')
    else:
        raise ValueError('Unknown native project operation')
    if state['C_holder'] == 'Jules' and state['J_container'] == 'C':
        state['C_load'] = state['J_load']
    effect.setdefault('set', {}).setdefault('C_actual', {}).update(
        reserved_to=state['C_reserved'], holder=state['C_holder'])
    effect['set']['project_actual'] = {name: state[name] for name in
        ['A_holder', 'case_custodian', 'case_location', 'C_holder', 'C_load',
         'J_location', 'J_container', 'J_load', 'counter_complete']}
    effect['native_state_replace'] = state
    if schedules:
        effect['native_schedule'] = schedules
    if added:
        effect['add'] = added
    return {'effect': effect, 'facts': result}
