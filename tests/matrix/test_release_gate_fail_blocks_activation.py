import os
import json
import pytest
from tezaver.matrix.core.migration_engine import plan_migration, execute_migration

def test_release_gate_fail_blocks_activation(tmp_path):
    home = str(tmp_path)
    cid = "C_FAIL"
    
    # Only RG-04 (Approved Pool) exists
    ad = tmp_path / "approved" / cid
    os.makedirs(ad, exist_ok=True)
    with open(ad / "manifest.json", "w") as f:
         json.dump({"candidate_id": cid, "symbol": "S", "timeframe": "15m"}, f)
         
    # Policy: Activate=True
    policy = {"mode": "PROMOTE_ALL", "activate": True}
    
    plan = plan_migration(home, policy)
    report = execute_migration(home, plan)
    
    # Check Report
    res = report["results"][0]
    assert res["candidate_id"] == cid
    assert res["status"] == "OK" # It still imports!
    assert "gate_blocked" in res
    assert res["gate_blocked"] is True
    
    # Check Strategy Status
    from tezaver.matrix.core.cloud_registry import read_strategy
    s = read_strategy(home, res["strategy_id"])
    assert s["status_info"]["status"] == "PAUSED" # Blocked from being ACTIVE
    
    # Check Event Log
    ops_dir = tmp_path / "ops" / "migration" / "events.ndjson"
    with open(ops_dir) as f:
        logs = f.read()
        assert "MIGRATION_BLOCKED_BY_GATE" in logs
