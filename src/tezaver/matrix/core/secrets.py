import os
import json
from typing import Dict, Any, Optional

def load_binance_secrets(home: str) -> Dict[str, Any]:
    """
    Loads Binance secrets from ENV or File.
    Precedence: ENV > File.
    """
    secrets = {
        "present": False,
        "source": "NONE",
        "api_key": None,
        "api_secret": None,
        "testnet": False
    }

    # 1. Check ENV
    env_key = os.environ.get("TEZAVER_BINANCE_API_KEY")
    env_secret = os.environ.get("TEZAVER_BINANCE_API_SECRET")
    env_testnet = os.environ.get("TEZAVER_BINANCE_TESTNET", "false").lower() == "true"

    if env_key and env_secret:
        secrets["present"] = True
        secrets["source"] = "ENV"
        secrets["api_key"] = env_key
        secrets["api_secret"] = env_secret
        secrets["testnet"] = env_testnet
        return secrets

    # 2. Check File
    path = os.path.join(home, "secrets", "binance.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
                if data.get("api_key") and data.get("api_secret"):
                    secrets["present"] = True
                    secrets["source"] = "FILE"
                    secrets["api_key"] = data["api_key"]
                    secrets["api_secret"] = data["api_secret"]
                    secrets["testnet"] = data.get("testnet", False)
                    return secrets
        except:
            pass
            
    return secrets

def redact_secrets(secrets: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a safe summary of secrets.
    """
    return {
        "present": secrets["present"],
        "source": secrets["source"],
        "testnet": secrets["testnet"],
        # No api_key or secret here
    }
