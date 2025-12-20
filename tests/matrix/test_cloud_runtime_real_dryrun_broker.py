import os
import json
import pytest
from tezaver.matrix.core.cloud_runtime import cloud_runtime_tick
from tezaver.matrix.core.broker_config import save_broker_config, load_broker_config

def test_cloud_runtime_real_dryrun_broker(tmp_path):
    home = str(tmp_path)
    
    # 1. Setup Broker Config -> REAL_DRYRUN
    cfg = load_broker_config(home)
    cfg["mode"] = "REAL_DRYRUN"
    save_broker_config(home, cfg)
    
    # 2. Setup Active Strategy (Green Bar -> BUY)
    bars = [{"ts": 1000, "open": 100, "close": 105, "closed": True}]
    bars_path = tmp_path / "bars.json"
    with open(bars_path, "w") as f: json.dump(bars, f)
    
    sid = "STRAT_A"
    d = tmp_path / "cloud_registry" / "strategies" / sid
    os.makedirs(d, exist_ok=True)
    with open(d / "status.json", "w") as f: json.dump({"status": "ACTIVE"}, f)
    with open(d / "strategy.json", "w") as f:
        json.dump({
            "timeframe": "1s",
            "symbol": "BTCUSDT",
            "bars_source": {"type": "JSON_FILE", "path": str(bars_path)}
        }, f)
        
    # 3. Run Tick
    res = cloud_runtime_tick(home, ticks=1, steps_per_strategy=1)
    
    # 4. Verify
    events_path = tmp_path / "cloud_runtime" / "runs" / res["cloud_run_id"] / "events.ndjson"
    lines = events_path.read_text().strip().split("\n")
    
    broker_mode_evt = None
    real_order_evt = None
    
    for l in lines:
        e = json.loads(l)
        if e["type"] == "BROKER_MODE": broker_mode_evt = e
        if e["type"] == "REAL_ORDER_WOULD_SEND": real_order_evt = e
        
    assert broker_mode_evt
    assert broker_mode_evt["payload"]["mode"] == "REAL_DRYRUN"
    
    assert real_order_evt
    assert real_order_evt["payload"]["accepted"]
    assert real_order_evt["payload"]["dryrun"]
    assert real_order_evt["payload"]["details"]["side"] == "BUY"
    assert real_order_evt["payload"]["details"]["symbol"] == "BTCUSDT"
