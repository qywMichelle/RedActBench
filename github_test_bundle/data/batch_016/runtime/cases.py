from common import pair
from cases_preflight import banter,repair_reports,concert_routes,sync_permissions,craft_shift
REGISTRY={'t2-01':banter,'t2-02':repair_reports,'t3-03':concert_routes,'t4-03':sync_permissions,'t5-02':craft_shift}
def cases(ids=None):
 rows=[pair(fn) for sid,fn in REGISTRY.items() if ids is None or sid in ids]
 from cases_hard import hard_cases
 rows.extend(c for c in hard_cases() if ids is None or c['short_id'] in ids)
 from cases_extra_medium import extra_medium_cases
 rows.extend(c for c in extra_medium_cases() if ids is None or c['short_id'] in ids)
 try:
  from cases_primary_medium import primary_cases
 except ImportError:primary_cases=lambda:[]
 rows.extend(c for c in primary_cases() if ids is None or c['short_id'] in ids)
 from constructor_revisions import revised_cases
 rows.extend(c for c in revised_cases() if ids is None or c['short_id'] in ids)
 from cases_primary_hard import revised_camera,revised_sync
 for sid,fn in [('t3-01',revised_camera),('t4-03',revised_sync)]:
  if ids is None or sid in ids:
   c=pair(fn);c['authored_by']='primary_coauthor';rows.append(c)
 by_id={c['short_id']:c for c in rows}
 from language_revisions import improve
 return sorted([improve(c) for c in by_id.values()],key=lambda c:c['short_id'])
