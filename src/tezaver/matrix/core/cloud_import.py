import os
import json
import shutil
import time
import hashlib
from typing import Dict, List, Tuple
from tezaver.matrix.core.checksums import sha256_file, write_json

def read_export_manifest(export_path: str) -> Dict:
    man_path = os.path.join(export_path, "export_manifest.json")
    if not os.path.exists(man_path):
        raise FileNotFoundError("export_manifest.json not found")
    with open(man_path) as f:
        return json.load(f)

def verify_export_manifest(manifest: Dict) -> List[str]:
    errors = []
    if manifest.get("version") != "export_v1":
        errors.append(f"Unsupported version: {manifest.get('version')}")
    
    req_keys = ["candidate_id", "symbol", "timeframe", "files", "sha256"]
    for k in req_keys:
        if k not in manifest:
            errors.append(f"Missing key: {k}")
            
    return errors

def verify_checksums(export_path: str, manifest: Dict) -> List[str]:
    errors = []
    sha_map = manifest.get("sha256", {})
    files = manifest.get("files", [])
    
    for frel in files:
        fpath = os.path.join(export_path, frel)
        if not os.path.exists(fpath):
            errors.append(f"Missing file: {frel}")
            continue
            
        expected = sha_map.get(frel)
        if not expected:
            errors.append(f"No checksum for file: {frel}")
            continue
            
        actual = sha256_file(fpath)
        if actual != expected:
            errors.append(f"Checksum mismatch for {frel}: expected {expected[:8]}, got {actual[:8]}")
            
    return errors

def compute_strategy_id(candidate_id: str, export_sha: str) -> str:
    # Short hash of manifest content or similar to ensure uniqueness
    short = export_sha[:8]
    return f"STRAT_{candidate_id}_{short}"

def import_export_package(home: str, export_path: str, activate: bool = False) -> Dict:
    # 1. Validation
    manifest = read_export_manifest(export_path)
    
    errs = verify_export_manifest(manifest)
    if errs:
        raise ValueError(f"Manifest invalid: {errs}")
        
    errs = verify_checksums(export_path, manifest)
    if errs:
        raise ValueError(f"Checksum verification failed: {errs}")
        
    # 2. Strategy ID
    # Hash the manifest file itself as the 'fingerprint' of the export package
    man_path = os.path.join(export_path, "export_manifest.json")
    man_sha = sha256_file(man_path)
    
    strat_id = compute_strategy_id(manifest["candidate_id"], man_sha)
    
    # 3. Setup Target
    cloud_reg_dir = os.path.join(home, "cloud_registry")
    target_dir = os.path.join(cloud_reg_dir, "strategies", strat_id)
    
    if os.path.exists(target_dir):
        # Already imported? Check idempotency?
        # We can overwrite or raise. Let's overwrite for update logic, or idempotency.
        pass
    else:
        os.makedirs(target_dir, exist_ok=True)
        
    # 4. Copy Files
    # We copy everything into 'files/' subdir except export_manifest.json which goes to root of strategy?
    # Spec says:
    # strategies/<id>/
    #   strategy.json
    #   export_manifest.json
    #   files/ ...
    
    files_dir = os.path.join(target_dir, "files")
    os.makedirs(files_dir, exist_ok=True)
    
    shutil.copy2(man_path, os.path.join(target_dir, "export_manifest.json"))
    
    # Copy content files
    for frel in manifest["files"]:
        src = os.path.join(export_path, frel)
        dest = os.path.join(files_dir, frel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)
        
    # 5. Create Metadata
    status = "ACTIVE" if activate else "PAUSED"
    write_json(os.path.join(target_dir, "status.json"), {"status": status, "updated_ts": int(time.time())})
    
    # Proofs (extract paths from manifest files list for quick access?)
    # Assume standard names from Phase-9A
    # But files list is flat relative paths?
    # "proofs/last_live_run_judge.json" etc.
    
    proofs_map = {}
    for f in manifest["files"]:
        if "judge" in f: proofs_map["judge"] = f
        if "scorecard" in f: proofs_map["scorecard"] = f
        if "audit" in f: proofs_map["audit"] = f
        
    strategy = {
        "strategy_id": strat_id,
        "candidate_id": manifest["candidate_id"],
        "symbol": manifest["symbol"],
        "timeframe": manifest["timeframe"],
        "imported_ts": int(time.time()),
        "export_trace": manifest.get("trace"),
        "proofs": proofs_map,
        "source_export_path": export_path
    }
    write_json(os.path.join(target_dir, "strategy.json"), strategy)
    
    return {
        "strategy_id": strat_id,
        "status": status,
        "target_path": target_dir
    }
