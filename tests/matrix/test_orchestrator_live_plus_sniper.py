import os
import json
import time
import pytest
from tezaver.matrix.core.orchestrator import enqueue_job, run_ticks, OrchestratorStore
from tezaver.matrix.core.live_engine import start_live_run, save_live_state
from tezaver.matrix.core.trace import TraceIds
from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig

def test_orchestrator_live_plus_sniper(tmp_path):
    home = str(tmp_path)
    os.environ["TEZAVER_MATRIX_HOME"] = home
    
    # 1. Setup Data for Sniper
    c_store = tmp_path / "candidates" # Not used by FileCandidateStore default? 
    # FileCandidateStore uses {home}/candidates
    c_dir = tmp_path / "candidates"
    os.makedirs(c_dir)
    
    with open(c_dir / "SNIPER_CAND.json", "w") as f:
        json.dump({
            "symbol": "BTC", "timeframe": "1m", "build_ts": "2024",
            "story": {} 
        }, f)
        
    bars_path = tmp_path / "bars.json"
    # Create valid bars
    # run_cycle needs at least 1 closed bar
    bars_data = [{"ts": 1000, "open":10, "high":12, "low":9, "close":11, "volume":100, "closed": True}]
    with open(bars_path, "w") as f: json.dump(bars_data, f)
    
    # 2. Setup Live Run
    dr_dir = tmp_path / "data_reports"
    os.makedirs(dr_dir)
    with open(dr_dir / "latest.json", "w") as f:
        json.dump({"ok": True, "ts": 1234567890}, f)
        
    runs_dir = tmp_path / "runs"
    os.makedirs(runs_dir)
    
    # Manually start live run to get ID
    # Use helper or direct call? Direct call to start_live_run requires many args.
    # Let's mock the run dir and meta.
    
    run_id = "run_BTC_1m_LIVE_12345"
    run_dir = runs_dir / run_id
    os.makedirs(run_dir)
    
    meta = {
        "run_id": run_id, 
        "run_profile": "LIVE",
        "candidate": {"symbol": "BTC", "timeframe": "1m", "build_ts": "2024"},
        "trace": {"data_fingerprint": "test", "engine_version": "v4", "config_signature": "test"},
        "config": {"risk": {}, "gov": {}}
    }
    with open(run_dir / "meta.json", "w") as f: json.dump(meta, f)
    
    # Init state
    save_live_state(home, run_id, {
        "cursor": 0, "last_bar_ts": 0, "timeframe": "1m", "tf_ms": 60000, "bars_fingerprint": "test"
    })
    
    # 3. Enqueue Jobs
    # Live Step (High Priority)
    j1 = enqueue_job(home, "LIVE_STEP", {"run_id": run_id, "bars_path": str(bars_path), "steps": 1}, priority=100)
    
    # Sniper (Lower Priority)
    j2 = enqueue_job(home, "SNIPER", {"candidate_id": "SNIPER_CAND", "bars_path": str(bars_path)}, priority=50)
    
    # 4. Run Ticks
    res = run_ticks(home, ticks=2)
    
    # 5. Verify
    assert len(res["executed"]) == 2
    executed_ids = res["executed"]
    
    store = OrchestratorStore(home)
    hist = store.load_history()
    
    # J1 should be first (higher prio) or J2? 
    # J1 prio 100, J2 prio 50. J1 should run first.
    # Note: run_ticks processes one by one. order: J1 then J2.
    # executed list appends. so executed[0] is J1.
    
    assert executed_ids[0] == j1
    assert executed_ids[1] == j2
    
    # Verify Live State updated
    with open(run_dir / "live_state.json") as f:
        state = json.load(f)
        assert state["cursor"] == 1
        
    # Verify Sniper Artifacts
    for h in hist:
        if h["type"] == "SNIPER":
            assert h["status"] == "DONE"
            res = h["result"]
            assert res["verdict"] in ["PASS", "IMPROVE", "FAIL"]
            
