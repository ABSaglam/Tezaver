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
    
    # MX-9350: Setup minimal gate proofs for ACTIVE status
    # Release gate requires: SNIPER PASS, WAR PASS, LIVE APPROVED
    
    # Sniper run
    sniper_dir = tmp_path / "out" / "matrix_runs" / "sniper" / "run_C2_sn"
    os.makedirs(sniper_dir, exist_ok=True)
    with open(sniper_dir / "meta.json", "w") as f:
        json.dump({"run_profile": "SNIPER", "candidate": {"candidate_id": "C2"}}, f)
    with open(sniper_dir / "judge.json", "w") as f:
        json.dump({"overall": "PASS"}, f)
    
    # War run
    war_dir = tmp_path / "out" / "matrix_runs" / "war" / "run_C2_war"
    os.makedirs(war_dir, exist_ok=True)
    with open(war_dir / "meta.json", "w") as f:
        json.dump({"run_profile": "WAR", "candidate": {"candidate_id": "C2"}}, f)
    with open(war_dir / "judge.json", "w") as f:
        json.dump({"overall": "PASS"}, f)
    
    # Live run + APPROVED stage
    live_dir = tmp_path / "out" / "matrix_runs" / "live" / "run_C2_live"
    os.makedirs(live_dir, exist_ok=True)
    with open(live_dir / "meta.json", "w") as f:
        json.dump({"run_profile": "LIVE", "candidate": {"candidate_id": "C2"}}, f)
    with open(live_dir / "judge.json", "w") as f:
        json.dump({"overall": "PASS"}, f)
    
    # APPROVED stage file
    stage_dir = tmp_path / "candidates_stage"
    os.makedirs(stage_dir, exist_ok=True)
    with open(stage_dir / "C2.json", "w") as f:
        json.dump({"stage": "APPROVED"}, f)
    
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
