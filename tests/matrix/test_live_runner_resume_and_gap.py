import os
import json
import subprocess
import sys

def test_live_runner_resume_and_gap(tmp_path):
    home = tmp_path
    c_dir = home / "candidates"
    os.makedirs(c_dir)
    
    # 1. Setup Candidate
    cid = "BTC_1m"
    c1 = {
        "symbol": "BTC", "timeframe": "1m", "bundle_version": "v1", "build_ts": "2024-01-01T00:00:00",
        "story": {
            "phases": [{"name": "P1", "start_bar": 0, "end_bar": 10}],
            "anchors": {"entry_bar": 1, "invalidation_bar": 5},
            "tags": {"overview": "test"}
        }
    }
    with open(c_dir / f"{cid}.json", "w") as f: json.dump(c1, f)
    
    # 2. Setup Bars (With GAP)
    # 1m = 60000ms
    # Bar 0: 1700000000000
    # Bar 1: 1700000060000 (1m)
    # Bar 2: 1700000300000 (Gap! diff 240000 > 66000)
    bars_data = [
        {"ts": 1700000000000, "open":10, "high":12, "low":9, "close":11, "volume":100, "closed": True},
        {"ts": 1700000060000, "open":11, "high":13, "low":10, "close":12, "volume":100, "closed": True},
        {"ts": 1700000300000, "open":12, "high":14, "low":11, "close":13, "volume":100, "closed": True}
    ]
    bars_path = home / "bars.json"
    with open(bars_path, "w") as f: json.dump(bars_data, f)
    
    # 2b. Setup Data Report (for Judge PASS)
    dr_dir = home / "data_reports"
    os.makedirs(dr_dir)
    with open(dr_dir / "latest.json", "w") as f:
        json.dump({"ok": True, "ts": 1234567890}, f)
    
    # 3. First Run: Steps=2 (Process Bar 0, 1)
    cmd = [
        sys.executable, "-m", "tezaver.matrix.apps.run_live",
        "--candidate-id", cid,
        "--bars", str(bars_path),
        "--steps", "2",
        "--home", str(home)
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    print("RUN 1 STDOUT:", proc.stdout)
    print("RUN 1 STDERR:", proc.stderr)
    assert proc.returncode == 0
    
    # Extract Run ID from output
    run_id = None
    for line in proc.stdout.splitlines():
        if "Run ID: " in line:
            run_id = line.split("Run ID: ")[1].strip()
            break
    assert run_id
    
    # Verify State
    ls_path = home / "runs" / run_id / "live_state.json"
    assert ls_path.exists()
    with open(ls_path) as f:
        state = json.load(f)
        assert state["cursor"] == 2
        assert state["last_bar_ts"] == 1700000060000
        
    # 4. Resume Run: Steps=1 (Process Bar 2 -> GAP)
    # Using --run-id
    cmd2 = [
        sys.executable, "-m", "tezaver.matrix.apps.run_live",
        "--candidate-id", cid,
        "--bars", str(bars_path),
        "--steps", "1",
        "--home", str(home),
        "--run-id", run_id
    ]
    
    proc2 = subprocess.run(cmd2, env=env, capture_output=True, text=True)
    print("RUN 2 STDOUT:", proc2.stdout)
    assert proc2.returncode == 0
    assert f"Resuming Run: {run_id}" in proc2.stdout
    
    # Verify Gap Event
    events_path = home / "runs" / run_id / "events.ndjson"
    events = []
    with open(events_path) as f:
        for line in f: events.append(json.loads(line))
        
    gap_events = [e for e in events if e["event_type"] == "GAP_DETECTED"]
    assert len(gap_events) == 1
    p = gap_events[0]["payload"]
    assert p["prev_ts"] == 1700000060000
    assert p["next_ts"] == 1700000300000
    
    reconnects = [e for e in events if e["event_type"] == "RECONNECT"]
    assert len(reconnects) >= 1
    
    # Verify State Advanced
    with open(ls_path) as f:
        state = json.load(f)
        assert state["cursor"] == 3
        assert state["last_bar_ts"] == 1700000300000
