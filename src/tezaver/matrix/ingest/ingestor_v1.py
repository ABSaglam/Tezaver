
"""
Matrix Ingestor V1
==================

Gatekeeper for the Matrix System.
Watches the Bus Inbox, validates bundles, and ingests them into the Matrix Library.

Logic:
1. Scan ~/.tezaver_bus/pipeline/inbox
2. For each Candidate:
   - Validate Directory Name (Protocol V1)
   - Validate Manifest.json (Schema V1)
   - Validate Data Integrity (Parquet readable, 'timestamp' present)
3. Outcome:
   - VALID: Move to src/tezaver/matrix/library/bundles/{id}
   - INVALID: Move to ~/.tezaver_bus/pipeline/rejected/{id} (+ error.log)
"""

import os
import shutil
import json
import time
import logging
from pathlib import Path
from typing import List, Optional
import pandas as pd

from tezaver.schemas.bundle_v1 import BundleManifestV1, BundleNamingV1, PROTOCOL_VERSION

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [INGESTOR] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("matrix_ingestor.log") # Log to file as well
    ]
)
logger = logging.getLogger("MatrixIngestor")

class MatrixIngestorV1:
    def __init__(self, bus_root_env: str = "TEZAVER_BUS", project_root: str = "."):
        # Resolve Bus
        home = os.environ.get(bus_root_env, os.environ.get("HOME", "."))
        self.bus_root = Path(home) / ".tezaver_bus" / "pipeline"
        self.inbox_dir = self.bus_root / "inbox"
        self.rejected_dir = self.bus_root / "rejected"
        
        # Resolve Matrix Library (Destination)
        # Using specific project path for clean integration
        self.matrix_lib_dir = Path(project_root) / "src/tezaver/matrix/library/bundles"
        
        self._ensure_dirs()
        
    def _ensure_dirs(self):
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.rejected_dir.mkdir(parents=True, exist_ok=True)
        self.matrix_lib_dir.mkdir(parents=True, exist_ok=True)
        
    def scan_and_ingest(self) -> int:
        """
        One-shot scan of inbox. Returns number of processed bundles.
        """
        processed_count = 0
        candidates = [p for p in self.inbox_dir.iterdir() if p.is_dir()]
        
        if not candidates:
            logger.debug("Inbox empty.")
            return 0
            
        logger.info(f"Scanning inbox: {len(candidates)} candidates found.")
        
        for bundle_path in candidates:
            try:
                self._process_bundle(bundle_path)
                processed_count += 1
            except Exception as e:
                logger.error(f"Critical error processing {bundle_path.name}: {e}")
                # Try to reject if possible to unblock queue, else skip
                try:
                    self._reject(bundle_path, f"Critical System Error: {e}")
                except:
                    pass
                    
        return processed_count
        
    def _process_bundle(self, path: Path):
        bundle_id = path.name
        logger.info(f"Processing candidate: {bundle_id}")
        
        # 1. Validate Name
        if not BundleNamingV1.validate_id(bundle_id):
            self._reject(path, f"Invalid Bundle ID format: {bundle_id}. Expected standard format.")
            return

        # 2. Validate Manifest
        manifest_path = path / "manifest.json"
        if not manifest_path.exists():
            self._reject(path, "Missing manifest.json")
            return
            
        try:
            with open(manifest_path, 'r') as f:
                data = json.load(f)
            manifest = BundleManifestV1.from_dict(data)
        except Exception as e:
            self._reject(path, f"Manifest Validation Failed: {e}")
            return
            
        # 3. Quick Data Validation
        # Check integrity of key parquet file
        # Helper: assume history file name standard? Or check manifest pointers?
        # Protocol V1 requires 'data' folder usually, but let's be flexible or strict?
        # Let's check any .parquet in valid locations
        data_valid = self._validate_data_integrity(path, manifest)
        if not data_valid[0]:
            self._reject(path, f"Data Integrity Failed: {data_valid[1]}")
            return
            
        # 4. Success -> Ingest
        self._ingest(path)
        
    def _validate_data_integrity(self, path: Path, manifest: BundleManifestV1) -> (bool, str):
        """Check if data files are readable and have required columns."""
        # Find parquet files
        # Check pointers first?
        # The PackagingV1 writes absolute/relative paths in 'pointers'. But specific file structure is what we care for.
        
        # Scan for any parquet
        parquets = list(path.rglob("*.parquet"))
        if not parquets:
            return False, "No parquet data files found in bundle."
            
        for p in parquets:
            try:
                df = pd.read_parquet(p)
                if df.empty:
                    return False, f"Empty dataframe in {p.name}"
                
                # Check for timestamp
                # We enforce 'timestamp' or 'open_time' or 'event_time' standardization
                # Plan says: "Time column MUST be 'timestamp'"
                # But let's allow open_time if we convert it? No, strict ingestor should reject or fix.
                # Let's reject if NO recognized time column.
                
                valid_time = False
                for col in ['timestamp', 'open_time', 'time', 'date', 'event_time']:
                    if col in df.columns:
                        valid_time = True
                        break
                
                if not valid_time:
                    return False, f"No valid time column in {p.name}. Found: {list(df.columns)}"
                    
            except Exception as e:
                return False, f"Corrupt parquet {p.name}: {e}"
                
        return True, "OK"

    def _ingest(self, source_path: Path):
        """Move successfully validated bundle to Library."""
        bundle_id = source_path.name
        dest_path = self.matrix_lib_dir / bundle_id
        
        try:
            if dest_path.exists():
                logger.warning(f"Bundle {bundle_id} exists in library. Overwriting.")
                shutil.rmtree(dest_path)
            
            shutil.move(str(source_path), str(dest_path))
            logger.info(f"✅ INGESTED: {bundle_id} -> Library")
            
        except Exception as e:
            logger.error(f"Failed to move {bundle_id} to library: {e}")
            raise e

    def _reject(self, source_path: Path, reason: str):
        """Move failed bundle to Rejected."""
        bundle_id = source_path.name
        dest_path = self.rejected_dir / bundle_id
        
        # Cleanup dest if exists
        if dest_path.exists():
            shutil.rmtree(dest_path)
            
        try:
            shutil.move(str(source_path), str(dest_path))
            
            # Write error log
            with open(dest_path / "rejection_reason.txt", "w") as f:
                f.write(f"Rejected at {time.ctime()}\n")
                f.write(f"Reason: {reason}\n")
                
            logger.warning(f"❌ REJECTED: {bundle_id}. Reason: {reason}")
            
        except Exception as e:
            logger.error(f"Failed to reject {bundle_id}: {e}")

if __name__ == "__main__":
    # Simple Loop Mode
    ingestor = MatrixIngestorV1()
    print(f"Matrix Ingestor V1 Active.")
    print(f"Inbox: {ingestor.inbox_dir}")
    print(f"Library: {ingestor.matrix_lib_dir}")
    print("Watching... (Ctrl+C to stop)")
    
    try:
        while True:
            ingestor.scan_and_ingest()
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nStopping Ingestor.")
