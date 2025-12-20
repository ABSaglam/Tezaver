from tezaver.matrix.core.approval import apply_run_result, get_candidate_stage
from tezaver.matrix.core.judge import GateVerdict

def test_approval_advance(tmp_path):
    home = str(tmp_path)
    cid = "C1"
    
    # Initial
    s = get_candidate_stage(home, cid)
    assert s["stage"] == "NEW"
    
    # Run 1: PASS -> SNIPER
    judge = {"overall": "PASS"}
    res = apply_run_result(home, "run1", judge, cid)
    assert res["stage"] == "SNIPER"
    
    # Run 2: FAIL -> Blocked, no advance
    judge_fail = {"overall": "FAIL"}
    res = apply_run_result(home, "run2", judge_fail, cid)
    assert res["stage"] == "SNIPER"
    assert res["flags"]["blocked"] is True
    
    # Run 3: PASS -> WAR (unblocks?)
    # Logic: blocked set to False on PASS
    res = apply_run_result(home, "run3", judge, cid)
    assert res["stage"] == "WAR"
    assert res["flags"]["blocked"] is False
