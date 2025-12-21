import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any

def get_file_sha256(file_path: Path) -> str:
    """Calculates SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def calculate_data_fingerprint(file_paths: List[Path]) -> str:
    """
    Calculates a combined fingerprint for a list of data files.
    Format: combined_shas + total_size
    """
    combined = hashlib.sha256()
    total_size = 0
    
    # Sort paths for determinism
    for path in sorted(file_paths):
        if path.exists():
            file_sha = get_file_sha256(path)
            combined.update(file_sha.encode())
            total_size += path.stat().st_size
            
    # Mix in total size to catch truncation/changes even if hash collision (unlikely)
    combined.update(str(total_size).encode())
    return combined.hexdigest()

def calculate_config_signature(config: Dict[str, Any]) -> str:
    """Calculates SHA256 hash of a configuration dictionary (canonical JSON)."""
    config_json = json.dumps(config, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(config_json.encode()).hexdigest()
