"""Hashing utilities for data integrity and verification."""

import hashlib
from typing import Tuple

def hash_string(data: str, algorithm: str = 'sha256') -> str:
    """Hash a string using the specified algorithm."""
    return hashlib.new(algorithm, data.encode()).hexdigest()

def verify_hash(data: str, hash_value: str, algorithm: str = 'sha256') -> bool:
    """Verify if data matches the given hash."""
    return hash_string(data, algorithm) == hash_value

def hash_file(filepath: str, algorithm: str = 'sha256') -> str:
    """Hash file contents."""
    hasher = hashlib.new(algorithm)
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()
