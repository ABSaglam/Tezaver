import os
import json
import time
from typing import Dict, Any

DEFAULT_BROKER_CONFIG = {
    "mode": "PAPER", # PAPER, REAL_DRYRUN
    "exchange": "BINANCE",
    "reduce_only": True,
    "last_update_ts": 0
}

def get_broker_config_path(home: str) -> str:
    return os.path.join(home, "cloud_runtime", "broker_config.json")

def load_broker_config(home: str) -> Dict[str, Any]:
    path = get_broker_config_path(home)
    if os.path.exists(path):
        try:
            with open(path) as f:
                cfg = json.load(f)
                # Merge defaults
                for k, v in DEFAULT_BROKER_CONFIG.items():
                    if k not in cfg: cfg[k] = v
                return cfg
        except:
            pass
    return DEFAULT_BROKER_CONFIG.copy()

def save_broker_config(home: str, config: Dict[str, Any]) -> None:
    path = get_broker_config_path(home)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    config["last_update_ts"] = int(time.time() * 1000)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
