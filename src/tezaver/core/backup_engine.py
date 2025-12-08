"""
Backup Engine (System Security)
===============================

This module handles creating system snapshots (Code, Data, or Full) and managing their lifecycle
using a 'Rolling Backup' policy (keep last N per type).

Core Logic:
1. Zips specified directories (src, data, library).
2. Saves to 'backups/' with timestamp and label.
3. Rotates old backups based on label to ensure only the latest N remain for that type.
"""

import os
import shutil
import zipfile
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


def get_project_root() -> Path:
    """Resolve project root based on file location."""
    # This file is in src/tezaver/core/backup_engine.py -> 3 levels up to src -> 1 more to root
    return Path(__file__).resolve().parents[3]


def create_snapshot(targets: List[str], label: str, backup_dir_name: str = "backups", max_backups: int = 7) -> Tuple[bool, str]:
    """
    Create a zip snapshot of specific target folders and rotate old backups of that type.
    
    Args:
        targets: List of folder names relative to root (e.g. ["src", "data"]).
        label: Identifier for this backup type (e.g. "full", "src", "data").
               Filename format: tezaver_{label}_{timestamp}.zip
        backup_dir_name: Directory to store backups.
        max_backups: Number of recent backups of THIS LABEL to keep.
        
    Returns:
        Tuple (success: bool, message: str)
    """
    try:
        root = get_project_root()
        backup_dir = root / backup_dir_name
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Generate Filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tezaver_{label}_{timestamp}.zip"
        filepath = backup_dir / filename
        
        # 2. Create Zip
        logger.info(f"Starting backup [{label}]: {filepath}")
        
        items_added = 0
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for folder_name in targets:
                folder_path = root / folder_name
                if not folder_path.exists():
                    logger.warning(f"Target path not found: {folder_path}")
                    continue
                    
                if folder_path.is_file():
                    # Handle single file
                    arcname = folder_path.relative_to(root)
                    zipf.write(folder_path, arcname)
                    items_added += 1
                else:
                    # Handle directory
                    for root_dir, _, files in os.walk(folder_path):
                        for file in files:
                            file_path = Path(root_dir) / file
                            # Create archive name relative to project root
                            arcname = file_path.relative_to(root)
                            zipf.write(file_path, arcname)
                            items_added += 1
                        
        if items_added == 0:
            logger.warning("Backup created but zero items were added!")
        
        logger.info(f"Backup created successfully: {filepath}")
        
        # 3. Rotation Policy (Per Label)
        _rotate_backups(backup_dir, label, max_backups)
        
        size_mb = filepath.stat().st_size / (1024 * 1024)
        return True, f"Yedek [{label}] başarıyla alındı: {filename} ({size_mb:.1f} MB)"
        
    except Exception as e:
        logger.error(f"Backup failed: {e}", exc_info=True)
        return False, f"Yedekleme hatası: {str(e)}"

# Alias for backward compatibility or ease of use
def create_full_snapshot() -> Tuple[bool, str]:
    return create_snapshot(["src", "data", "library"], "full")


def _rotate_backups(backup_dir: Path, label: str, max_backups: int) -> None:
    """
    Enforce rolling backup policy: Keep only latest `max_backups` files FOR THE GIVEN LABEL.
     Pattern: tezaver_{label}_YYYYMMDD...
    """
    try:
        # Glob pattern for this specific label
        pattern = f"tezaver_{label}_*.zip"
        
        files = sorted(
            [f for f in backup_dir.glob(pattern) if f.is_file()],
            key=lambda f: f.stat().st_mtime
        )
        
        total = len(files)
        if total > max_backups:
            to_delete = files[:total - max_backups]
            for f in to_delete:
                try:
                    f.unlink()
                    logger.info(f"Rotated (deleted) old backup: {f.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete old backup {f.name}: {e}")
                    
    except Exception as e:
        logger.error(f"Error during backup rotation: {e}")
