"""
Incident Bundle Export v1
Generic exporter for fatal/BLOCK events (Preflight, Runtime, Gates).
"""

import os
import json
import shutil
import zipfile
import hashlib
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

from tezaver.matrix.live.logs_tail import read_ndjson_tail, filter_events

@dataclass
class BundleContext:
    """Context for bundle export."""
    reason: str
    ndjson_path: Path
    log_file_path: Optional[Path] = None
    config: Optional[Dict[str, Any]] = None
    output_dir: Path = Path("data/incidents")
    last_n_events: int = 500
    last_n_log_lines: int = 300
    repo_branch: str = "unknown"
    repo_commit: str = "unknown"
    cmdline: str = "unknown"

def calculate_sha256(filepath: Path) -> str:
    """Calculate SHA256 of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def redact_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive keys from config dict."""
    redacted = config.copy()
    sensitive = ["key", "secret", "password", "token", "auth"]
    for k in redacted:
        if any(s in k.lower() for s in sensitive):
            redacted[k] = "[REDACTED]"
    return redacted

def export_incident_bundle(ctx: BundleContext) -> str:
    """
    Create an incident bundle zip file.
    Returns the path to the created zip file.
    """
    ts_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ctx.output_dir.mkdir(parents=True, exist_ok=True)
    
    bundle_name = f"incident_bundle_{ts_str}.zip"
    bundle_path = ctx.output_dir / bundle_name
    
    # Prepare temp staging area implicitly (we write directly to zip or memory)
    # But files need to be gathered.
    
    manifest_files = []
    
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        
        # 1. live_events.ndjson (filtered tail)
        events_data = "[]"
        if ctx.ndjson_path.exists():
            tail_result = read_ndjson_tail(ctx.ndjson_path, n=ctx.last_n_events)
            events = tail_result.get("events", [])
            # Serialize
            lines = [json.dumps(e) for e in events]
            events_data = "\n".join(lines)
        
        zf.writestr("live_events.ndjson", events_data)
        manifest_files.append({
            "name": "live_events.ndjson",
            "size_bytes": len(events_data.encode("utf-8")),
            "sha256": hashlib.sha256(events_data.encode("utf-8")).hexdigest()
        })
        
        # 2. recent_logs.txt
        logs_data = "NO_LOG_SOURCE"
        if ctx.log_file_path and ctx.log_file_path.exists():
            try:
                # Read last N lines
                # Not efficient for huge logs, but safe for generic logs
                with open(ctx.log_file_path, "rb") as f:
                    # Seek to end? For now just read lines (safe for typical log sizes in this ctx)
                    # Or use a tail method.
                    # Simple robust way: readlines()
                    lines = f.readlines()
                    tail_lines = lines[-ctx.last_n_log_lines:]
                    logs_data = b"".join(tail_lines).decode("utf-8", errors="replace")
            except Exception as e:
                logs_data = f"ERROR_READING_LOGS: {e}"
        
        zf.writestr("recent_logs.txt", logs_data)
        manifest_files.append({
            "name": "recent_logs.txt",
            "size_bytes": len(logs_data.encode("utf-8")),
            "sha256": hashlib.sha256(logs_data.encode("utf-8")).hexdigest()
        })
        
        # 3. config_snapshot.json
        config_data = "{}"
        if ctx.config:
            safe_config = redact_config(ctx.config)
            config_data = json.dumps(safe_config, indent=2)
        
        zf.writestr("config_snapshot.json", config_data)
        manifest_files.append({
            "name": "config_snapshot.json",
            "size_bytes": len(config_data.encode("utf-8")),
            "sha256": hashlib.sha256(config_data.encode("utf-8")).hexdigest()
        })
        
        # 4. Manifest
        manifest = {
            "metadata": {
                "created_ts_utc": datetime.now(timezone.utc).isoformat(),
                "repo_branch": ctx.repo_branch,
                "repo_commit": ctx.repo_commit,
                "cmdline": ctx.cmdline,
                "reason": ctx.reason
            },
            "files": manifest_files
        }
        manifest_str = json.dumps(manifest, indent=2)
        zf.writestr("manifest.json", manifest_str)
        
    return str(bundle_path)

def emit_export_telemetry(ndjson_path: Path, bundle_path: str, reason: str, files_count: int):
    """Emit INCIDENT_BUNDLE_EXPORTED event."""
    # This appends to the SAME ndjson we likely just read.
    # It's fine, it will appear in next reads.
    
    bundle_sha = calculate_sha256(Path(bundle_path))
    
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": "INCIDENT_BUNDLE_EXPORTED",
        "path": str(bundle_path),
        "reason": reason,
        "bundle_sha256": bundle_sha,
        "files_count": files_count
    }
    
    try:
        with open(ndjson_path, "a") as f:
            f.write(json.dumps(event) + "\n")
    except:
        pass
