import hashlib
import os
from typing import List

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def fingerprint_file(path: str) -> str:
    """Computes SHA256 of a file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "rb") as f:
        return sha256_bytes(f.read())

def fingerprint_ts_list(ts_list: List[int]) -> str:
    """Computes deterministic SHA256 of sorted timestamp list."""
    # Ensure determinism by sorting? Or strictly validate order elsewhere?
    # Requirement: "normalized: ',' join"
    normalized = ",".join(str(ts) for ts in ts_list)
    return sha256_bytes(normalized.encode("utf-8"))
