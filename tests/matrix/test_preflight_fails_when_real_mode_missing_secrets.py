import os
import json
import pytest
from tezaver.matrix.core.preflight import run_preflight
from tezaver.matrix.core.broker_config import save_broker_config

def test_preflight_fails_when_real_mode_missing_secrets(tmp_path):
    home = str(tmp_path)
    os.makedirs(tmp_path / "ops", exist_ok=True)
    with open(tmp_path / "ops" / "meta.json", "w") as f: f.write("{}")
    
    # Helper to find check status
    def get_status(pf_res, name):
        for c in pf_res["checks"]:
            if c["name"] == name:
                return c["status"]
        return "NOT_FOUND"

    # 1. PAPER Mode -> OK (Secrets Skipped)
    save_broker_config(home, {"mode": "PAPER"})
    pf = run_preflight(home)
    assert pf["ok"]
    assert get_status(pf, "SECRETS_CHECK") == "PASS"
    
    # 2. REAL_BINANCE_STUB -> Fail without secrets
    save_broker_config(home, {"mode": "REAL_BINANCE_STUB"})
    pf = run_preflight(home)
    assert not pf["ok"]
    assert get_status(pf, "SECRETS_CHECK") == "FAIL"
    
    # 3. Secrets Present -> OK
    os.makedirs(tmp_path / "secrets", exist_ok=True)
    with open(tmp_path / "secrets" / "binance.json", "w") as f:
        json.dump({"api_key": "k", "api_secret": "s"}, f)
        
    pf = run_preflight(home)
    assert pf["ok"]
    assert get_status(pf, "SECRETS_CHECK") == "PASS"
