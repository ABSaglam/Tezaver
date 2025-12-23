import pytest
import json
from pathlib import Path
from tezaver.matrix.pool_exec.pool_order_intents_v1 import (
    PoolOrderIntentV1,
    PoolOrderIntentsReportV1,
    now_iso
)
from tezaver.matrix.pool_exec.pool_executor_sim_v0 import run_sim_execution

def create_intents_report(run_id: str, stage: str, intents_data: list) -> PoolOrderIntentsReportV1:
    """Create intents report from data."""
    intents = []
    for d in intents_data:
        meta = d.get("meta", {})
        if "ref_price" not in meta:
            meta["ref_price"] = 100.0  # Default ref price for testing
        
        intents.append(PoolOrderIntentV1(
            intent_id=d.get("intent_id", "i1"),
            order_key=d.get("order_key", "k1"),
            stage=stage,
            run_id=run_id,
            action=d.get("action", "OPEN_POSITION"),
            symbol=d.get("symbol", "BTC"),
            timeframe="1h",
            bundle_id="b1",
            src="SELECTION",
            notional=d.get("notional", 100.0),
            mode="MARKET_SIM",
            policy_spec=d.get("policy_spec"),
            reason="OK",
            created_ts_iso=now_iso(),
            meta=meta
        ))
    
    return PoolOrderIntentsReportV1(
        run_id=run_id,
        stage=stage,
        engine_version="v1.0.0",
        data_fingerprint="DF",
        config_signature="CS",
        built_ts_iso=now_iso(),
        court_verdict="PASS",
        intents_total=len(intents),
        intents_open=len(intents),
        intents_close=0,
        intents=intents
    )

def test_executor_writes_fill_report(tmp_path):
    """Executor writes fill report with correct data."""
    reports_dir = tmp_path / "war" / "run_fill" / "reports"
    reports_dir.mkdir(parents=True)
    
    report = create_intents_report("run_fill", "war", [
        {"order_key": "f1", "intent_id": "i1", "symbol": "BTC", "notional": 100.0},
        {"order_key": "f2", "intent_id": "i2", "symbol": "ETH", "notional": 200.0}
    ])
    
    result = run_sim_execution(report, reports_dir, {}, home_dir=str(tmp_path))
    
    assert result["executed_sim"] == 2
    assert result["total_fee_cost"] > 0
    assert result["total_slippage_cost"] > 0
    
    # Check fill report exists
    fill_path = reports_dir / "pool_sim_fill_report_v1.json"
    assert fill_path.exists()
    
    with open(fill_path) as f:
        fill_data = json.load(f)
    
    assert fill_data["fills_total"] == 2
    assert len(fill_data["fills"]) == 2
    assert fill_data["totals"]["fee_cost"] > 0
    assert fill_data["totals"]["slippage_cost"] > 0

def test_policy_overrides_defaults(tmp_path):
    """Policy spec overrides default fee/slippage."""
    reports_dir = tmp_path / "war" / "run_policy" / "reports"
    reports_dir.mkdir(parents=True)
    
    # Custom policy with higher fee/slippage
    report = create_intents_report("run_policy", "war", [
        {
            "order_key": "p1",
            "intent_id": "i1",
            "symbol": "BTC",
            "notional": 1000.0,
            "policy_spec": {"fee_bps": 10.0, "slippage_bps": 20.0}
        }
    ])
    
    result = run_sim_execution(report, reports_dir, {}, home_dir=str(tmp_path))
    
    fill_path = reports_dir / "pool_sim_fill_report_v1.json"
    with open(fill_path) as f:
        fill_data = json.load(f)
    
    fill = fill_data["fills"][0]
    
    # fee_bps=10 → fee_cost = 1000 * 10/10000 = 1.0
    assert abs(fill["fee_cost"] - 1.0) < 1e-6
    # slippage_bps=20 → eff_price = 100 * (1 + 20/10000) = 100.2
    assert abs(fill["eff_price"] - 100.2) < 1e-6
