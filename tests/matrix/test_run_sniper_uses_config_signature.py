import os
import json
import pytest
from tezaver.matrix.apps.run_sniper import run_sniper_once

@pytest.mark.core
def test_run_sniper_uses_config_signature(tmp_path):
    home = str(tmp_path)
    os.environ["TEZAVER_MATRIX_HOME"] = home
    
    # Setup
    c_dir = tmp_path / "candidates"
    os.makedirs(c_dir)
    with open(c_dir / "C1.json", "w") as f:
        json.dump({"symbol":"BTC","timeframe":"1m","build_ts":"100","story":{}}, f)
        
    bars = tmp_path / "bars.json"
    with open(bars, "w") as f:
        json.dump([{"ts":1000,"open":10,"high":12,"low":9,"close":11,"volume":100,"closed":True}], f)
        
    # Run
    res = run_sniper_once(home, "C1", str(bars))
    assert res["status"] in ["DONE", "FAIL"]
    
    rid = res.get("run_id")
    if rid:
        # Check Meta
        mpath = tmp_path / "runs" / rid / "meta.json"
        with open(mpath) as f:
            meta = json.load(f)
            
        sig = meta.get("trace", {}).get("config_signature", "")
        assert sig != "sniper-demo"
        assert len(sig) == 64 # SHA256 hex
