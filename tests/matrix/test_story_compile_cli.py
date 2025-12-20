import os
import json
import subprocess
import sys

def test_story_compile_cli(tmp_path):
    candidates_dir = tmp_path / "candidates"
    os.makedirs(candidates_dir)
    
    # Create source
    src_id = "BTC_15m_v1_2024"
    src_path = candidates_dir / f"{src_id}.json"
    source = {
        "symbol": "BTC", "timeframe": "15m", "build_ts": "2024", "bundle_version": "v1",
        "story": {
            "phases": [{"name": "P1", "start_bar": 0, "end_bar": 60}],
            "anchors": {"entry_bar": 60, "invalidation_bar": 0}
        }
    }
    with open(src_path, "w") as f:
        json.dump(source, f)
        
    # Run CLI
    cmd = [
        sys.executable, "-m", "tezaver.matrix.apps.story_compile",
        "--candidate-id", src_id,
        "--target", "both",
        "--home", str(tmp_path)
    ]
    
    proc = subprocess.run(cmd, capture_output=True, text=True, env={"PYTHONPATH": os.getcwd() + "/src"})
    
    assert proc.returncode == 0
    assert "Compiled 1h" in proc.stdout
    assert "Compiled 4h" in proc.stdout
    
    # Verify files exist
    assert any("BTC_1h_" in f for f in os.listdir(candidates_dir))
    assert any("BTC_4h_" in f for f in os.listdir(candidates_dir))
