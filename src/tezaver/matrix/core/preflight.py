import os
import sys
import time
import json
from typing import Dict, List, Any

def run_preflight(home: str) -> Dict[str, Any]:
    home = home or os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix")
    if not os.path.exists(home):
        return {"ok": False, "ts": int(time.time()), "checks": [{"name": "HOME_EXISTS", "status": "FAIL", "detail": f"{home} not found"}], "warnings": []}
        
    checks = []
    warnings = []
    
    # Check 1: Home Writable
    try:
        test_file = os.path.join(home, ".write_test")
        with open(test_file, "w") as f: f.write("ok")
        os.remove(test_file)
        checks.append({"name": "HOME_WRITABLE", "status": "PASS", "detail": "Writable"})
    except Exception as e:
        checks.append({"name": "HOME_WRITABLE", "status": "FAIL", "detail": str(e)})
        
    # Check 2: Directories
    required_dirs = [
        "candidates", "runs", "incidents", "exports", 
        "approved", "orchestrator", "ops/preflight",
        "cloud_registry/strategies"
    ]
    
    for d in required_dirs:
        path = os.path.join(home, d)
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
                checks.append({"name": f"DIR_{d.upper()}", "status": "PASS", "detail": "Created"})
            except Exception as e:
                checks.append({"name": f"DIR_{d.upper()}", "status": "FAIL", "detail": str(e)})
        else:
            checks.append({"name": f"DIR_{d.upper()}", "status": "PASS", "detail": "Exists"})
            
    # Check 3: Typo Guard
    typo_path = os.path.join(home, "cloud_registry", "strateiges")
    if os.path.exists(typo_path):
        warnings.append("Found typo directory: cloud_registry/strateiges")
        
    # Check 4: Import Path Sanity
    try:
        import tezaver.matrix.apps.panel_server as p
        if "/src/tezaver/" not in p.__file__ and "site-packages" in p.__file__:
            warnings.append(f"Running from site-packages? {p.__file__}")
        checks.append({"name": "IMPORT_PATH", "status": "PASS", "detail": p.__file__})
    except ImportError:
        checks.append({"name": "IMPORT_PATH", "status": "FAIL", "detail": "Could not import tezaver"})
    except Exception as e:
        checks.append({"name": "IMPORT_PATH", "status": "FAIL", "detail": str(e)})
        
    # Consolidate
    failed = any(c["status"] == "FAIL" for c in checks)
    
    return {
        "ts": int(time.time()),
        "ok": not failed,
        "checks": checks,
        "warnings": warnings,
        "home": home
    }
