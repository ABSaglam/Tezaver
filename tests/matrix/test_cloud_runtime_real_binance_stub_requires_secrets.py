import os
import json
import pytest
from tezaver.matrix.core.cloud_runtime import cloud_runtime_tick
from tezaver.matrix.core.broker_config import save_broker_config

def test_cloud_runtime_real_binance_stub_requires_secrets(tmp_path):
    home = str(tmp_path)
    
    # Setup Strategy (Green Bar -> BUY)
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
        
    # Case 1: REAL_BINANCE_STUB but Missing Secrets
    save_broker_config(home, {"mode": "REAL_BINANCE_STUB"})
    
    res = cloud_runtime_tick(home, ticks=1, steps_per_strategy=1)
    
    events_path = tmp_path / "cloud_runtime" / "runs" / res["cloud_run_id"] / "events.ndjson"
    lines = events_path.read_text().strip().split("\n")
    
    found_misconfig = False
    found_real_order = False
    
    for l in lines:
        e = json.loads(l)
        if e["type"] == "BROKER_MISCONFIG": found_misconfig = True
        if e["type"] == "REAL_ORDER_WOULD_SEND": found_real_order = True
        
    assert found_misconfig
    assert not found_real_order # Should be blocked
    
    # Reset Cursor for Case 2
    from tezaver.matrix.core.cloud_runtime import save_strategy_state, load_strategy_state
    st = load_strategy_state(home, sid)
    st["cursor"] = 0
    save_strategy_state(home, sid, st)

    # Case 2: Secrets Present
    os.makedirs(tmp_path / "secrets", exist_ok=True)
    with open(tmp_path / "secrets" / "binance.json", "w") as f:
        json.dump({"api_key": "k", "api_secret": "s"}, f)
        
    res2 = cloud_runtime_tick(home, ticks=1, steps_per_strategy=1)
    lines2 = (tmp_path / "cloud_runtime" / "runs" / res2["cloud_run_id"] / "events.ndjson").read_text().strip().split("\n")
    
    found_real_order_2 = False
    for l in lines2:
        e = json.loads(l)
        if e["type"] == "REAL_ORDER_WOULD_SEND": found_real_order_2 = True
        
    assert found_real_order_2
