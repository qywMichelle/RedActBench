"""Compare complete real native request bodies and tile SHA/coordinates offline."""
import copy
import hashlib
import json
from pathlib import Path
import resource
import time

import native_tile_cache
import resume_with_image_budget as images

root = Path(__file__).resolve().parent
fixture = root / 'github_test_bundle/output/api-preflight/blocked-request-fixture.json'
body = json.loads(fixture.read_text())
# Fixture may contain the wrapper used by the original full-request regression.
if 'body' in body and 'messages' not in body:
    body = body['body']
body['model'] = 'claude-opus-5-5-science'


def snapshot():
    started = time.process_time()
    protocol, native = images.translate(copy.deepcopy(body))
    seconds = time.process_time() - started
    sha = hashlib.sha256(json.dumps(native, sort_keys=True, ensure_ascii=False,
                                   separators=(',', ':')).encode()).hexdigest()
    metadata = copy.deepcopy((images.LOCAL.resizes, images.LOCAL.tiles))
    del native
    return protocol, sha, metadata, seconds


baseline = snapshot()  # Includes the existing resize cache's cold miss.
cache = native_tile_cache.install(images)
cold = snapshot()
warm = snapshot()
assert baseline[:3] == cold[:3] == warm[:3], 'Native request payload or image metadata changed'
assert cache.hits > 0 and cache.size <= cache.max_bytes
report = {'first_uncached_cpu_seconds': baseline[3], 'tile_cache_cold_cpu_seconds': cold[3],
          'tile_cache_warm_cpu_seconds': warm[3], 'request_sha256': baseline[1],
          'cache_bytes': cache.size, 'cache_limit_bytes': cache.max_bytes,
          'hits': cache.hits, 'misses': cache.misses,
          'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          'deployment': 'staged_only_existing_bridge_not_restarted'}
(root / 'github_test_bundle/output/performance/tile-cache-benchmark.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
