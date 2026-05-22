import hashlib

_cache = {}

def hash_prompt(prompt: str):
    return hashlib.md5(prompt.encode()).hexdigest()

def get(prompt):
    return _cache.get(hash_prompt(prompt))

def set(prompt, response):
    _cache[hash_prompt(prompt)] = response
