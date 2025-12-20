import os
import json
import pytest
from tezaver.matrix.core.migration_engine import plan_migration, execute_migration
from tezaver.matrix.core.cloud_registry import read_strategy, list_strategies

def test_migration_allowlist_activate(tmp_path):
    home = str(tmp_path)
    
    # C1, C2
    for c in ["C1", "C2"]:
        d = tmp_path / "approved" / c
        os.makedirs(d, exist_ok=True)
        with open(d / "manifest.json", "w") as f:
            json.dump({"candidate_id": c, "symbol": "S", "timeframe": "T"}, f)
            
    # Policy: Allowlist C2 only, Activate=True
    policy = {
        "mode": "PROMOTE_ALLOWLIST",
        "activate": True,
        "allowlist": ["C2"]
    }
    
    plan = plan_migration(home, policy)
    assert len(plan["items"]) == 1
    assert plan["items"][0]["candidate_id"] == "C2"
    
    report = execute_migration(home, plan)
    assert report["ok"] == 1
    
    # Verify
    sids = list_strategies(home)
    assert len(sids) == 1
    
    s = read_strategy(home, sids[0])
    assert s["candidate_id"] == "C2"
    assert s["status_info"]["status"] == "ACTIVE"
