"""
Backup Engine for Tezaver Mac.
Handles creation and restoration of mini and full backups.

Tezaver Philosophy:
- "Veri kutsaldır, kaybolmasına izin verilemez."
- "Geçmişi korumak, geleceği inşa etmenin temelidir."
"""

import os
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from tezaver.core.config import get_turkey_now

from tezaver.core import coin_cell_paths
from tezaver.core.config import BACKUP_DIR_NAME
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


def get_project_root() -> Path:
    """Returns the project root directory."""
    return coin_cell_paths.get_project_root()


def get_backup_root() -> Path:
    """Returns the root backup directory, creating it if needed."""
    root = get_project_root()
    backups_dir = root / BACKUP_DIR_NAME
    backups_dir.mkdir(exist_ok=True)
    return backups_dir


def get_daily_backup_dir() -> Path:
    """Returns the daily (mini) backup directory."""
    daily_dir = get_backup_root() / "daily"
    daily_dir.mkdir(exist_ok=True)
    return daily_dir


def get_full_backup_dir() -> Path:
    """Returns the full backup directory."""
    full_dir = get_backup_root() / "full"
    full_dir.mkdir(exist_ok=True)
    return full_dir


def _add_path_to_zip(zipf: zipfile.ZipFile, base_path: Path, rel_root: Path) -> None:
    """
    Recursively adds a directory to a zip file.
    
    Args:
        zipf: Open ZipFile object.
        base_path: The absolute path to the directory to add.
        rel_root: The relative path to use as the root in the archive.
    """
    if not base_path.exists():
        return

    # If it's a file, just add it
    if base_path.is_file():
        arcname = str(rel_root)
        zipf.write(base_path, arcname=arcname)
        return

    # If directory, walk it
    for root, _, files in os.walk(base_path):
        root_path = Path(root)
        # Calculate relative path from base_path
        rel_path = root_path.relative_to(base_path)
        
        for file in files:
            file_path = root_path / file
            # Archive name is rel_root + relative path from base + filename
            if str(rel_path) == ".":
                arcname = rel_root / file
            else:
                arcname = rel_root / rel_path / file
            
            zipf.write(file_path, arcname=str(arcname))


def create_mini_backup() -> Path:
    """
    Creates a 'mini' backup containing only logical state.
    Includes: data/coin_state.json, data/coin_profiles/
    """
    root = get_project_root()
    ts = get_turkey_now().strftime("%Y%m%d_%H%M%S")
    out_dir = get_daily_backup_dir()
    archive_path = out_dir / f"tezaver_mini_{ts}.zip"
    
    print(f"Creating mini backup at {archive_path}...")
    logger.info(f"Creating mini backup at {archive_path}...")
    
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as z:
        # 1. coin_state.json
        coin_state = root / "data" / "coin_state.json"
        if coin_state.exists():
            z.write(coin_state, arcname="data/coin_state.json")
        
        # 2. coin_profiles
        coin_profiles = root / "data" / "coin_profiles"
        if coin_profiles.exists():
            _add_path_to_zip(z, coin_profiles, Path("data/coin_profiles"))
            
        # 3. global_wisdom (optional)
        global_wisdom = root / "data" / "global_wisdom"
        if global_wisdom.exists():
            _add_path_to_zip(z, global_wisdom, Path("data/global_wisdom"))
            
    logger.info(f"Mini backup created successfully: {archive_path.name}")
    return archive_path


def create_full_backup() -> Path:
    """
    Creates a 'full' backup containing all data artifacts.
    Includes: data/, coin_cells/, library/, config/
    """
    root = get_project_root()
    ts = get_turkey_now().strftime("%Y%m%d_%H%M%S")
    out_dir = get_full_backup_dir()
    archive_path = out_dir / f"tezaver_full_{ts}.zip"
    
    logger.info(f"Creating full backup at {archive_path}...")
    
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as z:
        for dir_name in ["data", "coin_cells", "library", "config"]:
            p = root / dir_name
            if p.exists():
                if p.is_dir():
                    _add_path_to_zip(z, p, Path(dir_name))
                else:
                    z.write(p, arcname=dir_name)
                    
    logger.info(f"Full backup created successfully: {archive_path.name}")
    return archive_path


def list_backups(kind: str = "mini") -> List[Path]:
    """
    Lists available backups of a given kind.
    
    Args:
        kind: "mini" or "full"
    """
    if kind == "mini":
        target_dir = get_daily_backup_dir()
    elif kind == "full":
        target_dir = get_full_backup_dir()
    else:
        return []
        
    if not target_dir.exists():
        return []
        
    backups = list(target_dir.glob("*.zip"))
    # Sort by modification time (newest last)
    backups.sort(key=lambda x: x.stat().st_mtime)
    return backups


def get_latest_backup(kind: str = "mini") -> Optional[Path]:
    """Returns the most recent backup of a given kind."""
    backups = list_backups(kind)
    if not backups:
        return None
    return backups[-1]


def restore_backup(archive_path: Path, mode: str = "auto", dry_run: bool = True) -> None:
    """
    Restores a backup archive.
    
    Args:
        archive_path: Path to the zip file.
        mode: "mini", "full", or "auto".
        dry_run: If True, only prints what would happen.
    """
    if not archive_path.exists():
        logger.error(f"Error: Backup file not found: {archive_path}")
        return

    root = get_project_root()
    
    # Determine mode if auto
    if mode == "auto":
        if "mini" in archive_path.name:
            mode = "mini"
        elif "full" in archive_path.name:
            mode = "full"
        else:
            logger.warning("Warning: Could not auto-detect mode, defaulting to 'full' extraction safety check.")
            mode = "full" # Default to full extraction logic (extract all)
            
    logger.info(f"Restoring backup: {archive_path.name}")
    logger.info(f"Mode: {mode}")
    logger.info(f"Dry Run: {dry_run}")
    
    with zipfile.ZipFile(archive_path, "r") as z:
        members = z.namelist()
        
        # Filter members based on mode
        to_extract = []
        if mode == "mini":
            # Only restore logical state
            for m in members:
                if m.startswith("data/coin_state.json") or m.startswith("data/coin_profiles/"):
                    to_extract.append(m)
        else:
            # Full restore - extract everything
            to_extract = members
            
        if not to_extract:
            logger.warning("No matching files found in archive for this mode.")
            return

        logger.info(f"Found {len(to_extract)} files to restore.")
        
        for member in to_extract:
            target_path = root / member
            if dry_run:
                logger.info(f"[DRY-RUN] Would restore {member} -> {target_path}")
            else:
                # Ensure parent dir exists
                target_path.parent.mkdir(parents=True, exist_ok=True)
                # Extract
                z.extract(member, path=root)
                logger.info(f"Restored {member}")
                
    if not dry_run:
        logger.info("Restore completed successfully.")
    else:
        logger.info("Dry run completed. No changes made.")
