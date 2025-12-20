from tezaver.matrix.core.approval import apply_run_result, get_candidate_stage
from tezaver.matrix.core.judge import GateVerdict

def test_approval_advance(tmp_path):
    home = str(tmp_path)
    cid = "C1"
    
    # Initial
    s = get_candidate_stage(home, cid)
    assert s["stage"] == "NEW"
    
    # Run 1: PASS -> SNIPER -> WAR
    judge = {"overall": "PASS"}
    res = apply_run_result(home, "run1", judge, cid, run_profile="SNIPER")
    assert res["stage"] == "WAR"
    
    # Run 2: FAIL -> Blocked, no advance
    judge_fail = {"overall": "FAIL"}
    res = apply_run_result(home, "run2", judge_fail, cid, run_profile="WAR")
    assert res["stage"] == "WAR"
    assert res["flags"]["blocked"] is True
    
    # Run 3: PASS -> WAR -> LIVE
    # Logic: blocked set to False on PASS
    res = apply_run_result(home, "run3", judge, cid, run_profile="WAR")
    assert res["stage"] == "LIVE"
