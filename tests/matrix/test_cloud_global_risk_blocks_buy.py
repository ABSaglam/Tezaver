import os
import json
import pytest
from tezaver.matrix.core.cloud_runtime import cloud_runtime_tick
from tezaver.matrix.core.paper_broker import load_portfolio
from tezaver.matrix.core.global_risk import save_global_risk, load_global_risk

def test_cloud_global_risk_blocks_buy(tmp_path):
    home = str(tmp_path)
    
    # 1. Setup Global Risk -> Max Positions = 1
    cfg = load_global_risk(home)
    cfg["max_open_positions"] = 1
    save_global_risk(home, cfg)
    
    # 2. Setup Bars (Green -> BUY req)
    bars = [{"ts": 1000, "open": 100, "close": 105, "closed": True}]
    bars_path = tmp_path / "bars.json"
    with open(bars_path, "w") as f: json.dump(bars, f)
    
    # 3. Setup 2 Strategies
    # Both active, both using this bar -> both want to BUY
    for sid in ["STRAT_A", "STRAT_B"]:
        d = tmp_path / "cloud_registry" / "strategies" / sid
        os.makedirs(d, exist_ok=True)
        with open(d / "status.json", "w") as f: json.dump({"status": "ACTIVE"}, f)
        with open(d / "strategy.json", "w") as f:
            json.dump({
                "timeframe": "1s",
                "bars_source": {"type": "JSON_FILE", "path": str(bars_path)}
            }, f)
            
    # 4. Run Tick
    # Strategies processed alphabetically? A then B?
    # A buys -> Total Pos 1.
    # B buys -> Blocked (Exceeds 1)? Wait, totals are updated during loop? 
    # Yes, implementation updates `risk_totals` in memory.
    res = cloud_runtime_tick(home, ticks=1, steps_per_strategy=1)
    
    # 5. Verify
    # STRAT_A should have bought
    pf_a = load_portfolio(home, "STRAT_A")
    assert pf_a["position_qty"] == 1.0
    
    # STRAT_B should be blocked
    pf_b = load_portfolio(home, "STRAT_B")
    assert pf_b["position_qty"] == 0.0
    
    # Check Events
    events_path = tmp_path / "cloud_runtime" / "runs" / res["cloud_run_id"] / "events.ndjson"
    lines = events_path.read_text().strip().split("\n")
    
    block_evt = None
    for l in lines:
        e = json.loads(l)
        if e["type"] == "GLOBAL_RISK_BLOCK" and e["strategy_id"] == "STRAT_B":
            block_evt = e
            break
            
    assert block_evt
    assert block_evt["payload"]["decision"] == "BUY"
    assert block_evt["payload"]["reason"] == "GLOBAL_RISK_LIMIT"
