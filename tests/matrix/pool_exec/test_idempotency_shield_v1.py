import pytest
import json
from pathlib import Path
from tezaver.matrix.pool_exec.pool_order_intents_v1 import (
    PoolOrderIntentV1,
    PoolOrderIntentsReportV1,
    now_iso
)
from tezaver.matrix.pool_exec.pool_executor_sim_v0 import run_sim_execution
from tezaver.matrix.pool_exec.idempotency_store_v1 import load_keys, keys_count

def create_intents_report(run_id: str, stage: str, intents_data: list) -> PoolOrderIntentsReportV1:
    """Create intents report from data."""
    intents = []
    for d in intents_data:
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
            notional=100.0,
            mode="MARKET_SIM",
            policy_spec=None,
            reason="OK",
            created_ts_iso=now_iso()
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

def test_first_run_executes_all(tmp_path):
    """First run executes all intents."""
    reports_dir = tmp_path / "war" / "run_first" / "reports"
    reports_dir.mkdir(parents=True)
    
    report = create_intents_report("run_first", "war", [
        {"order_key": "key_1", "intent_id": "i1", "symbol": "BTC"},
        {"order_key": "key_2", "intent_id": "i2", "symbol": "ETH"}
    ])
    
    result = run_sim_execution(report, reports_dir, {}, home_dir=str(tmp_path))
    
    assert result["executed_sim"] == 2
    assert result["skipped_idempotent"] == 0
    
    # Keys file created
    assert keys_count("war", "run_first", str(tmp_path)) == 2

def test_second_run_blocks_duplicates(tmp_path):
    """Second run blocks duplicates."""
    reports_dir = tmp_path / "war" / "run_dup" / "reports"
    reports_dir.mkdir(parents=True)
    
    report = create_intents_report("run_dup", "war", [
        {"order_key": "dup_1", "intent_id": "d1", "symbol": "BTC"},
        {"order_key": "dup_2", "intent_id": "d2", "symbol": "ETH"}
    ])
    
    # First run
    result1 = run_sim_execution(report, reports_dir, {}, home_dir=str(tmp_path))
    assert result1["executed_sim"] == 2
    
    # Second run - same intents
    result2 = run_sim_execution(report, reports_dir, {}, home_dir=str(tmp_path))
    assert result2["executed_sim"] == 0
    assert result2["skipped_idempotent"] == 2
    
    # Check idempotency report
    idemp_path = reports_dir / "pool_idempotency_report_v1.json"
    with open(idemp_path) as f:
        idemp_data = json.load(f)
    
    assert idemp_data["skipped_idempotent"] == 2
    assert len(idemp_data["sample_blocked"]) == 2

def test_partial_new_intent(tmp_path):
    """New intents are executed, old ones blocked."""
    reports_dir = tmp_path / "war" / "run_partial" / "reports"
    reports_dir.mkdir(parents=True)
    
    # First run with 2 intents
    report1 = create_intents_report("run_partial", "war", [
        {"order_key": "old_1", "intent_id": "o1", "symbol": "BTC"},
        {"order_key": "old_2", "intent_id": "o2", "symbol": "ETH"}
    ])
    
    result1 = run_sim_execution(report1, reports_dir, {}, home_dir=str(tmp_path))
    assert result1["executed_sim"] == 2
    
    # Second run with 3 intents (2 old + 1 new)
    report2 = create_intents_report("run_partial", "war", [
        {"order_key": "old_1", "intent_id": "o1", "symbol": "BTC"},
        {"order_key": "old_2", "intent_id": "o2", "symbol": "ETH"},
        {"order_key": "new_3", "intent_id": "n3", "symbol": "SOL"}
    ])
    
    result2 = run_sim_execution(report2, reports_dir, {}, home_dir=str(tmp_path))
    assert result2["executed_sim"] == 1  # Only new one
    assert result2["skipped_idempotent"] == 2  # Old ones blocked
    
    # Total keys should be 3
    assert keys_count("war", "run_partial", str(tmp_path)) == 3
