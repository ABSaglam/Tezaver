import os
import zipfile
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

def build_proof_bundle(run_dir: Path) -> Dict[str, Any]:
    """
    MX-5170: Packages all run evidence into a single ZIP bundle.
    Tr: Tüm run kanıtlarını (telemetry, reports vb.) tek bir ZIP paketine toplar.
    """
    bundle_dir = run_dir / "proof_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = bundle_dir / "proof_bundle_v1.zip"
    artifact_count = 0
    total_bytes = 0
    
    # Files/Dirs to include
    include_patterns = [
        "telemetry.ndjson",
        "report.json",
        "scorecard.json",
        "trade_audit_v2.jsonl",
        "reports/**",
        "incidents/**"
    ]
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for pattern in include_patterns:
            if "**" in pattern:
                # Directory recursion
                base_pattern = pattern.replace("/**", "")
                target_dir = run_dir / base_pattern
                if target_dir.exists() and target_dir.is_dir():
                    for file in target_dir.rglob("*"):
                        if file.is_file():
                            rel_path = file.relative_to(run_dir)
                            zipf.write(file, rel_path)
                            artifact_count += 1
                            total_bytes += file.stat().st_size
            else:
                # Single file
                target_file = run_dir / pattern
                if target_file.exists() and target_file.is_file():
                    zipf.write(target_file, pattern)
                    artifact_count += 1
                    total_bytes += target_file.stat().st_size
                    
    # Create bundle metadata
    metadata = {
        "run_id": run_dir.name,
        "bundle_ts": datetime.utcnow().isoformat() + "Z",
        "bundle_v": "v1",
        "artifact_count": artifact_count,
        "total_bytes": total_bytes,
        "bundle_path": str(zip_path.relative_to(run_dir.parent.parent.parent)) # Relative to project root
    }
    
    with open(bundle_dir / "bundle_metadata_v1.json", "w") as f:
        json.dump(metadata, f, indent=2)
        
    return metadata
