import pytest
import subprocess
import sys
import json
import os

def test_importer_cli(tmp_path):
    # 1. Create a dummy candidate file
    candidate_data = {
        "symbol": "SOL",
        "timeframe": "4h",
        "bundle_version": "v1",
        "build_ts": "2025-02-01T09:00:00",
        "story": {
            "phases": [{"name": "RALLY", "start_bar": 100, "end_bar": 200}],
            "anchors": {"entry_bar": 190, "invalidation_bar": 90}
        }
    }
    
    src_file = tmp_path / "candidate.json"
    with open(src_file, "w") as f:
        json.dump(candidate_data, f)
        
    home_dir = tmp_path / "matrix_home"
    
    cmd = [
        sys.executable, "-m", "tezaver.matrix.apps.candidate_importer",
        "--path", str(src_file),
        "--home", str(home_dir)
    ]
    
    # Run with current environment but ensure PYTHONPATH is set if needed
    env = os.environ.copy()
    if 'PYTHONPATH' not in env:
        # Assuming we run from repo root in tests usually
        env['PYTHONPATH'] = os.getcwd() + "/src"
        
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    assert result.returncode == 0
    assert "Imported: 1" in result.stdout
    
    # Verify file exists in store
    candidates_dir = home_dir / "candidates"
    files = list(candidates_dir.glob("*.json"))
    assert len(files) == 1
