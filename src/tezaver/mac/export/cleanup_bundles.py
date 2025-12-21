import argparse
import shutil
import os
import sys
import types
from pathlib import Path
from datetime import datetime, timedelta

# MACX-2060: Global dummy dotenv mock
try:
    import dotenv
except ImportError:
    dummy_dotenv = types.ModuleType('dotenv')
    dummy_dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules['dotenv'] = dummy_dotenv

from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def cleanup_bundles(root_dir: Path, keep_last: int = None, retention_days: int = None):
    """
    Cleans up old bundles in out/matrix_candidates/{symbol}/{tf}/bundle_v*/
    MACX-2060
    """
    if not root_dir.exists():
        logger.warning(f"Root directory does not exist: {root_dir}")
        return

    # Find all bundle directories
    # Structure: root_dir / {symbol} / {tf} / bundle_{version} / {timestamp}_bundle_...
    # Wait, in our implementation bundle_dir is the version dir itself for now?
    # Let's re-check bundle_exporter.py:
    # bundle_dir = self.output_base / symbol / timeframe / f"bundle_{version_tag}"
    # This means multiple runs overwrite the same dir unless we change it.
    
    # Correction: Based on my bundle_exporter implementation, bundle_dir is fixed.
    # To support retention, normally we'd want a timestamp in the bundle folder name.
    # My bundle_id has a timestamp, but the DIR currently is fixed to bundle_v1.
    
    # For Sprint-2, I will assume we might want to clean up multiple versions or 
    # if the user manually added timestamps.
    
    logger.info(f"🧹 Starting cleanup in {root_dir}...")
    
    # Generic logic: Find all subdirs in out/matrix_candidates that contain manifest.json
    bundles = []
    for manifest_path in root_dir.glob("**/manifest.json"):
        bundle_path = manifest_path.parent
        mtime = datetime.fromtimestamp(bundle_path.stat().st_mtime)
        bundles.append((bundle_path, mtime))
    
    # Sort by mtime descending (newest first)
    bundles.sort(key=lambda x: x[1], reverse=True)
    
    to_delete = []
    
    # Retention by count
    if keep_last is not None:
        if len(bundles) > keep_last:
            to_delete.extend(bundles[keep_last:])
            
    # Retention by days
    if retention_days is not None:
        now = datetime.now()
        for b_path, b_time in bundles:
            if (now - b_time).days > retention_days:
                if (b_path, b_time) not in to_delete:
                    to_delete.append((b_path, b_time))
                    
    # Perform deletion
    deleted_count = 0
    for b_path, b_time in to_delete:
        try:
            logger.info(f"🗑️ Deleting old bundle: {b_path} (from {b_time})")
            shutil.rmtree(b_path)
            deleted_count += 1
        except Exception as e:
            logger.error(f"❌ Failed to delete {b_path}: {e}")
            
    logger.info(f"✅ Cleanup finished. {deleted_count} bundles removed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CandidateBundle Cleanup Tool")
    parser.add_argument("--root", type=str, default="out/matrix_candidates", help="Root candidates directory")
    parser.add_argument("--keep-last", type=int, help="Number of newest bundles to keep")
    parser.add_argument("--retention-days", type=int, help="Number of days to keep bundles")
    
    args = parser.parse_args()
    cleanup_bundles(Path(args.root), args.keep_last, args.retention_days)
