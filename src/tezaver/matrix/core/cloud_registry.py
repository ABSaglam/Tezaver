import os
import json
import time
from typing import List, Dict, Optional
from tezaver.matrix.core.checksums import write_json

def get_registry_dir(home: str) -> str:
    path = os.path.join(home, "cloud_registry", "strategies")
    os.makedirs(path, exist_ok=True)
    return path

def list_strategies(home: str) -> List[str]:
    reg_dir = get_registry_dir(home)
    if not os.path.exists(reg_dir): return []
    return sorted([d for d in os.listdir(reg_dir) if os.path.isdir(os.path.join(reg_dir, d))])

def read_strategy(home: str, strategy_id: str) -> Optional[Dict]:
    reg_dir = get_registry_dir(home)
    strat_dir = os.path.join(reg_dir, strategy_id)
    if not os.path.exists(strat_dir): return None
    
    s_path = os.path.join(strat_dir, "strategy.json")
    st_path = os.path.join(strat_dir, "status.json")
    
    data = {}
    if os.path.exists(s_path):
        with open(s_path) as f: data.update(json.load(f))
        
    if os.path.exists(st_path):
        with open(st_path) as f: data["status_info"] = json.load(f)
    else:
        data["status_info"] = {"status": "UNKNOWN"}
        
    return data

def set_status(home: str, strategy_id: str, status: str) -> None:
    valid_statuses = ["ACTIVE", "PAUSED", "REVOKED"]
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}")
        
    reg_dir = get_registry_dir(home)
    strat_dir = os.path.join(reg_dir, strategy_id)
    if not os.path.exists(strat_dir):
        raise ValueError(f"Strategy not found: {strategy_id}")
        
    st_path = os.path.join(strat_dir, "status.json")
    write_json(st_path, {"status": status, "updated_ts": int(time.time())})
