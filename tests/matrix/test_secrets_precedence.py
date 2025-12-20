import os
import json
import pytest
from tezaver.matrix.core.secrets import load_binance_secrets

def test_secrets_precedence(tmp_path, monkeypatch):
    home = str(tmp_path)
    secrets_dir = tmp_path / "secrets"
    os.makedirs(secrets_dir)
    
    # 1. File only
    with open(secrets_dir / "binance.json", "w") as f:
        json.dump({"api_key": "FILE_KEY", "api_secret": "FILE_SEC"}, f)
        
    res = load_binance_secrets(home)
    assert res["present"]
    assert res["source"] == "FILE"
    assert res["api_key"] == "FILE_KEY"
    
    # 2. Env overrides File
    monkeypatch.setenv("TEZAVER_BINANCE_API_KEY", "ENV_KEY")
    monkeypatch.setenv("TEZAVER_BINANCE_API_SECRET", "ENV_SEC")
    
    res = load_binance_secrets(home)
    assert res["present"]
    assert res["source"] == "ENV"
    assert res["api_key"] == "ENV_KEY"
    
    # 3. None
    monkeypatch.delenv("TEZAVER_BINANCE_API_KEY")
    os.remove(secrets_dir / "binance.json")
    
    res = load_binance_secrets(home)
    assert not res["present"]
    assert res["source"] == "NONE"
