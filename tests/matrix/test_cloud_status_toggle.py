import os
import json
import pytest
from tezaver.matrix.core.cloud_registry import set_status, read_strategy
from tezaver.matrix.core.cloud_import import import_export_package
from tezaver.matrix.core.checksums import sha256_file, write_json

def test_cloud_status_toggle(tmp_path):
    home = str(tmp_path)
    # Setup Strategy via Import
    exp_dir = tmp_path / "exports" / "EXP1"
    os.makedirs(exp_dir)
    write_json(str(exp_dir / "c.json"), {})
    man = {
        "version": "export_v1", "candidate_id": "C1", "symbol": "BTC", "timeframe": "1m",
        "files": ["c.json"],
        "sha256": {"c.json": sha256_file(str(exp_dir / "c.json"))}
    }
    write_json(str(exp_dir / "export_manifest.json"), man)
    
    res = import_export_package(home, str(exp_dir), activate=False)
    sid = res["strategy_id"]
    
    # Verify initial
    s = read_strategy(home, sid)
    assert s["status_info"]["status"] == "PAUSED"
    
    # Toggle Active
    set_status(home, sid, "ACTIVE")
    s = read_strategy(home, sid)
    assert s["status_info"]["status"] == "ACTIVE"
    
    # Toggle Paused
    set_status(home, sid, "PAUSED")
    s = read_strategy(home, sid)
    assert s["status_info"]["status"] == "PAUSED"
