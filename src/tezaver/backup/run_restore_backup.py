import sys
import os
from pathlib import Path

# Add src to sys.path
project_root = Path(__file__).resolve().parent.parent.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from tezaver.backup.backup_engine import (
    get_latest_backup,
    restore_backup,
    list_backups,
)
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main():
    args = sys.argv[1:]
    
    kind = "mini"
    if "full" in args:
        kind = "full"
        
    dry_run = True
    if "apply" in args:
        dry_run = False
        
    logger.info(f"Looking for latest {kind} backup...")
    latest = get_latest_backup(kind)
    
    if latest is None:
        logger.warning(f"No {kind} backups found.")
        return
        
    logger.info(f"Found backup: {latest}")
    
    if dry_run:
        logger.info("Running in DRY-RUN mode. Use 'apply' argument to execute.")
    else:
        logger.warning("WARNING: This will overwrite current data!")
        confirm = input("Type 'yes' to confirm restore: ")
        if confirm.lower() != "yes":
            logger.info("Restore cancelled.")
            return
    
    restore_backup(latest, mode="auto", dry_run=dry_run)

if __name__ == "__main__":
    main()
