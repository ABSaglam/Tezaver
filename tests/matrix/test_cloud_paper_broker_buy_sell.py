import os
import json
import pytest
from tezaver.matrix.core.cloud_runtime import cloud_runtime_tick
from tezaver.matrix.core.paper_broker import load_portfolio

def test_cloud_paper_broker_buy_sell(tmp_path):
    home = str(tmp_path)
    
    # 1. Setup Bars
    # Bar 1: Green (Open 100, Close 105) -> Should BUY
    # Bar 2: Red (Open 105, Close 100) -> Should SELL
    bars = [
        {"ts": 1000, "open": 100, "close": 105, "closed": True}, 
        {"ts": 2000, "open": 105, "close": 100, "closed": True}
    ]
    bars_path = tmp_path / "bars.json"
    with open(bars_path, "w") as f:
        json.dump(bars, f)
        
    # 2. Setup Strategy
    s_a = tmp_path / "cloud_registry" / "strategies" / "STRAT_A"
    os.makedirs(s_a, exist_ok=True)
    with open(s_a / "status.json", "w") as f: json.dump({"status": "ACTIVE"}, f)
    with open(s_a / "strategy.json", "w") as f:
        json.dump({
            "timeframe": "1s",
            "bars_source": {"type": "JSON_FILE", "path": str(bars_path)}
        }, f)
        
    # 3. Run Tick
    res = cloud_runtime_tick(home, ticks=1, steps_per_strategy=5)
    
    # 4. Verify Portfolio
    pf = load_portfolio(home, "STRAT_A")
    assert pf["position_qty"] == 0 # Bought then Sold = 0
    assert pf["last_fill_ts"] == 2000
    
    # 5. Verify Orders Log
    ord_path = tmp_path / "cloud_runtime" / "strategies" / "STRAT_A" / "orders.ndjson"
    lines = ord_path.read_text().strip().split("\n")
    
    order_news = [l for l in lines if "ORDER_NEW" in l]
    order_fills = [l for l in lines if "ORDER_FILLED" in l]
    pos_updates = [l for l in lines if "POSITION_UPDATE" in l]
    
    assert len(order_news) == 2
    assert len(order_fills) == 2
    assert len(pos_updates) == 2
    
    # Check First Order (BUY)
    o1 = json.loads(order_news[0])
    assert o1["type"] == "ORDER_NEW"
    assert o1["payload"]["side"] == "BUY"
    assert o1["payload"]["price"] == 105
    
    # Check Second Order (SELL)
    o2 = json.loads(order_news[1])
    assert o2["type"] == "ORDER_NEW"
    assert o2["payload"]["side"] == "SELL"
    assert o2["payload"]["price"] == 100
