from typing import List

def compute_higher_tf_closes(base_close_ts: List[int], higher_tf_seconds: int) -> List[int]:
    """Derives higher timeframe close timestamps from base timestamps."""
    higher_ms = higher_tf_seconds * 1000
    return [ts for ts in base_close_ts if ts % higher_ms == 0]

def validate_multi_tf_alignment(base_close_ts: List[int], higher_close_ts: List[int], higher_tf_seconds: int) -> List[str]:
    """Validates that higher TF timestamps are properly derived and aligned."""
    errors = []
    base_set = set(base_close_ts)
    higher_ms = higher_tf_seconds * 1000
    
    for ts in higher_close_ts:
        if ts % higher_ms != 0:
            errors.append(f"Higher TF timestamp {ts} not aligned to {higher_tf_seconds}s")
        if ts not in base_set:
            errors.append(f"Higher TF timestamp {ts} not found in base timestamps (orphan)")
            
    return errors
