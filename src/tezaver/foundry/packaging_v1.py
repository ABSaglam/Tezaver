"""
Packaging v1 - ApprovedRallyBundle Packaging Engine
====================================================

Packages QC-PASSED approved annotations into Matrix-ready bundles.
"""

from typing import List, Optional, Dict, Any
import pandas as pd
from pathlib import Path
import json

from tezaver.sniper.sniper_annotations import SniperAnnotation, SniperAnnotationRepository
from tezaver.foundry.models import QCReport
from tezaver.foundry.bundle_models import ApprovedRallyBundleManifest
from tezaver.foundry import bundle_io
from tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct
from tezaver.rally.rally_narrative_engine import analyze_scenario, SCENARIO_DEFINITIONS
from tezaver.core import coin_cell_paths


def package_event(
    symbol: str,
    timeframe: str,
    event_id: str,
    output_root: str = ".tezaver_matrix/approved_bundles_v1"
) -> Optional[str]:
    """
    Package a single event into ApprovedRallyBundle.
    
    Args:
        symbol: Trading pair symbol
        timeframe: Timeframe (15m, 1h, 4h)
        event_id: Event identifier
        output_root: Root directory for bundles
    
    Returns:
        Path to bundle directory, or None if skipped
    """
    # Load annotation
    repo = SniperAnnotationRepository()
    annotation = repo.get_one(symbol, timeframe, event_id)
    
    if not annotation:
        return None
    
    # Check APPROVED status
    if getattr(annotation, 'status', '') != 'APPROVED':
        return None
    
    # Load QC report
    qc_report_path = Path(f".tezaver_matrix/foundry/qc_reports/{symbol}/{timeframe}/qc_{event_id}.json")
    if not qc_report_path.exists():
        return None
    
    with open(qc_report_path, 'r') as f:
        qc_report_dict = json.load(f)
    
    qc_report = QCReport.from_dict(qc_report_dict)
    
    # Skip if QC not PASS
    if qc_report.qc_verdict != "PASS":
        return None
    
    # Load event dataset row
    event_row = _load_event_row(symbol, timeframe, event_id)
    if event_row is None:
        return None
    
    # Compute tier from future_max_gain_pct
    future_gain = event_row.get('future_max_gain_pct')
    if future_gain is not None and pd.notna(future_gain):
        tier = compute_tier_from_gain_pct(float(future_gain))
        if tier is None:
            tier = "UNKNOWN"
    else:
        tier = "UNKNOWN"
    
    # Create bundle directory
    bundle_dir = bundle_io.create_bundle_directory(symbol, timeframe, event_id, output_root)
    
    # Build approved dict
    approved = {
        "entry_bar_offset": getattr(annotation, 'approved_entry_bar_offset', None),
        "entry_ts": getattr(annotation, 'approved_entry_ts', None),
        "exit_bar_offset": getattr(annotation, 'approved_exit_bar_offset', None),
        "exit_ts": getattr(annotation, 'approved_exit_ts', None)
    }
    
    # Build QC dict
    qc_dict = {
        "verdict": qc_report.qc_verdict,
        "score": qc_report.qc_score,
        "report_path": f"../../../qc_reports/{symbol}/{timeframe}/qc_{event_id}.json"
    }
    
    # Build pointers (relative paths)
    annotation_path = repo._get_file_path(symbol, timeframe)
    event_dataset_path = _get_event_dataset_path(symbol, timeframe)
    history_path = coin_cell_paths.get_history_file(symbol, timeframe)
    
    pointers = {
        "annotation_path": str(annotation_path),
        "event_dataset_path": event_dataset_path if event_dataset_path else "",
        "history_path": str(history_path)
    }
    
    # Extract price window
    price_window_df = _extract_price_window(symbol, timeframe, event_row.get('event_time'))
    
    # Build manifest
    bundle_id = f"{symbol}_{timeframe}_{event_id}"
    event_time_iso = pd.to_datetime(event_row.get('event_time')).isoformat() if pd.notna(event_row.get('event_time')) else ""
    
    # Analyze Narrative / Scenario
    try:
        scenario_id = analyze_scenario(event_row)
        scenario_def = SCENARIO_DEFINITIONS.get(scenario_id, SCENARIO_DEFINITIONS["SCENARIO_NEUTRAL"])
        narrative = {
            "label": scenario_def["label"],
            "desc": scenario_def["desc"],
            "risk": scenario_def["risk"]
        }
    except Exception as e:
        scenario_id = "SCENARIO_NEUTRAL"
        narrative = SCENARIO_DEFINITIONS["SCENARIO_NEUTRAL"]

    manifest = ApprovedRallyBundleManifest(
        bundle_id=bundle_id,
        symbol=symbol,
        timeframe=timeframe,
        event_id=event_id,
        event_time_iso=event_time_iso,
        tier=tier,
        approved=approved,
        qc=qc_dict,
        pointers=pointers,
        scenario_id=scenario_id,
        narrative=narrative
    )
    
    # Prepare event row dict (minimal fields)
    event_row_dict = {
        "event_id": event_id,
        "event_time": event_time_iso,
        "future_max_gain_pct": event_row.get('future_max_gain_pct'),
        "bars_to_peak": int(event_row.get('bars_to_peak')) if pd.notna(event_row.get('bars_to_peak')) else None,
        "tier": tier
    }
    
    # Prepare annotation dict
    annotation_dict = annotation.to_dict()
    
    # Write all bundle files
    bundle_io.write_bundle_files(
        bundle_dir=bundle_dir,
        manifest=manifest,
        annotation_dict=annotation_dict,
        qc_report_dict=qc_report_dict,
        event_row_dict=event_row_dict,
        price_window_df=price_window_df
    )
    
    return str(bundle_dir)


def package_symbol_timeframe(
    symbol: str,
    timeframe: str,
    limit: Optional[int] = None,
    output_root: str = ".tezaver_matrix/approved_bundles_v1"
) -> List[str]:
    """
    Package all QC-PASSED events for a symbol/timeframe.
    
    Args:
        symbol: Trading pair symbol
        timeframe: Timeframe (15m, 1h, 4h)
        limit: Optional limit on number of bundles to create
        output_root: Root directory for bundles
    
    Returns:
        List of created bundle directory paths
    """
    bundle_dirs = []
    
    # Load all annotations
    repo = SniperAnnotationRepository()
    annotations = repo.load_all(symbol, timeframe)
    
    if not annotations:
        return bundle_dirs
    
    # Filter APPROVED annotations
    approved_anns = [ann for ann in annotations if getattr(ann, 'status', '') == 'APPROVED']
    
    # Apply limit if specified
    if limit:
        approved_anns = approved_anns[:limit]
    
    # Package each annotation
    for ann in approved_anns:
        bundle_dir = package_event(symbol, timeframe, ann.event_id, output_root)
        if bundle_dir:
            bundle_dirs.append(bundle_dir)
    
    return bundle_dirs


def _load_event_row(symbol: str, timeframe: str, event_id: str) -> Optional[pd.Series]:
    """Load event dataset row for the given event_id."""
    event_path = _get_event_dataset_path(symbol, timeframe)
    if not event_path or not Path(event_path).exists():
        return None
    
    try:
        df = pd.read_parquet(event_path)
        if 'event_time' in df.columns:
            df['event_time'] = pd.to_datetime(df['event_time'], errors='coerce')
        
        # Try exact match first
        matches = df[df['event_id'] == event_id]
        if not matches.empty:
            return matches.iloc[0]
        
        return None
    except:
        return None


def _get_event_dataset_path(symbol: str, timeframe: str) -> Optional[str]:
    """Get path to event dataset for the given symbol/timeframe."""
    if timeframe == "15m":
        return f"library/fast15_rallies/{symbol}/fast15_rallies.parquet"
    elif timeframe == "1h":
        return f"library/time_labs/1h/{symbol}/rallies_1h.parquet"
    elif timeframe == "4h":
        return f"library/time_labs/4h/{symbol}/rallies_4h.parquet"
    return None


def _extract_price_window(
    symbol: str,
    timeframe: str,
    event_time: Any,
    window_before: int = 100,
    window_after: int = 300
) -> Optional[pd.DataFrame]:
    """
    Extract price window around event.
    
    Args:
        symbol: Trading pair symbol
        timeframe: Timeframe
        event_time: Event timestamp
        window_before: Bars before event
        window_after: Bars after event
    
    Returns:
        Price window dataframe or None
    """
    if event_time is None or pd.isna(event_time):
        return None
    
    history_file = coin_cell_paths.get_history_file(symbol, timeframe)
    if not history_file.exists():
        return None
    
    try:
        df = pd.read_parquet(history_file)
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', errors='coerce')
        
        # Normalize timezone
        event_ts = pd.to_datetime(event_time)
        if df['open_time'].dt.tz is not None and event_ts.tz is None:
            event_ts = event_ts.tz_localize('UTC')
        elif df['open_time'].dt.tz is None and event_ts.tz is not None:
            event_ts = event_ts.tz_localize(None)
        
        # Find event index
        mask = df['open_time'] <= event_ts
        matching_indices = df[mask].index.tolist()
        
        if not matching_indices:
            return None
        
        event_idx = matching_indices[-1]
        
        # Extract window
        start_idx = max(0, event_idx - window_before)
        end_idx = min(len(df), event_idx + window_after + 1)
        
        window_df = df.iloc[start_idx:end_idx].copy()
        
        # Keep only essential columns
        essential_cols = ['open_time', 'open', 'high', 'low', 'close', 'volume']
        available_cols = [col for col in essential_cols if col in window_df.columns]
        
        return window_df[available_cols]
    except:
        return None
