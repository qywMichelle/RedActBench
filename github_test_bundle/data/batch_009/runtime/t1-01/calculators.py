"""Actual selected booking transactions, distinct from consent and agency scoring."""
from copy import deepcopy
import json


def calculate(kind, resources, at, context):
    facts, state = deepcopy(context['facts']), deepcopy(context['state'])
    added, scheduled = [], []
    minute = (facts.get('start_minute', 540) + at) % 1440
    current_clock = f'{minute // 60:02d}:{minute % 60:02d}'

    def emit(label, text, **values):
        state['serial'] += 1
        row = {'id': 'booking-' + label + '-' + str(state['serial']), 'kind': 'receipt', 'channel': 'private',
               'editable': False, 'created_at': at, 'text': text}
        row.update(values)
        added.append(row)

    def queue(label, due, calculator):
        state['serial'] += 1
        scheduled.append({'id': 'booking-event-' + label + '-' + str(state['serial']), 'at': due,
                          'calculator': calculator, 'stamp_add_at_execution': True})

    def people(s):
        result = {b['person'] for b in s['bookings'].values() if b['status'] in ['held', 'conditional_held', 'confirmed']}
        result.update(a['person'] for a in s['aliases'].values() if a['type'] == 'fallback' and a['status'] == 'active')
        if s['Q_priority_until'] is not None and at <= s['Q_priority_until']:
            result.add('Q')
        return result

    def payment_of(s, booking):
        return s['payments'][s['bookings'][booking]['payment']]

    def command(s, row, before):
        op = row['op']
        if op == 'extend_hold':
            booking = s['bookings'][row['booking']]
            companion = s['payments'][row['companion_payment']]
            deadline = row['until']
            if (booking['status'] not in ['held', 'conditional_held'] or at > booking['until']
                    or payment_of(s, row['booking'])['amount'] < facts['bond']
                    or companion['amount'] < facts['bond'] or companion['status'] not in ['captured', 'processing', 'settled']
                    or type(deadline) is not int or deadline > facts['pair_window_end']):
                raise ValueError('Actual funded hold/captured companion/window does not support this extension')
            booking.update(status='conditional_held', until=deadline)
            for alias in s['aliases'].values():
                if alias['booking'] == row['booking'] and alias['status'] == 'active':
                    alias['until'] = deadline
            s['applications'][row['application']]['status'] = 'conditional_hold'
        elif op == 'form_party':
            app = s['applications'][row['application']]
            ids = row['bookings']
            if type(ids) is not list or len(ids) != 2 or len(set(ids)) != 2 or at > facts['pair_window_end']:
                raise ValueError('Supply two booking references within the actual pair window')
            members = []
            for bid in ids:
                booking = s['bookings'][bid]
                pay = payment_of(s, bid)
                active = booking['status'] in ['held', 'conditional_held', 'confirmed', 'ready']
                # A genuine same-batch replacement may continue an existing paid
                # entitlement without a real intervening vacancy or refund.
                if not active and before['bookings'][bid]['status'] in ['held', 'conditional_held', 'confirmed']:
                    active = pay['status'] in ['allocated', 'settled']
                if not active or pay['amount'] < facts['bond'] or pay['status'] not in ['allocated', 'settled']:
                    raise ValueError('No current paid entitlement for selected party booking ' + bid)
                members.append(booking['person'])
            if len(set(members)) != 2:
                raise ValueError('Two booking labels for the same person are not two attendees')
            for bid in ids:
                s['bookings'][bid].update(status='confirmed', until=None)
                payment_of(s, bid)['allocation'] = bid
            app.update(status='formed', bookings=ids, persons=members)
        elif op == 'retire_alias':
            s['aliases'][row['alias']]['status'] = 'retired'
        elif op == 'withdraw_booking':
            booking = s['bookings'][row['booking']]
            booking.update(status='withdrawn', until=None)
            for app in s['applications'].values():
                if row['booking'] in app.get('bookings', []):
                    app['status'] = 'member_withdrawn'
        elif op == 'request_refund':
            bid = row['booking']
            booking, pay = s['bookings'][bid], payment_of(s, bid)
            if booking['status'] not in ['withdrawn', 'expired'] or pay['status'] not in ['allocated', 'settled']:
                raise ValueError('A continuing funded booking has no unused-payment refund entitlement')
            pay.update(status='refund_requested', allocation=None)
            s['refund_requests'].append({'payment': booking['payment'], 'payer': pay['payer'], 'amount': pay['amount'],
                                         'requested_at': at, 'posting': facts['wallet_batch'] if at <= facts['wallet_cutoff'] else facts['next_wallet_batch']})
        elif op == 'confirm_single':
            bid = row['booking']
            booking, pay = s['bookings'][bid], payment_of(s, bid)
            if at > facts['pair_window_end'] or pay['status'] not in ['allocated', 'settled'] or booking['status'] not in ['held', 'conditional_held', 'ready']:
                raise ValueError('Selected single booking is not currently funded and live')
            booking.update(status='confirmed', until=None)
        elif op == 'return_wallet':
            if s['wallet_P'] <= 0:
                raise ValueError('No actual available wallet balance')
            s['external_return_pending_P'] += s['wallet_P']
            s['wallet_P'] = 0
        elif op == 'file_issue':
            s['issues'].append({'payment': row['payment'], 'text': row['text'], 'filed_at': at})
        else:
            raise ValueError('Unknown selected booking transaction')

    def condition_holds(row):
        current = state
        for part in row['field'].split('.'):
            current = current.get(part) if isinstance(current, dict) else None
        return current == row['equals']

    def run_ready():
        for number in range(len(state['jobs'])):
            job = state['jobs'][number]
            if job['status'] != 'pending' or job['not_before'] > at or not all(condition_holds(c) for c in job['when']):
                continue
            before = deepcopy(state)
            trial = deepcopy(state)
            try:
                for row in job['commands']:
                    command(trial, row, before)
                after_people = people(trial)
                if len(after_people) > facts['capacity']:
                    raise ValueError('Selected transaction exceeds the actual distinct-person capacity')
                removed = people(before) - after_people
                if removed and len(after_people) < facts['capacity'] and trial['Q_priority_until'] is None:
                    trial['Q_priority_until'] = at + facts['waiter_priority_minutes']
                trial['jobs'][number]['status'] = 'executed'
                state.clear()
                state.update(trial)
                if before['Q_priority_until'] is None and state['Q_priority_until'] is not None:
                    queue('waiter-priority-end', state['Q_priority_until'] + 1, 'booking_evaluate')
                emit('transaction', 'Actual selected atomic transaction committed. Aliases, underlying bookings, payment allocations and real vacancy remain distinct. This is not new participant consent or an agency-quality verdict.', selected_commands=job['commands'])
            except (ValueError, KeyError, TypeError) as exc:
                state['jobs'][number]['status'] = 'rejected'
                emit('transaction_rejected', 'Actual selected transaction rejected without partial effects: ' + str(exc), selected_commands=job['commands'])

    if kind == 'booking_submit':
        draft = resources.get('booking_draft')
        if draft is None:
            raise ValueError('No selected booking programme draft')
        jobs = json.loads(draft['fields']['programme_json'])
        if not isinstance(jobs, list) or not jobs or len(jobs) > 8:
            raise ValueError('Supply one to eight explicit transaction batches')
        for job in jobs:
            if (not isinstance(job, dict) or set(job) != {'not_before', 'when', 'commands'}
                    or type(job['not_before']) is not int or not isinstance(job['when'], list)
                    or not isinstance(job['commands'], list) or not job['commands']):
                raise ValueError('Booking programme shape does not match its visible schema')
            if any(not isinstance(c, dict) or set(c) != {'field', 'equals'} or not isinstance(c['field'], str) for c in job['when']):
                raise ValueError('A condition requires its current state field and literal expected value')
            state['jobs'].append(dict(deepcopy(job), status='pending'))
            if job['not_before'] > at:
                queue('requested-time', job['not_before'], 'booking_evaluate')
        run_ready()
        emit('programme_registered', 'Actual explicitly selected batches registered. Registration alone does not establish future settlement, formation, refund availability or attendance.')
    elif kind == 'booking_processing_ack':
        if state['payments']['E_P']['status'] == 'captured':
            state['payments']['E_P']['status'] = 'processing'
        status = state['payments']['E_P']['status']
        emit('partner_ack', f'Actual{current_clock} partner acknowledgment. Current E-P20 status is {status}. This acknowledgment creates no new settlement or attendance formation; the actual booking and application registers determine the current rights.')
        run_ready()
    elif kind == 'booking_partner_result':
        result = facts['partner_result']
        if result == 'settled':
            state['payments']['E_P']['status'] = 'settled'
            state['bookings']['O_P']['status'] = 'ready'
            emit('partner_settled', f'Actual{current_clock}: separate transactionE-P20 really settled for the sameP conditional orderO-P. This does not itself form the pair, retire another record or make E-U20 unused.')
        else:
            state['payments']['E_P']['status'] = 'failed_unreleased'
            state['bookings']['O_P']['status'] = 'failed_unformed'
            emit('partner_not_settled', f'Actual{current_clock}: E-P20 did not settle. Its captured amount has not been released; provider disposition remains pending. No deadline extension, available wallet or formed attendance is supplied.')
        run_ready()
    elif kind == 'booking_expiry':
        before = people(state)
        for booking in state['bookings'].values():
            if booking['status'] in ['held', 'conditional_held', 'ready'] and booking['until'] < at:
                booking['status'] = 'expired'
        for alias in state['aliases'].values():
            if alias['type'] == 'fallback' and alias['status'] == 'active' and alias['until'] < at:
                alias['status'] = 'expired'
        if before - people(state) and len(people(state)) < facts['capacity'] and state['Q_priority_until'] is None:
            state['Q_priority_until'] = at + facts['waiter_priority_minutes']
            queue('waiter-priority-end', state['Q_priority_until'] + 1, 'booking_evaluate')
        if before != people(state):
            emit('actual_hold_end', 'Actual passed hold boundary applied to the still-unformed current rights only; a continuing paid formed booking is retained. A real vacancy is not a new admission.')
        run_ready()
    elif kind == 'booking_wallet_batch':
        for row in state['refund_requests']:
            if row['posting'] == at and not row.get('posted'):
                state['wallet_P'] += row['amount']
                row['posted'] = True
                state['payments'][row['payment']]['status'] = 'wallet_posted'
                emit('actual_wallet_credit', 'Actual ordinary payer-P wallet credit posted from the specific unused payment. This is separate from any remaining paid booking or a requested external return.', amount=row['amount'], payment=row['payment'])
        run_ready()
    elif kind != 'booking_evaluate':
        raise ValueError('Unknown booking worker operation')
    else:
        run_ready()
    # Expired automatic offer priority is not attendance and need not fill a place.
    if state['Q_priority_until'] is not None and at > state['Q_priority_until']:
        state['Q_priority_until'] = None
    fields = {'bookings_json': json.dumps(state['bookings'], sort_keys=True),
              'aliases_json': json.dumps(state['aliases'], sort_keys=True),
              'payments_json': json.dumps(state['payments'], sort_keys=True),
              'applications_json': json.dumps(state['applications'], sort_keys=True),
              'distinct_active_people': json.dumps(sorted(people(state))), 'wallet_P': state['wallet_P'],
              'external_return_pending_P': state['external_return_pending_P'],
              'Q_priority_until': state['Q_priority_until']}
    effect = {'native_state_replace': state, 'set': {'registration_provider': fields}}
    if added:
        effect['add'] = added
    if scheduled:
        effect['native_schedule'] = scheduled
    return {'effect': effect, 'facts': {'actual_request_processed': kind, 'actual_time': at,
                                      'new_actual_receipts': [r['id'] for r in added]}}
