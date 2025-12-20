import os
import json
import time
from typing import Dict, Any, List

DEFAULT_RISK = {
    "max_open_positions": 999,
    "max_total_notional": 999999999.0,
    "max_open_trades_per_tick": 999,
    "paused": False,
    "last_update_ts": 0
}

def get_risk_config_path(home: str) -> str:
    return os.path.join(home, "cloud_runtime", "global_risk.json")

def load_global_risk(home: str) -> Dict[str, Any]:
    path = get_risk_config_path(home)
    if os.path.exists(path):
        try:
            with open(path) as f:
                cfg = json.load(f)
                # Merge with defaults ensuring keys exist
                for k, v in DEFAULT_RISK.items():
                    if k not in cfg: cfg[k] = v
                return cfg
        except:
            pass
    return DEFAULT_RISK.copy()

def save_global_risk(home: str, config: Dict[str, Any]) -> None:
    path = get_risk_config_path(home)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    config["last_update_ts"] = int(time.time() * 1000)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)

def compute_totals(home: str, active_strategies: List[str]) -> Dict[str, Any]:
    # Import here to avoid circular dependency if any, though paper_broker is core
    from tezaver.matrix.core.paper_broker import load_portfolio
    
    open_pos = 0
    total_notional = 0.0
    
    for sid in active_strategies:
        pf = load_portfolio(home, sid)
        qty = pf.get("position_qty", 0)
        avg = pf.get("avg_price", 0)
        # Notional = abs(qty) * avg (using avg price as proxy for current val)
        # Ideally we use current price but avg price is safe approximation for exposure magnitude if no live feed
        if qty != 0:
            open_pos += 1
            total_notional += abs(qty) * avg
            
    return {
        "open_positions": open_pos,
        "total_notional": total_notional
    }

def should_block_decision(config: Dict[str, Any], totals: Dict[str, Any], decision: str) -> bool:
    if decision != "BUY":
        return False # SELL/HOLD always allowed to reduce risk
        
    # Check Limits
    if totals["open_positions"] >= config["max_open_positions"]:
        return True
        
    if totals["total_notional"] >= config["max_total_notional"]:
        return True
        
    return False

def evaluate_risk_status(config: Dict[str, Any], totals: Dict[str, Any]) -> List[str]:
    reasons = []
    if totals["open_positions"] >= config["max_open_positions"]:
        reasons.append(f"Positions {totals['open_positions']} >= Limit {config['max_open_positions']}")
    if totals["total_notional"] >= config["max_total_notional"]:
        reasons.append(f"Notional {totals['total_notional']} >= Limit {config['max_total_notional']}")
    if config["paused"]:
        reasons.append("Kill Switch Active")
    return reasons
