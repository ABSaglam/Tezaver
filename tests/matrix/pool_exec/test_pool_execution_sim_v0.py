import pytest
import json
from pathlib import Path
from tezaver.matrix.pool_exec.pool_execution_runner_v0 import build_pool_order_intents_v1
from tezaver.matrix.pool_exec.pool_executor_sim_v0 import run_sim_execution, run_pool_execution_sim_v0

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)

def test_court_fail_zero_intents(tmp_path):
    """Court FAIL -> 0 intents."""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True)
    
    write_json(reports_dir / "pool_court_verdict_v1.json", {"verdict": "FAIL"})
    
    report = build_pool_order_intents_v1(reports_dir, "war", "run_1", {})
    
    assert report.court_verdict == "FAIL"
    assert report.intents_total == 0
    assert len(report.intents) == 0

def test_court_pass_creates_open_intents(tmp_path):
    """Court PASS + plan -> OPEN intents."""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True)
    
    write_json(reports_dir / "pool_court_verdict_v1.json", {"verdict": "PASS"})
    write_json(reports_dir / "pool_execution_summary_v1.json", {
        "plan": [
            {"action": "PLACE_ORDER", "symbol": "BTC", "timeframe": "1h", "bundle_id": "b1", "notional": 100},
            {"action": "PLACE_ORDER", "symbol": "ETH", "timeframe": "4h", "bundle_id": "b2", "notional": 150}
        ]
    })
    
    report = build_pool_order_intents_v1(reports_dir, "war", "run_2", {})
    
    assert report.court_verdict == "PASS"
    assert report.intents_open == 2
    assert report.intents_close == 0
    assert len(report.intents) == 2

def test_replacement_adds_close_open_intents(tmp_path):
    """Replacement suggested -> CLOSE + OPEN intents."""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True)
    
    write_json(reports_dir / "pool_court_verdict_v1.json", {"verdict": "IMPROVE"})
    write_json(reports_dir / "pool_execution_summary_v1.json", {"plan": []})
    write_json(reports_dir / "pool_replacement_plan_v1.json", {
        "replacement_verdict": "SUGGESTED",
        "close_plan": {"pos_id": "pos1", "symbol": "WEAK"},
        "open_plan": {"symbol": "STRONG", "timeframe": "1h", "bundle_id": "b3", "notional": 200}
    })
    
    report = build_pool_order_intents_v1(reports_dir, "war", "run_3", {})
    
    assert report.intents_close == 1
    assert report.intents_open == 1
    assert report.intents_total == 2
    
    close_intent = [i for i in report.intents if i.action == "CLOSE_POSITION"][0]
    assert close_intent.reason == "REPLACEMENT_CLOSE"
    
    open_intent = [i for i in report.intents if i.action == "OPEN_POSITION"][0]
    assert open_intent.reason == "REPLACEMENT_OPEN"

def test_deterministic_order_keys(tmp_path):
    """Same input -> same order_key/intent_id."""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True)
    
    write_json(reports_dir / "pool_court_verdict_v1.json", {"verdict": "PASS"})
    write_json(reports_dir / "pool_execution_summary_v1.json", {
        "plan": [{"action": "PLACE_ORDER", "symbol": "BTC", "timeframe": "1h", "bundle_id": "b1", "notional": 100}]
    })
    
    report1 = build_pool_order_intents_v1(reports_dir, "war", "run_det", {})
    report2 = build_pool_order_intents_v1(reports_dir, "war", "run_det", {})
    
    assert report1.intents[0].order_key == report2.intents[0].order_key
    assert report1.intents[0].intent_id == report2.intents[0].intent_id

def test_sim_executor_writes_result(tmp_path):
    """SIM executor writes result file."""
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True)
    
    write_json(reports_dir / "pool_court_verdict_v1.json", {"verdict": "PASS"})
    write_json(reports_dir / "pool_execution_summary_v1.json", {
        "plan": [
            {"action": "PLACE_ORDER", "symbol": "BTC", "timeframe": "1h", "bundle_id": "b1", "notional": 100}
        ]
    })
    
    result = run_pool_execution_sim_v0("war", "run_sim", {}, reports_dir)
    
    assert result["status"] == "OK"
    assert result["intents_total"] == 1
    
    sim_result_path = reports_dir / "pool_execution_sim_result_v0.json"
    assert sim_result_path.exists()
    
    with open(sim_result_path) as f:
        sim_data = json.load(f)
    
    assert sim_data["planned"] == 1
    assert sim_data["executed_sim"] == 1
    assert sim_data["failed_sim"] == 0
