"""Batch019 registry; cases are added only after preflight gate."""
from helpers import pair
from cases_preflight import REGISTRY
try:
 from cases_primary import REGISTRY as PRIMARY
except ImportError:PRIMARY={}
REGISTRY.update(PRIMARY)
from cases_medium import REGISTRY as MEDIUM
REGISTRY.update(MEDIUM)
from cases_hard import REGISTRY as HARD
REGISTRY.update(HARD)
def cases(ids=None):return [pair(fn) for sid,fn in sorted(REGISTRY.items()) if ids is None or sid in ids]
