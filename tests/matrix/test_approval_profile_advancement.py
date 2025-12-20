from tezaver.matrix.core.approval import apply_run_result, get_candidate_stage

def test_approval_profile_flow(tmp_path):
    home = str(tmp_path)
    cid = "C1"
    
    # 1. NEW -> SNIPER Run (PASS) -> WAR
    judge = {"overall": "PASS"}
    res = apply_run_result(home, "run1", judge, cid, run_profile="SNIPER")
    assert res["stage"] == "WAR"
    
    # 2. WAR Run (PASS) -> LIVE
    res = apply_run_result(home, "run2", judge, cid, run_profile="WAR")
    assert res["stage"] == "LIVE"
    
    # 3. LIVE Run (PASS) -> APPROVED
    res = apply_run_result(home, "run3", judge, cid, run_profile="LIVE")
    assert res["stage"] == "APPROVED"
    
def test_approval_profile_mismatch(tmp_path):
    # If we run SNIPER on a WAR candidate, it shouldn't downgrade or upgrade?
    # Logic: SNIPER target is WAR. Current is WAR. Result WAR.
    home = str(tmp_path)
    cid = "C2"
    
    # Force set stage WAR
    apply_run_result(home, "run0", {"overall":"PASS"}, cid, "SNIPER")
    
    # Run SNIPER again
    res = apply_run_result(home, "run1", {"overall":"PASS"}, cid, "SNIPER")
    assert res["stage"] == "WAR" # Should stay WAR, not go to LIVE
