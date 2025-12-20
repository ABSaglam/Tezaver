import os
import json
import pytest
from tezaver.matrix.core.release_gate import evaluate_release_gate

def test_release_gate_pass(tmp_path):
    home = str(tmp_path)
    cid = "C_PASS"
    
    # RG-01: Sniper
    rdir = tmp_path / "runs" / "R_SNIPER"
    os.makedirs(rdir, exist_ok=True)
    with open(rdir / "meta.json", "w") as f:
        json.dump({"run_profile": "SNIPER", "candidate": {"candidate_id": cid}}, f)
    with open(rdir / "judge.json", "w") as f:
        json.dump({"overall": "PASS"}, f)
        
    # RG-02: War
    wdir = tmp_path / "war_sessions" / "S_WAR"
    os.makedirs(wdir, exist_ok=True)
    with open(wdir / "report.json", "w") as f:
        json.dump({"results": [{"candidate_id": cid, "verdict": "PASS"}]}, f)
        
    # RG-03: Live & Approved
    rdir2 = tmp_path / "runs" / "R_LIVE"
    os.makedirs(rdir2, exist_ok=True)
    with open(rdir2 / "meta.json", "w") as f:
        json.dump({"run_profile": "LIVE", "candidate": {"candidate_id": cid}}, f)
    with open(rdir2 / "judge.json", "w") as f:
        json.dump({"overall": "PASS"}, f)
        
    st_dir = tmp_path / "candidates_stage"
    os.makedirs(st_dir, exist_ok=True)
    with open(st_dir / f"{cid}.json", "w") as f:
        json.dump({"stage": "APPROVED"}, f)
        
    # RG-04: Approved Pool
    ad = tmp_path / "approved" / cid
    os.makedirs(ad, exist_ok=True)
    with open(ad / "manifest.json", "w") as f: f.write("{}")
    
    # RG-05: Export
    ed = tmp_path / "exports" / f"EXPORT_{cid}_123"
    os.makedirs(ed, exist_ok=True)
    
    # RG-06: Checksums (Create dummy file and manifest)
    dummy = ed / "dummy.txt"
    dummy.write_text("ok")
    
    # Need correct sha
    sha = "TODO" 
    # Or just mock sha256_file?
    # Let's write invalid sha? No, we want PASS.
    # We rely on imported sha function?
    # Or we construct manifest with correct sha
    import hashlib
    h = hashlib.sha256(b"ok").hexdigest()
    
    with open(ed / "export_manifest.json", "w") as f:
        json.dump({"sha256": {"dummy.txt": h}}, f)
        
    # Evaluate
    res = evaluate_release_gate(home, cid)
    assert res["ok"] is True
    assert all(c["status"] == "PASS" for c in res["checks"])
