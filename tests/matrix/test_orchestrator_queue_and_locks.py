import os
import json
import time
from tezaver.matrix.core.orchestrator import OrchestratorStore, enqueue_job, run_ticks, acquire_locks

def test_orchestrator_locks(tmp_path):
    home = str(tmp_path)
    # 1. Enqueue 2 jobs for same resource
    # Mock LIVE_STEP usually locks "run:ID"
    
    jid1 = enqueue_job(home, "LIVE_STEP", {"run_id": "R1", "steps": 1})
    jid2 = enqueue_job(home, "LIVE_STEP", {"run_id": "R1", "steps": 1})
    
    # 2. Manually lock R1 for J1
    acquire_locks(home, ["run:R1"], jid1)
    
    # 3. Try to lock R1 for J2 -> Should fail
    success = acquire_locks(home, ["run:R1"], jid2)
    assert not success
    
def test_orchestrator_scheduler(tmp_path):
    home = str(tmp_path)
    
    # Setup for SNIPER job needs candidate & bars
    c_dir = tmp_path / "candidates"
    os.makedirs(c_dir)
    with open(c_dir / "BTC_1m.json", "w") as f:
        json.dump({
            "symbol": "BTC", "timeframe": "1m", "build_ts": "2024",
            "story": {} 
        }, f)
        
    bars_path = tmp_path / "bars.json"
    with open(bars_path, "w") as f:
        json.dump([], f) 
        
    # Enqueue Dummy Jobs that might fail but prove scheduler picked them
    # Use SNIPER but with valid paths so it runs partially
    
    # Actually simplest is to ensure job executed and moved to history.
    # Even if it fails.
    
    jid = enqueue_job(home, "SNIPER", {"candidate_id": "BTC_1m", "bars_path": str(bars_path)}, priority=100)
    
    res = run_ticks(home, ticks=1)
    assert len(res["executed"]) == 1
    assert res["executed"][0] == jid
    
    store = OrchestratorStore(home)
    queue = store.load_queue()
    history = store.load_history()
    
    assert len(queue) == 0
    assert len(history) == 1
    assert history[0]["job_id"] == jid
    # Result might be FAIL because of validation inside run_sniper, but scheduler worked
