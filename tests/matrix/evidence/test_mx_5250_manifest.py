import pytest
import json
from pathlib import Path
from tezaver.matrix.evidence.evidence_manifest import generate_manifest, sha256_file

def test_manifest_hashing(tmp_path):
    run_dir = tmp_path / "run_1"
    run_dir.mkdir()
    reports_dir = run_dir / "reports"
    reports_dir.mkdir()
    
    # Create fake artifacts
    file1 = run_dir / "report.json"
    file1.write_text('{"ok": true}')
    
    file2 = reports_dir / "data_integrity_v1.json"
    file2.write_text('{"status": "PASS"}')
    
    build_info = {
        "run_id": "run_1",
        "config_signature": "sig_1"
    }
    
    manifest = generate_manifest(run_dir, "war", build_info)
    
    assert manifest["run_id"] == "run_1"
    assert len(manifest["artifacts"]) == 2
    assert any(a["rel_path"] == "report.json" for a in manifest["artifacts"])
    assert any(a["rel_path"] == "reports/data_integrity_v1.json" for a in manifest["artifacts"])
    assert "manifest_sha256" in manifest

def test_manifest_chaining(tmp_path):
    # Setup runs_root
    runs_root = tmp_path / "war"
    runs_root.mkdir()
    
    # Run 1
    run1_dir = runs_root / "run1"
    run1_dir.mkdir()
    (run1_dir / "reports").mkdir()
    (run1_dir / "report.json").write_text("data1")
    
    man1 = generate_manifest(run1_dir, "war", {"run_id": "run1"})
    hash1 = man1["manifest_sha256"]
    
    # Run 2
    run2_dir = runs_root / "run2"
    run2_dir.mkdir()
    (run2_dir / "reports").mkdir()
    (run2_dir / "report.json").write_text("data2")
    
    # We need to ensure run1 is older
    import os
    import time
    os.utime(run1_dir, (time.time() - 100, time.time() - 100))
    
    man2 = generate_manifest(run2_dir, "war", {"run_id": "run2"})
    
    assert man2["prev_manifest_sha256"] == hash1
