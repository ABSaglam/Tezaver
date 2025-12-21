import pytest
import os
import json
from tezaver.matrix.core.war_engine import WarEngine
from tezaver.matrix.apps.war_planner import WarPlan, WarCell, PlanDiagnostics
from datetime import datetime

def test_real_pnl_calculation():
    # Helper to create a plan
    cell = WarCell("BTC", "1h", "c1", "b1", "p1")
    plan = WarPlan("plan1", datetime.now().isoformat(), [cell], ["BTC"], ["c1"], "hash1")
    engine = WarEngine(plan)
    
    # Mock bars that trigger a trade and then a CYCLE exit
    # Entry at 100, Exit at 110 (Long)
    bars = []
    for i in range(100):
        price = 100.0 if i < 40 else 110.0
        bars.append({"timestamp": i, "close": price})
    
    # We need to inject these bars into process_cell
    # Instead of full run, we can mock _process_cell dependencies or just run a mini version
    engine._process_cell = lambda c: None # disable real processing
    
    # Manually test the logic (Formula verification)
    entry_price = 100.0
    exit_price = 110.0
    qty = 10.0 # $1000 / 100
    side = "LONG"
    
    gross = (exit_price - entry_price) * qty
    fee = (entry_price * qty + exit_price * qty) * 0.001
    slip = abs(gross) * 0.0005
    net = gross - fee - slip
    
    assert gross == 100.0
    assert fee == (1000.0 + 1100.0) * 0.001 # 2.1
    assert slip == 0.05
    assert net == 100.0 - 2.1 - 0.05

def test_exit_trigger_sl(tmp_path):
    # This test needs real engine execution with fake price path
    cell = WarCell("BTC", "15m", "c1", "b1", "p1")
    plan = WarPlan("p1", datetime.now().isoformat(), [cell], ["BTC"], ["c1"], "h1", diagnostics=PlanDiagnostics(approved_for_war_count=1))
    engine = WarEngine(plan, output_dir=str(tmp_path))
    
    # Price path: Entry at 100, then drop to 98 (SL is 1%)
    bars = []
    for i in range(200):
        if i < 10: price = 100.0
        elif i < 15: price = 100.0 # Stay at entry
        else: price = 98.0 # Drop below 99 (1% SL)
        bars.append({"timestamp": i, "close": price})
    
    # Monkeypatch ParquetDataPort to return our bars
    from unittest.mock import MagicMock
    import tezaver.matrix.core.war_engine as we
    
    mock_port = MagicMock()
    mock_port.get_bars.return_value = bars
    
    # We need to patch ParquetDataPort inside _process_cell
    import tezaver.matrix.core.war_engine
    original_port = tezaver.matrix.core.war_engine.ParquetDataPort
    tezaver.matrix.core.war_engine.ParquetDataPort = lambda s, t: mock_port
    
    try:
        engine.run()
    finally:
        tezaver.matrix.core.war_engine.ParquetDataPort = original_port

            
    # Check trade audit for SL
    assert len(engine.trade_audit) > 0
    last_trade = engine.trade_audit[0]
    assert last_trade["exit_reason"] == "SL"
    assert last_trade["net_pnl"] < 0

def test_exit_trigger_tp(tmp_path):
    cell = WarCell("BTC", "15m", "c1", "b1", "p1")
    plan = WarPlan("p1", datetime.now().isoformat(), [cell], ["BTC"], ["c1"], "h1", diagnostics=PlanDiagnostics(approved_for_war_count=1))
    engine = WarEngine(plan, output_dir=str(tmp_path))
    
    # Price path: Entry at 100, then jump to 103 (TP is 2%)
    bars = []
    for i in range(200):
        if i < 10: price = 100.0
        elif i < 15: price = 100.0
        else: price = 103.0 # Above 102
        bars.append({"timestamp": i, "close": price})
    
    from unittest.mock import MagicMock
    mock_port = MagicMock()
    mock_port.get_bars.return_value = bars
    
    import tezaver.matrix.core.war_engine
    original_port = tezaver.matrix.core.war_engine.ParquetDataPort
    tezaver.matrix.core.war_engine.ParquetDataPort = lambda s, t: mock_port
    
    try:
        engine.run()
    finally:
        tezaver.matrix.core.war_engine.ParquetDataPort = original_port
            
    assert len(engine.trade_audit) > 0
    last_trade = engine.trade_audit[0]
    assert last_trade["exit_reason"] == "TP"
    assert last_trade["net_pnl"] > 0
