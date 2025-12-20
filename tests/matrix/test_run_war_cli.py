import os
import json
import subprocess
import sys
import shutil

def test_run_war_cli(tmp_path):
    home = tmp_path
    c_dir = home / "candidates"
    b_dir = home / "bars"
    os.makedirs(c_dir)
    os.makedirs(b_dir)
    
    # 1. Setup Candidates
    # C1: valid
    c1 = {
        "symbol": "BTC", "timeframe": "1h", "bundle_version": "v1", "build_ts": "2024-01-01T00:00:00",
        "story": {
            "phases": [{"name": "P1", "start_bar": 0, "end_bar": 10}],
            "anchors": {"entry_bar": 1, "invalidation_bar": 5},
            "tags": {"overview": "test"}
        }
    }
    with open(c_dir / "BTC_1h.json", "w") as f: json.dump(c1, f)
    
    # C2: valid different
    c2 = {
        "symbol": "ETH", "timeframe": "4h", "bundle_version": "v1", "build_ts": "2024-01-01T00:00:00",
        "story": {
            "phases": [{"name": "P1", "start_bar": 0, "end_bar": 10}],
            "anchors": {"entry_bar": 1, "invalidation_bar": 5},
            "tags": {"overview": "test"}
        }
    }
    with open(c_dir / "ETH_4h.json", "w") as f: json.dump(c2, f)
    
    # 2. Setup Bars
    # BTC_1h.json (exact match)
    bars_btc = [{"ts": 1000, "open":10, "high":12, "low":9, "close":11, "volume":100, "closed": True}]
    with open(b_dir / "BTC_1h.json", "w") as f: json.dump(bars_btc, f)
    
    # ETH.json (symbol match fallback)
    bars_eth = [{"ts": 1000, "open":10, "high":12, "low":9, "close":11, "volume":100, "closed": True}]
    with open(b_dir / "ETH.json", "w") as f: json.dump(bars_eth, f)
    
    # Fake Judge Requirement (Data report)
    drep = home / "data_reports"
    os.makedirs(drep)
    with open(drep / "latest.json", "w") as f: json.dump({"ok": True}, f)
    
    # 3. Run CLI
    cmd = [
        sys.executable, "-m", "tezaver.matrix.apps.run_war",
        "--candidates-dir", str(c_dir),
        "--bars-dir", str(b_dir),
        "--home", str(home)
    ]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    print(proc.stdout)
    print(proc.stderr)
    
    # Debug index
    s_dir = home / "war_sessions"
    if s_dir.exists():
        sessions = list(s_dir.iterdir())
        if sessions:
            idx = sessions[0] / "index.json"
            if idx.exists():
                with open(idx) as f:
                    print("INDEX:", f.read())

    assert proc.returncode == 0
    
    # 4. Verify
    s_dir = home / "war_sessions"
    assert s_dir.exists()
    sessions = list(s_dir.iterdir())
    assert len(sessions) == 1
    
    idx_path = sessions[0] / "index.json"
    assert idx_path.exists()
    
    with open(idx_path) as f:
        rows = json.load(f)
        
    assert len(rows) == 2
    
    # Check C1
    r1 = next(r for r in rows if r["symbol"] == "BTC")
    assert r1["verdict"] in ("PASS", "IMPROVE", "FAIL")
    assert "bars_path" in r1
    
    # Check Meta Profile
    runs_dir = home / "runs"
    rid = r1["run_id"]
    with open(runs_dir / rid / "meta.json") as f:
        meta = json.load(f)
        assert meta["run_profile"] == "WAR"
