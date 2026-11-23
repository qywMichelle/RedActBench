"""Lossless bounded native tile reuse, staged for the next normal bridge launch."""
from collections import OrderedDict
import copy
import hashlib
import threading


class TileCache:
    def __init__(self, images, max_bytes=16 * 1024 * 1024):
        self.images, self.original = images, images.message_image_parts
        self.cache = OrderedDict()
        self.max_bytes, self.size = max_bytes, 0
        self.hits = self.misses = 0
        self.lock = threading.Lock()

    def __call__(self, data, content_index):
        key = (hashlib.sha256(data).digest(), content_index,
               self.images.MAX_MESSAGE_IMAGE_SIDE, self.images.MAX_ENCODED_IMAGE_BYTES,
               self.images.PIL_VERSION)
        with self.lock:
            if key in self.cache:
                result, weight = self.cache.pop(key)
                self.cache[key] = (result, weight)
                self.hits += 1
                return copy.deepcopy(result)
            result = self.original(data, content_index)
            self.misses += 1
            parts, metadata = result
            weight = sum(len(p['source']['data']) if p['type'] == 'image' else len(p['text'])
                         for p in parts) + 4096
            if weight <= self.max_bytes:
                while self.cache and self.size + weight > self.max_bytes:
                    _, (_, removed) = self.cache.popitem(last=False)
                    self.size -= removed
                # Only immutable strings are shared; callers may mutate dictionaries.
                self.cache[key] = (copy.deepcopy(result), weight)
                self.size += weight
            return result


def install(images, max_bytes=16 * 1024 * 1024):
    cache = TileCache(images, max_bytes)
    images.message_image_parts = cache
    return cache
