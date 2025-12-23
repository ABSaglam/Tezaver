"""
Bundle Index - ApprovedRallyBundle Scanning
============================================

Scan and index ApprovedRallyBundle packages for UI display.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd


def scan_bundles(root_dir: str = ".tezaver_matrix/approved_bundles_v1") -> pd.DataFrame:
    """
    Scan all bundle manifests and create inventory DataFrame.
    
    Args:
        root_dir: Root directory for bundles
    
    Returns:
        DataFrame with bundle inventory
    """
    root_path = Path(root_dir)
    
    if not root_path.exists():
        return pd.DataFrame()
    
    # Find all manifest files
    manifest_files = list(root_path.glob("*/*/*/manifest.json"))
    
    if not manifest_files:
        return pd.DataFrame()
    
    # Parse each manifest
    bundles = []
    for manifest_file in manifest_files:
        try:
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
            
            bundle_info = {
                "symbol": manifest.get("symbol", ""),
                "timeframe": manifest.get("timeframe", ""),
                "event_id": manifest.get("event_id", ""),
                "tier": manifest.get("tier", "UNKNOWN"),
                "qc_verdict": manifest.get("qc", {}).get("verdict", ""),
                "qc_score": manifest.get("qc", {}).get("score", 0),
                "event_time_iso": manifest.get("event_time_iso", ""),
                "approved_entry_ts": manifest.get("approved", {}).get("entry_ts", ""),
                "build_ts_iso": manifest.get("build_ts_iso", ""),
                "bundle_dir": str(manifest_file.parent),
                "bundle_id": manifest.get("bundle_id", ""),
                "scenario_id": manifest.get("scenario_id", "SCENARIO_NEUTRAL"),
                "narrative": manifest.get("narrative", {})
            }
            
            bundles.append(bundle_info)
        except Exception as e:
            # Skip malformed manifests
            continue
    
    if not bundles:
        return pd.DataFrame()
    
    # Create DataFrame
    df = pd.DataFrame(bundles)
    
    # Sort by qc_score desc, then event_time desc
    df = df.sort_values(
        by=["qc_score", "event_time_iso"],
        ascending=[False, False]
    ).reset_index(drop=True)
    
    return df


def filter_bundles(
    df: pd.DataFrame,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    tiers: Optional[List[str]] = None,
    qc_verdicts: Optional[List[str]] = None,
    min_qc_score: int = 0
) -> pd.DataFrame:
    """
    Filter bundle inventory DataFrame.
    
    Args:
        df: Bundle inventory DataFrame
        symbol: Symbol filter (None = all)
        timeframe: Timeframe filter (None = all)
        tiers: Tier filter list (None = all)
        qc_verdicts: QC verdict filter list (None = all)
        min_qc_score: Minimum QC score
    
    Returns:
        Filtered DataFrame
    """
    if df.empty:
        return df
    
    filtered = df.copy()
    
    # Symbol filter
    if symbol and symbol != "All":
        filtered = filtered[filtered["symbol"] == symbol]
    
    # Timeframe filter
    if timeframe and timeframe != "All":
        filtered = filtered[filtered["timeframe"] == timeframe]
    
    # Tier filter
    if tiers:
        filtered = filtered[filtered["tier"].isin(tiers)]
    
    # QC verdict filter
    if qc_verdicts:
        filtered = filtered[filtered["qc_verdict"].isin(qc_verdicts)]
    
    # Min QC score filter
    filtered = filtered[filtered["qc_score"] >= min_qc_score]
    
    return filtered


def load_bundle_files(bundle_dir: str) -> Dict[str, Any]:
    """
    Load all files from a bundle directory.
    
    Args:
        bundle_dir: Path to bundle directory
    
    Returns:
        Dictionary with loaded files
    """
    bundle_path = Path(bundle_dir)
    
    result = {
        "manifest": None,
        "annotation": None,
        "qc_report": None,
        "event_row": None,
        "price_window": None
    }
    
    # Load manifest
    manifest_file = bundle_path / "manifest.json"
    if manifest_file.exists():
        with open(manifest_file, 'r') as f:
            result["manifest"] = json.load(f)
    
    # Load annotation
    annotation_file = bundle_path / "annotation.json"
    if annotation_file.exists():
        with open(annotation_file, 'r') as f:
            result["annotation"] = json.load(f)
    
    # Load QC report
    qc_file = bundle_path / "qc_report.json"
    if qc_file.exists():
        with open(qc_file, 'r') as f:
            result["qc_report"] = json.load(f)
    
    # Load event row
    event_file = bundle_path / "event_row.json"
    if event_file.exists():
        with open(event_file, 'r') as f:
            result["event_row"] = json.load(f)
    
    # Load price window
    price_file = bundle_path / "price_window.parquet"
    if price_file.exists():
        try:
            result["price_window"] = pd.read_parquet(price_file)
        except:
            pass
    
    return result
