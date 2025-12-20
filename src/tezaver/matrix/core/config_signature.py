import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, Any

@dataclass
class ConfigSpec:
    run_profile: str
    symbol: str
    timeframe: str
    risk: Dict[str, Any]
    governance: Dict[str, Any]
    extras: Dict[str, Any] = field(default_factory=dict)

def to_canonical_json(data: Any) -> str:
    """
    Produces a canonical JSON string:
    - Sorted keys
    - No whitespace (separators=(',', ':'))
    - Ensure ASCII=False (though usually fine, we want consistent bytes)
    """
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def compute_config_signature(spec: ConfigSpec) -> str:
    """
    Computes a deterministic SHA256 signature for the configuration.
    """
    data = asdict(spec)
    canonical = to_canonical_json(data)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
