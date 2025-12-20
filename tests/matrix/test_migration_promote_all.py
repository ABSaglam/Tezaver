import os
import json
import pytest
from tezaver.matrix.core.migration_engine import plan_migration, execute_migration
from tezaver.matrix.core.cloud_registry import list_strategies, read_strategy

def test_migration_promote_all(tmp_path):
    home = str(tmp_path)
    
    # 1. Setup Approved Candidates
    # C1
    c1_dir = tmp_path / "approved" / "C1"
    os.makedirs(c1_dir, exist_ok=True)
    with open(c1_dir / "manifest.json", "w") as f:
        json.dump({"candidate_id": "C1", "symbol": "BTC", "timeframe": "15m"}, f)
    # Proofs (needed for verification but export might skip details if missing)
    
    # C2
    c2_dir = tmp_path / "approved" / "C2"
    os.makedirs(c2_dir, exist_ok=True)
    with open(c2_dir / "manifest.json", "w") as f:
        json.dump({"candidate_id": "C2", "symbol": "ETH", "timeframe": "1h"}, f)
        
    # 2. Run Migration (Promote All, PAUSED)
    policy = {"mode": "PROMOTE_ALL", "activate": False}
    plan = plan_migration(home, policy)
    assert len(plan["items"]) == 2
    
    report = execute_migration(home, plan)
    
    assert report["total"] == 2
    assert report["ok"] == 2
    assert report["fail"] == 0
    
    # 3. Verify Cloud Registry
    sids = list_strategies(home)
    assert len(sids) == 2
    
    s1 = read_strategy(home, sids[0])
    s2 = read_strategy(home, sids[1])
    
    cids_in_reg = {s1["candidate_id"], s2["candidate_id"]}
    assert "C1" in cids_in_reg
    assert "C2" in cids_in_reg
    
    # Check Status PAUSED
    assert s1["status_info"]["status"] == "PAUSED"
