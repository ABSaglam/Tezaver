"""
Sniper v4 - Hashing Module
==========================

Fingerprint and signature generation for deterministic verification.
"""

import hashlib
from typing import List


def compute_selection_fingerprint(trade_ids: List[str]) -> str:
    """
    Compute SHA1 fingerprint of sorted trade_id list.
    
    Args:
        trade_ids: List of trade_id strings
        
    Returns:
        12-character hex fingerprint
    """
    sorted_ids = sorted(trade_ids)
    content = "\n".join(sorted_ids)
    return hashlib.sha1(content.encode()).hexdigest()[:12]


def compute_pnl_signature(pnl_list: List[float]) -> str:
    """
    Compute SHA1 signature of sorted PnL values.
    
    Args:
        pnl_list: List of PnL percentages (as decimals, e.g., 0.08 not 8.0)
        
    Returns:
        12-character hex signature
    """
    sorted_pnl = sorted([f"{p:.6f}" for p in pnl_list])
    content = ",".join(sorted_pnl)
    return hashlib.sha1(content.encode()).hexdigest()[:12]


def compute_config_hash(config: dict) -> str:
    """
    Compute hash of configuration dict for run identity.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        10-character hex hash
    """
    import json
    content = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha1(content.encode()).hexdigest()[:10]
