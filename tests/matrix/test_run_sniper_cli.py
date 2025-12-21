import os
import json
import subprocess
import sys
import pytest

@pytest.mark.core
def test_run_sniper_cli(tmp_path):
    home = tmp_path
    
    # 1. Create Candidate
    c_dir = home / "candidates"
    os.makedirs(c_dir)
    cid = "BTC_1h_v1_2024"
    with open(c_dir / f"{cid}.json", "w") as f:
        json.dump({
            "symbol": "BTC", "timeframe": "1h", "bundle_version": "v1", "build_ts": "2024-01-01T00:00:00",
            "story": {}
        }, f)
        
    # 2. Create Bars
    bars_path = home / "bars.json"
    with open(bars_path, "w") as f:
        json.dump([
            {"ts": 1000, "open":10, "high":12, "low":9, "close":11, "volume":100, "closed": True},
            {"ts": 2000, "open":11, "high":13, "low":10, "close":12, "volume":100, "closed": True}
        ], f)
        
    # 3. Create Data Report (for Judge PASS)
    drep = home / "data_reports"
    os.makedirs(drep)
    with open(drep / "latest.json", "w") as f:
        json.dump({"ok": True}, f)

    # 4. Run CLI
    cmd = [
        sys.executable, "-m", "tezaver.matrix.apps.run_sniper",
        "--candidate-id", cid,
        "--bars", str(bars_path),
        "--home", str(home)
    ]
    
    # We need PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    print(proc.stdout)
    print(proc.stderr)
    
    # Locate run for debug/assertion
    runs_dir = home / "runs"
    runs = list(runs_dir.iterdir()) if runs_dir.exists() else []
    
    # Debug on failure
    if proc.returncode != 0 and runs:
        rid = runs[0].name
        if (runs_dir / rid / "judge.json").exists():
            with open(runs_dir / rid / "judge.json") as f:
                print("JUDGE:", f.read())
        if (runs_dir / rid / "scorecard.json").exists():
            with open(runs_dir / rid / "scorecard.json") as f:
                print("SCORECARD:", f.read())
        if (runs_dir / rid / "events.ndjson").exists():
            print("EVENTS:")
            with open(runs_dir / rid / "events.ndjson") as f:
                for line in f: print(line.strip())

    assert proc.returncode == 0 # PASS
    assert "Verdict: PASS" in proc.stdout
    
    # Verify Run Artifacts
    assert len(runs) == 1
    
    # Verify Metadata Profile
    rid = runs[0].name
    with open(runs_dir / rid / "meta.json") as f:
        meta = json.load(f)
        assert meta["run_profile"] == "SNIPER"
