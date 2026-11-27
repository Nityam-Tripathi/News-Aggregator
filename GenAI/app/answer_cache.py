"""Process-local TTL/LRU cache of complete answers, keyed by actual retrieved evidence."""
import hashlib
import json
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import monotonic

class AnswerCache:
    def __init__(self, max_entries=128, ttl=300, clock=monotonic):
        self.max_entries, self.ttl, self.clock = max_entries, ttl, clock
        self.entries = OrderedDict()
        self.lock = Lock()

    def get(self, key):
        with self.lock:
            item = self.entries.get(key)
            if item is None:
                return None
            expires, value = item
            if expires <= self.clock():
                del self.entries[key]
                return None
            self.entries.move_to_end(key)
            return deepcopy(value)

    def put(self, key, value):
        if self.max_entries <= 0 or self.ttl <= 0 or not value.strip():
            return
        with self.lock:
            self.entries[key] = (self.clock()+self.ttl, value)
            self.entries.move_to_end(key)
            while len(self.entries) > self.max_entries:
                self.entries.popitem(last=False)

def cache_key(query, context, sources, model, prompt_version):
    return hashlib.sha256(json.dumps([query,context,sources,model,prompt_version],
        ensure_ascii=False, sort_keys=True).encode()).hexdigest()

answer_cache = AnswerCache()
