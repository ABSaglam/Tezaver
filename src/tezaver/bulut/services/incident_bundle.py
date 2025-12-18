# Tezaver Bulut - Incident Bundle Service
"""
Exports system state (logs, db, config) for debugging.
"""

import os
import shutil
import zipfile
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

class IncidentBundleService:
    def __init__(self, output_dir: str):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        
    def create_bundle(self, ctx, reason: str) -> str:
        """
        Create a zip bundle.
        Returns absolute path to zip file.
        """
        ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_reason = "".join([c if c.isalnum() else "_" for c in reason])
        bundle_name = f"incident_{ts_str}_{safe_reason}"
        bundle_dir = self._output_dir / bundle_name
        bundle_dir.mkdir(exist_ok=True)
        
        try:
            # 1. Config Dump (Redacted)
            cfg = ctx.config.to_dict()
            # Redact keys
            if "binance_api_secret" in cfg: cfg["binance_api_secret"] = "***"
            if "arm_token" in cfg: cfg["arm_token"] = "***"
            
            with open(bundle_dir / "config.json", "w") as f:
                json.dump(cfg, f, indent=2)
                
            # 2. System Status
            if ctx.status_service:
                st = ctx.status_service.get_status(ctx)
                with open(bundle_dir / "status.json", "w") as f:
                    json.dump(st.to_dict(), f, indent=2)
            
            # 3. Telemetry Log (Tail)
            # Assuming telemetry path is known or in config.
            # ctx.telemetry has _path
            if ctx.telemetry and hasattr(ctx.telemetry, "_path"):
                log_path = ctx.telemetry._path
                if log_path.exists():
                    shutil.copy2(log_path, bundle_dir / "telemetry.ndjson")
                    
            # 4. DB Snapshot
            # ctx.persistence has db path.
            # Need to checkpoint/backup safely?
            # SQLite allows online backup or just copy if WAL is ok.
            # For simplicity, we just copy.
            if ctx.persistence and hasattr(ctx.persistence, "_db_path"):
                 db_path = Path(ctx.persistence._db_path)
                 if db_path.exists():
                     shutil.copy2(db_path, bundle_dir / "bulut.db")
            
            # 5. Metadata
            with open(bundle_dir / "metadata.txt", "w") as f:
                f.write(f"Reason: {reason}\n")
                f.write(f"Timestamp: {ts_str}\n")
                
            # Zip it
            zip_path = self._output_dir / f"{bundle_name}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(bundle_dir):
                    for file in files:
                        abs_file = os.path.join(root, file)
                        rel_file = os.path.relpath(abs_file, bundle_dir)
                        zf.write(abs_file, rel_file)
                        
            return str(zip_path)
            
        finally:
            # Cleanup temp dir
            if bundle_dir.exists():
                shutil.rmtree(bundle_dir)
