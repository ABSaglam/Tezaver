import os
import json
import pytest
from tezaver.matrix.core.cloud_import import import_export_package
from tezaver.matrix.core.checksums import sha256_file, write_json

def test_cloud_import_success(tmp_path):
    home = str(tmp_path)
    
    # 1. Create fake export package
    exp_dir = tmp_path / "exports" / "EXPORT_C1_100"
    os.makedirs(exp_dir)
    
    # Files
    cand_content = {"symbol": "BTC", "timeframe": "1m"}
    write_json(str(exp_dir / "candidate.json"), cand_content)
    
    os.makedirs(exp_dir / "proofs")
    write_json(str(exp_dir / "proofs" / "judge.json"), {"verdict": "PASS"})
    
    # Manifest
    files = ["candidate.json", "proofs/judge.json"]
    sha_map = {
        "candidate.json": sha256_file(str(exp_dir / "candidate.json")),
        "proofs/judge.json": sha256_file(str(exp_dir / "proofs" / "judge.json"))
    }
    
    manifest = {
        "version": "export_v1",
        "candidate_id": "C1",
        "symbol": "BTC",
        "timeframe": "1m",
        "files": files,
        "sha256": sha_map
    }
    write_json(str(exp_dir / "export_manifest.json"), manifest)
    
    # 2. Import
    res = import_export_package(home, str(exp_dir), activate=False)
    
    # 3. Verify
    assert res["status"] == "PAUSED"
    assert res["strategy_id"].startswith("STRAT_C1_")
    
    target = res["target_path"]
    assert os.path.exists(os.path.join(target, "status.json"))
    assert os.path.exists(os.path.join(target, "strategy.json"))
    assert os.path.exists(os.path.join(target, "files", "candidate.json"))
    
    # Check activation
    res2 = import_export_package(home, str(exp_dir), activate=True)
    assert res2["status"] == "ACTIVE"
    # Idempotency check: should reuse dir, update status
    assert res2["strategy_id"] == res["strategy_id"]
    with open(os.path.join(target, "status.json")) as f:
        st = json.load(f)
        assert st["status"] == "ACTIVE"
