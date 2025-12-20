import os
import json
import pytest
from tezaver.matrix.core.userstream_reconciler import reconcile_stream
from tezaver.matrix.core.paper_broker import save_portfolio, load_portfolio

def test_userstream_reconcile_order_trade_update_updates_portfolio(tmp_path):
    home = str(tmp_path)
    os.makedirs(tmp_path / "cloud_runtime" / "userstream", exist_ok=True)
    
    # Setup Strategy & Portfolio
    sid = "STRAT1"
    os.makedirs(tmp_path / "cloud_runtime" / "strategies" / sid, exist_ok=True)
    save_portfolio(home, sid, {"inventory": {"BTCUSDT": 0.0}})
    
    # 1. Write Raw Event: BUY FILL
    # msg: {e: ORDER_TRADE_UPDATE, o: {c: "mx_STRAT1_etc", s: BTCUSDT, S: BUY, l: 1.0, z: 1.0, X: FILLED}}
    evt1 = {
        "e": "ORDER_TRADE_UPDATE",
        "o": {
            "c": "mx_STRAT1_123456_uuid",
            "s": "BTCUSDT",
            "S": "BUY",
            "l": "1.0", # Last filled qty (Delta)
            "z": "1.0", # Cum filled
            "X": "FILLED",
            "L": "50000"
        }
    }
    
    with open(tmp_path / "cloud_runtime" / "userstream" / "raw.ndjson", "w") as f:
        f.write(json.dumps(evt1) + "\n")
        
    # 2. Reconcile
    res = reconcile_stream(home)
    assert res["processed"] == 1
    assert res["updates"] == 1
    
    # 3. Verify Portfolio (Buying 1.0)
    pf = load_portfolio(home, sid)
    assert pf["inventory"]["BTCUSDT"] == 1.0
    
    # 4. Verify orders.ndjson
    ops = (tmp_path / "cloud_runtime" / "strategies" / sid / "orders.ndjson").read_text()
    assert "EXCHANGE_ORDER_UPDATE" in ops
    assert "FILLED" in ops
    
    # 5. Write Raw Event: SELL FILL (Reduce 0.5)
    evt2 = {
        "e": "ORDER_TRADE_UPDATE",
        "o": {
            "c": "mx_STRAT1_999999_uuid2",
            "s": "BTCUSDT",
            "S": "SELL",
            "l": "0.5",
            "z": "0.5",
            "X": "FILLED"
        }
    }
    with open(tmp_path / "cloud_runtime" / "userstream" / "raw.ndjson", "a") as f:
        f.write(json.dumps(evt2) + "\n")
        
    res2 = reconcile_stream(home)
    assert res2["processed"] == 1
    
    pf2 = load_portfolio(home, sid)
    assert pf2["inventory"]["BTCUSDT"] == 0.5 # 1.0 - 0.5
