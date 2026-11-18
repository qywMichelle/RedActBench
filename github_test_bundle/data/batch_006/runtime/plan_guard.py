"""Constructor-only trajectory integrity guards, not candidate quality scoring."""
from runtime import run

def check_authored_plans(c):
    reference = c['plan']
    event_times = {e['at'] for e in c['events']}
    variants = {'reference': reference, 'alternative': c['alternative'], **c.get('additional_plans', {})}
    for mode in ('failure_initial', 'failure_near'):
        control = c[mode]
        index = control['index']
        original = reference[index]
        changed = control['action']
        assert original.get('target') == changed.get('target'), (c['id'], mode, 'mutation drifted to another target')
        assert original['action'] == changed['action'], (c['id'], mode, 'mutation replaced a wait or different operation')
        plan = [dict(a) for a in reference]
        plan[index] = dict(changed)
        if mode == 'failure_near':
            assert not any(a.get('target') == changed.get('target') and a['action'] in ('WRITE', 'SET') for a in plan[index + 1:]), (c['id'], 'near-miss overwritten later')
        variants[mode] = plan
    results = []
    for name, plan in variants.items():
        waits = {a['until'] for a in plan if a['action'] == 'WAIT'}
        # Author plans deliberately use explicit phase waits; this is not a restriction on candidate paths.
        assert event_times <= waits, (c['id'], name, 'missing authored event-phase wait', event_times - waits)
        results.append({'strategy': name, 'independent_event_waits': sorted(event_times), 'explicit_phase_waits_present': True})
    return results
