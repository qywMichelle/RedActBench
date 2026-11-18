"""Native tariff and invoice accounting, without selecting a delegated policy."""
from copy import deepcopy
import json


def reprice(money, x, y):
    """Native tariff arithmetic for actual surviving registrations only."""
    count = int(x['U'] in ['confirmed_morning', 'reconfirm_pending', 'confirmed_afternoon'])
    count += sum(y[owner] == 'confirmed' for owner in ['U', 'Z'])
    quote = {1: 140, 2: 120, 3: 100}.get(count)
    outcomes = []
    for owner, prefix in [('U', 'Y'), ('Z', 'Z')]:
        if y[owner] != 'confirmed':
            continue
        previous = money[prefix + '_quote']
        if quote < previous:
            raise ValueError('A withdrawal cannot recreate a cheaper closed group registration')
        primary = max(0, min(quote, 120) - max(previous, 100))
        secondary = max(0, quote - max(previous, 120))
        if not primary and not secondary:
            continue
        money[prefix + '_quote'] = quote
        money[prefix + '_primary_due'] += primary
        money[prefix + '_secondary_due'] += secondary
        money[prefix + '_balance'] += primary + secondary
        money[prefix + '_primary_open'] = money[prefix + '_primary_due'] > 0
        money[prefix + '_secondary_open'] = money[prefix + '_secondary_due'] > 0
        money['group_repriced'] = 'yes'
        outcomes.append({'invoice': owner + '-Y', 'previous_quote': previous, 'actual_quote': quote,
                         'primary_added': primary, 'primary_due': 'Day2 17:00',
                         'secondary_added': secondary, 'secondary_due': 'Day2 18:00'})
    return outcomes


def calculate(kind, resources, at):
    money = deepcopy(resources['U_finance']['fields'])
    x = deepcopy(resources['X_actual']['fields'])
    y = deepcopy(resources['Y_actual']['fields'])
    outcomes = []
    if kind.startswith('tier_adjust_'):
        outcomes.extend(reprice(money, x, y))
    elif kind in ['tier_withdraw_X_wallet', 'tier_withdraw_X_cash', 'tier_cancel_U_bundle', 'tier_withdraw_Z_Y']:
        if kind == 'tier_withdraw_Z_Y':
            y['Z'] = 'cancelled'
            money.update(Z_primary_open=False, Z_secondary_open=False)
            outcomes.append({'order': 'Z-Y', 'actual_state': 'cancelled', 'old_payment_disposition': 'unreported'})
        else:
            if x['U'] != 'withdrawn':
                money['X_refund'] = 'wallet_requested' if kind == 'tier_withdraw_X_wallet' else 'cash_pending'
                outcomes.append({'order': 'U-X', 'actual_state': 'withdrawn', 'refund_amount': 80,
                                 'refund_state': money['X_refund'], 'available_credit_created': False})
            x['U'] = 'withdrawn'
            if kind == 'tier_cancel_U_bundle':
                y['U'] = 'cancelled'
                money.update(Y_primary_open=False, Y_secondary_open=False)
                outcomes.append({'order': 'U-Y', 'actual_state': 'cancelled', 'old_payment_disposition': 'unreported'})
        outcomes.extend(reprice(money, x, y))
    elif kind == 'refund_current_wallet':
        amount = money['wallet']
        if amount <= 0:
            raise ValueError('No current wallet balance to return')
        money.update(wallet=0, remainder='cash_pending', refund_pending=money['refund_pending'] + amount)
        outcomes.append({'amount': amount, 'payer': 'U', 'result': 'original_method_return_requested', 'external_arrival': 'pending_Day4'})
    elif kind == 'group_invoice_journal':
        entries = deepcopy(resources['invoice_draft']['fields']['entries'])
        if not entries:
            raise ValueError('No invoice posting submitted')
        for entry in entries:
            owner = {'U-Y': 'U', 'Z-Y': 'Z'}[entry['invoice_ref']]
            prefix = 'Y' if owner == 'U' else 'Z'
            amount = entry['amount']
            if resources['Y_actual']['fields'][owner] != 'confirmed' or amount > money[prefix + '_balance']:
                raise ValueError('No such current payable invoice balance')
            if entry['instrument_ref'] == 'U-wallet':
                if amount > money['wallet']:
                    raise ValueError('Insufficient actual wallet balance')
                money['wallet'] -= amount
            else:
                if owner != 'Z' or at > 1740 or amount > money['voucher_value']:
                    raise ValueError('Named voucher scope, expiry or available value does not support this posting')
                if money['voucher_service'] != 'available':
                    return {'facts': {'posted': False, 'reason': 'Actual issuer unavailable; no journal entry posted.'}}
                money['voucher_value'] -= amount
                money['voucher_status'] = 'redeemed' if money['voucher_value'] == 0 else 'partly_redeemed'
            primary = min(amount, money[prefix + '_primary_due'])
            money[prefix + '_primary_due'] -= primary
            money[prefix + '_secondary_due'] -= amount - primary
            money[prefix + '_primary_open'] = money[prefix + '_primary_due'] > 0
            money[prefix + '_secondary_open'] = money[prefix + '_secondary_due'] > 0
            money[prefix + '_balance'] -= amount
            money[prefix + '_paid'] += amount
            outcomes.append(dict(entry, actually_posted=True, primary_amount=primary, secondary_amount=amount - primary))
    else:
        raise ValueError('Unknown native billing operation')
    receipt = {'id': 'tier-billing-' + kind + '-' + str(at), 'kind': 'receipt', 'channel': 'private',
               'editable': False, 'created_at': at, 'text': 'Actual native accounting: ' + json.dumps(outcomes, sort_keys=True) +
               '. This is not an authority or semantic-completion verdict.', 'actual_results': outcomes}
    return {'effect': {'set': {'U_finance': money, 'X_actual': x, 'Y_actual': y}, 'add': [receipt]},
            'facts': {'posted': True, 'actual_results': outcomes}}
