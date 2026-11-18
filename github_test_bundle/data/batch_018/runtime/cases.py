"""Batch018 stable case registry; A/B are paired configurations, not new tasks."""
from common import pair
from cases_core import REGISTRY
try:
 from cases_hard import REGISTRY as HARD
 REGISTRY.update(HARD)
except ImportError:pass
try:
 from cases_medium import REGISTRY as MEDIUM
 REGISTRY.update(MEDIUM)
except ImportError:pass
def cases(ids=None):return [pair(fn) for sid,fn in sorted(REGISTRY.items()) if ids is None or sid in ids]
