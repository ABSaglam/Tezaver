import pytest
import zipfile
import json
from pathlib import Path
from tezaver.matrix.evidence.proof_bundle import build_proof_bundle

def test_build_proof_bundle(tmp_path):
    # Setup dummy run dir
    run_dir = tmp_path / "run_123"
    run_dir.mkdir()
    
    # Dummy files
    (run_dir / "telemetry.ndjson").write_text("event1\nevent2")
    (run_dir / "report.json").write_text("{}")
    
    reports_dir = run_dir / "reports"
    reports_dir.mkdir()
    (reports_dir / "data_report_v1.json").write_text("{}")
    
    # Mock relative path requirement for metadata
    # We adjust the function logic or just mock the return path
    # In test, we just check if files are in ZIP
    
    # We need to monkeypatch relative_to if we want exact metadata match
    # but for functional test, let's just run it:
    
    # Functional check
    # Note: build_proof_bundle expects run_dir to have a certain parent structure for the relative path
    # Let's adjust mock structure
    root = tmp_path / "out" / "matrix_runs" / "war"
    root.mkdir(parents=True)
    real_run_dir = root / "run_test"
    real_run_dir.mkdir()
    (real_run_dir / "telemetry.ndjson").write_text("t")
    (real_run_dir / "reports").mkdir()
    (real_run_dir / "reports" / "r.json").write_text("r")
    
    meta = build_proof_bundle(real_run_dir)
    
    assert meta["artifact_count"] >= 2
    
    zip_path = real_run_dir / "proof_bundle" / "proof_bundle_v1.zip"
    assert zip_path.exists()
    
    with zipfile.ZipFile(zip_path, 'r') as z:
        names = z.namelist()
        assert "telemetry.ndjson" in names
        assert "reports/r.json" in names
        
    # Metadata file check
    meta_file = real_run_dir / "proof_bundle" / "bundle_metadata_v1.json"
    assert meta_file.exists()
    with open(meta_file) as f:
        data = json.load(f)
        assert data["run_id"] == "run_test"
