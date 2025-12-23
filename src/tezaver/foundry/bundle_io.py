"""
Bundle I/O Layer
================

File operations for ApprovedRallyBundle packaging.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

from tezaver.foundry.bundle_models import ApprovedRallyBundleManifest


def create_bundle_directory(
    symbol: str,
    timeframe: str,
    event_id: str,
    output_root: str = ".tezaver_matrix/approved_bundles_v1"
) -> Path:
    """
    Create bundle directory structure.
    
    Args:
        symbol: Trading pair symbol
        timeframe: Timeframe (15m, 1h, 4h)
        event_id: Event identifier
        output_root: Root directory for bundles
    
    Returns:
        Path to created bundle directory
    """
    bundle_dir = Path(output_root) / symbol / timeframe / event_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    return bundle_dir


def write_bundle_manifest(manifest: ApprovedRallyBundleManifest, bundle_dir: Path) -> Path:
    """
    Write manifest.json to bundle directory.
    
    Args:
        manifest: Manifest object
        bundle_dir: Bundle directory path
    
    Returns:
        Path to written manifest file
    """
    manifest_path = bundle_dir / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest.to_dict(), f, indent=2)
    return manifest_path


def write_annotation_snapshot(annotation_dict: Dict[str, Any], bundle_dir: Path) -> Path:
    """
    Write annotation.json to bundle directory.
    
    Args:
        annotation_dict: Annotation data as dictionary
        bundle_dir: Bundle directory path
    
    Returns:
        Path to written annotation file
    """
    annotation_path = bundle_dir / "annotation.json"
    with open(annotation_path, 'w') as f:
        json.dump(annotation_dict, f, indent=2)
    return annotation_path


def write_qc_report_copy(qc_report_dict: Dict[str, Any], bundle_dir: Path) -> Path:
    """
    Write qc_report.json to bundle directory.
    
    Args:
        qc_report_dict: QC report data as dictionary
        bundle_dir: Bundle directory path
    
    Returns:
        Path to written QC report file
    """
    qc_path = bundle_dir / "qc_report.json"
    with open(qc_path, 'w') as f:
        json.dump(qc_report_dict, f, indent=2)
    return qc_path


def write_event_row(event_row_dict: Dict[str, Any], bundle_dir: Path) -> Path:
    """
    Write event_row.json to bundle directory.
    
    Args:
        event_row_dict: Event row data as dictionary
        bundle_dir: Bundle directory path
    
    Returns:
        Path to written event row file
    """
    event_path = bundle_dir / "event_row.json"
    with open(event_path, 'w') as f:
        json.dump(event_row_dict, f, indent=2)
    return event_path


def write_price_window(price_window_df: pd.DataFrame, bundle_dir: Path) -> Path:
    """
    Write price_window.parquet to bundle directory.
    
    Args:
        price_window_df: Price window dataframe
        bundle_dir: Bundle directory path
    
    Returns:
        Path to written price window file
    """
    price_path = bundle_dir / "price_window.parquet"
    price_window_df.to_parquet(price_path, index=False)
    return price_path


def get_relative_path(from_path: Path, to_path: Path) -> str:
    """
    Calculate relative path from one location to another.
    
    Args:
        from_path: Source path (e.g., bundle directory)
        to_path: Target path (e.g., annotation file)
    
    Returns:
        Relative path as string
    """
    try:
        # Make both absolute
        from_abs = from_path.resolve()
        to_abs = to_path.resolve()
        
        # Calculate relative
        rel_path = to_abs.relative_to(from_abs.parent)
        return str(rel_path)
    except ValueError:
        # If relative calculation fails, use absolute path
        return str(to_path.resolve())


def write_bundle_files(
    bundle_dir: Path,
    manifest: ApprovedRallyBundleManifest,
    annotation_dict: Dict[str, Any],
    qc_report_dict: Dict[str, Any],
    event_row_dict: Dict[str, Any],
    price_window_df: Optional[pd.DataFrame] = None
) -> Dict[str, Path]:
    """
    Write all bundle files.
    
    Args:
        bundle_dir: Bundle directory
        manifest: Manifest object
        annotation_dict: Annotation data
        qc_report_dict: QC report data
        event_row_dict: Event row data
        price_window_df: Optional price window dataframe
    
    Returns:
        Dictionary of written file paths
    """
    written_files = {}
    
    written_files['manifest'] = write_bundle_manifest(manifest, bundle_dir)
    written_files['annotation'] = write_annotation_snapshot(annotation_dict, bundle_dir)
    written_files['qc_report'] = write_qc_report_copy(qc_report_dict, bundle_dir)
    written_files['event_row'] = write_event_row(event_row_dict, bundle_dir)
    
    if price_window_df is not None and not price_window_df.empty:
        written_files['price_window'] = write_price_window(price_window_df, bundle_dir)
    
    return written_files
