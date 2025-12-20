from typing import List, Dict

ALLOWED_KEYS = ["rsi", "macd", "volume_z", "atr", "ma_slope"]

def check_signatures(signatures: Dict[str, Dict[str, float]]) -> List[str]:
    """Validates signature metrics against basic sanity rules."""
    errors = []
    
    for key, metrics in signatures.items():
        if key not in ALLOWED_KEYS:
            errors.append(f"Unknown signature key: {key}")
            continue
            
        if not isinstance(metrics, dict):
            errors.append(f"Signature {key} metrics must be a dict")
            continue
            
        # Check required stats
        for req in ["min", "max", "mean"]:
            if req not in metrics:
                errors.append(f"Signature {key} missing stat: {req}")
            elif not isinstance(metrics[req], (int, float)):
                errors.append(f"Signature {key}.{req} must be a number")
                
        if errors: continue # Skip logic check if structure invalid
        
        mn = metrics["min"]
        mx = metrics["max"]
        mu = metrics["mean"]
        
        # Sanity Logic
        if mn > mx:
            errors.append(f"Signature {key}: min ({mn}) > max ({mx})")
        
        if not (mn <= mu <= mx):
             errors.append(f"Signature {key}: mean ({mu}) not between min/max")
             
        # Specific constraints
        if key == "rsi":
            if mn < 0 or mx > 100:
                errors.append(f"Signature rsi out of bounds [0, 100]: {mn}-{mx}")
        
        if key == "atr":
            if mn < 0:
                errors.append(f"Signature atr cannot be negative: {mn}")
                
    return errors
