import sys
import os
from pathlib import Path

# Add src to sys.path
project_root = Path(__file__).resolve().parent.parent.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from tezaver.backup.backup_engine import create_mini_backup
from tezaver.core.backup_engine import create_snapshot, create_full_snapshot
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def main():
    args = sys.argv[1:]
    
    success = False
    msg = ""

    if "full" in args:
        logger.info("Starting FULL backup...")
        success, msg = create_full_snapshot()
    elif "src" in args:
        logger.info("Starting SRC (Code) backup...")
        success, msg = create_snapshot(["src"], "src")
    elif "data" in args:
        logger.info("Starting DATA backup...")
        success, msg = create_snapshot(["data"], "data")
    elif "library" in args:
        logger.info("Starting LIBRARY backup...")
        success, msg = create_snapshot(["library"], "library")
    elif "state" in args:
        logger.info("Starting STATE backup...")
        success, msg = create_snapshot(["data/coin_state.json"], "state")
    elif "profiles" in args:
        logger.info("Starting PROFILES backup...")
        success, msg = create_snapshot(["data/coin_profiles"], "profiles")
    else:
        logger.info("Starting MINI backup (Default)...")
        create_mini_backup()
        return # Mini backup handles its own logging/return for now or is void

    if success:
        logger.info(msg)
    else:
        # If msg is empty, it might be mini backup or unhandled
        if msg:
            logger.error(msg)
            sys.exit(1)

if __name__ == "__main__":
    main()
