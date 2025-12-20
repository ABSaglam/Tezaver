import os
import json
import pytest
from tezaver.matrix.core.migration_engine import plan_migration, execute_migration

def test_migration_idempotent(tmp_path):
    home = str(tmp_path)
    
    # C1
    d = tmp_path / "approved" / "C1"
    os.makedirs(d, exist_ok=True)
    with open(d / "manifest.json", "w") as f:
        json.dump({"candidate_id": "C1", "symbol": "S", "timeframe": "T"}, f)
        
    policy = {"mode": "PROMOTE_ALL", "activate": False}
    
    # Run 1
    plan1 = plan_migration(home, policy)
    rep1 = execute_migration(home, plan1)
    assert rep1["ok"] == 1
    
    # Run 2
    plan2 = plan_migration(home, policy)
    rep2 = execute_migration(home, plan2)
    
    assert rep2["total"] == 1
    assert rep2["ok"] == 0
    assert rep2["skipped"] == 1
    assert rep2["results"][0]["status"] == "SKIPPED"
