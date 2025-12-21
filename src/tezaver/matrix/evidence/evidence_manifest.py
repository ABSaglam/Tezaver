import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

def sha256_file(path: Path) -> str:
    """Computes SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_canonical_json_hash(data: Dict) -> str:
    """Computes SHA256 hash of a canonicalized JSON string."""
    json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

def generate_manifest(run_dir: Path, mode: str, build_info: Dict) -> Dict[str, Any]:
    """
    MX-5250: Generates a tamper-evident evidence manifest for a run.
    Tr: Bir run için artifact'leri sha256 ile mühürler ve manifest üretir.
    """
    reports_dir = run_dir / "reports"
    artifacts = []
    
    # 1. Collect Artifacts
    # Core artifacts
    core_files = ["report.json", "scorecard.json", "telemetry.ndjson", "trade_audit_v2.jsonl"]
    for cf in core_files:
        p = run_dir / cf
        if p.exists():
            artifacts.append({
                "rel_path": cf,
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
                "mtime": datetime.fromtimestamp(p.stat().st_mtime).isoformat()
            })
            
    # Reports
    if reports_dir.exists():
        for p in reports_dir.glob("*.json"):
            rel_path = f"reports/{p.name}"
            artifacts.append({
                "rel_path": rel_path,
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
                "mtime": datetime.fromtimestamp(p.stat().st_mtime).isoformat()
            })

    # 2. Hash Chaining (Optional v1)
    prev_manifest_sha256 = None
    runs_root = run_dir.parent # out/matrix_runs/<mode>/
    if runs_root.exists():
        # Find latest run excluding current
        prev_runs = sorted(
            [d for d in runs_root.iterdir() if d.is_dir() and d.name != run_dir.name],
            key=os.path.getmtime,
            reverse=True
        )
        if prev_runs:
            prev_man_path = prev_runs[0] / "reports" / "evidence_manifest_v1.json"
            if prev_man_path.exists():
                try:
                    with open(prev_man_path, "r") as f:
                        pm = json.load(f)
                        prev_manifest_sha256 = pm.get("manifest_sha256")
                except: pass

    # 3. Construct Manifest
    manifest = {
        "run_id": build_info.get("run_id"),
        "engine_version": build_info.get("engine_version", "v4"),
        "build_commit": build_info.get("build_commit", "unknown"),
        "config_signature": build_info.get("config_signature"),
        "data_fingerprint": build_info.get("data_fingerprint"),
        "ts": datetime.now().isoformat(),
        "artifacts": sorted(artifacts, key=lambda x: x["rel_path"]),
        "prev_manifest_sha256": prev_manifest_sha256
    }
    
    # Self-signing (manifest_sha256 is hash of the manifest content excluding itself)
    manifest["manifest_sha256"] = get_canonical_json_hash(manifest)
    
    # 4. Save
    reports_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = reports_dir / "evidence_manifest_v1.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        
    return manifest
