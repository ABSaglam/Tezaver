"""
QC Gate v1 - Quality Control Engine
====================================

Validates APPROVED annotations before Matrix packaging.

7 QC Rules:
- QC-010: History Exists
- QC-020: Approved Entry Exists
- QC-030: Approved Exit Optional
- QC-040: Event Exists in Dataset
- QC-050: Time Consistency
- QC-060: Snap Distance Bound
- QC-070: Closed-Bar Sanity
"""

from typing import Optional, List
import pandas as pd
from pathlib import Path

from tezaver.core.annotations import SniperAnnotation, SniperAnnotationRepository
from tezaver.foundry.models import QCReport
from tezaver.core import coin_cell_paths


def evaluate(
    annotation: SniperAnnotation,
    event_row: Optional[pd.Series],
    history_df: Optional[pd.DataFrame]
) -> QCReport:
    """
    Pure QC evaluation function (no I/O).
    
    Args:
        annotation: SniperAnnotation to validate
        event_row: Event data from rally dataset (optional)
        history_df: Price history dataframe
    
    Returns:
        QCReport with verdict, score, fails, and warns
    """
    fails = []
    warns = []
    score = 100
    
    # QC-010: History Exists
    if history_df is None:
        fails.append("HISTORY_MISSING")
        score -= 40
    elif history_df.empty:
        fails.append("HISTORY_EMPTY")
        score -= 40
    
    # QC-020: Approved Entry Exists
    approved_entry_offset = getattr(annotation, 'approved_entry_bar_offset', None)
    approved_entry_ts = getattr(annotation, 'approved_entry_ts', None)
    
    if approved_entry_offset is None:
        fails.append("APPROVED_ENTRY_MISSING")
        score -= 40
    
    if approved_entry_ts is None:
        fails.append("APPROVED_ENTRY_TS_INVALID")
        score -= 40
    else:
        # Try to parse timestamp
        try:
            pd.to_datetime(approved_entry_ts)
        except:
            fails.append("APPROVED_ENTRY_TS_INVALID")
            score -= 40
    
    # QC-030: Approved Exit Optional (v1)
    approved_exit_offset = getattr(annotation, 'approved_exit_bar_offset', None)
    if approved_exit_offset is None:
        warns.append("APPROVED_EXIT_MISSING")
        score -= 10
    
    # QC-040: Event Exists in Dataset
    if event_row is None:
        fails.append("EVENT_NOT_FOUND")
        score -= 40
    
    # QC-050: Time Consistency (only if we have valid data)
    if history_df is not None and not history_df.empty and approved_entry_ts and event_row is not None:
        try:
            entry_ts_parsed = pd.to_datetime(approved_entry_ts)
            event_time = pd.to_datetime(event_row.get('event_time'))
            
            # Normalize timezones
            if entry_ts_parsed.tz is not None:
                entry_ts_parsed = entry_ts_parsed.tz_localize(None)
            if event_time.tz is not None:
                event_time = event_time.tz_localize(None)
            
            history_min = history_df['open_time'].min()
            history_max = history_df['open_time'].max()
            
            if history_min.tz is not None:
                history_min = history_min.tz_localize(None)
            if history_max.tz is not None:
                history_max = history_max.tz_localize(None)
            
            # Time range checks
            if event_time < history_min or event_time > history_max:
                fails.append("TIME_RANGE_INVALID")
                score -= 40
            
            if entry_ts_parsed < event_time:
                fails.append("ENTRY_BEFORE_EVENT")
                score -= 40
            
            if entry_ts_parsed > history_max:
                fails.append("ENTRY_AFTER_HISTORY")
                score -= 40
        except Exception as e:
            warns.append(f"TIME_CONSISTENCY_CHECK_FAILED:{str(e)[:30]}")
            score -= 10
    
    # QC-060: Snap Distance Bound
    snap_distance_entry = getattr(annotation, 'snap_distance_entry', None)
    if snap_distance_entry is not None:
        if snap_distance_entry > 3:
            fails.append("SNAP_DISTANCE_TOO_LARGE")
            score -= 40
    else:
        warns.append("SNAP_META_MISSING")
        score -= 10
    
    # QC-070: Closed-Bar Sanity
    if history_df is not None and not history_df.empty and approved_entry_ts:
        try:
            entry_ts_parsed = pd.to_datetime(approved_entry_ts)
            if entry_ts_parsed.tz is not None:
                entry_ts_parsed = entry_ts_parsed.tz_localize(None)
            
            # Check if entry_ts is on a valid bar
            history_times = history_df['open_time'].copy()
            if history_times.dt.tz is not None:
                history_times = history_times.dt.tz_localize(None)
            
            if entry_ts_parsed not in history_times.values:
                # Check if within tolerance of a bar
                time_diffs = (history_times - entry_ts_parsed).abs()
                min_diff = time_diffs.min()
                
                # Tolerance: 1 minute for 15m, 5 minutes for 1h, 15 minutes for 4h
                tolerance_map = {"15m": pd.Timedelta(minutes=1), "1h": pd.Timedelta(minutes=5), "4h": pd.Timedelta(minutes=15)}
                tolerance = tolerance_map.get(annotation.timeframe, pd.Timedelta(minutes=5))
                
                if min_diff > tolerance:
                    warns.append("ENTRY_TS_NOT_ON_BAR")
                    score -= 10
        except Exception as e:
            warns.append(f"CLOSED_BAR_CHECK_FAILED:{str(e)[:30]}")
            score -= 10
    
    # Final verdict
    if fails or score < 60:
        qc_verdict = "FAIL"
    else:
        qc_verdict = "PASS"
    
    # Ensure score doesn't go negative
    score = max(0, score)
    
    return QCReport(
        symbol=annotation.symbol,
        timeframe=annotation.timeframe,
        event_id=annotation.event_id,
        qc_verdict=qc_verdict,
        score=score,
        fails=fails,
        warns=warns
    )


def run_for_symbol(symbol: str, timeframe: str) -> List[QCReport]:
    """
    Run QC for all APPROVED annotations for a symbol/timeframe.
    
    Args:
        symbol: Trading pair symbol
        timeframe: Timeframe (15m, 1h, 4h)
    
    Returns:
        List of QCReports
    """
    reports = []
    
    # Load annotations
    repo = SniperAnnotationRepository()
    annotations = repo.load_all(symbol, timeframe)
    
    if not annotations:
        return reports
    
    # Filter APPROVED annotations
    approved_anns = [ann for ann in annotations if getattr(ann, 'status', '') == 'APPROVED']
    
    # Load history
    history_file = coin_cell_paths.get_history_file(symbol, timeframe)
    if history_file.exists():
        history_df = pd.read_parquet(history_file)
        
        # Standardize column names
        if 'open_time' not in history_df.columns and 'timestamp' in history_df.columns:
            # Map timestamp (ms) to open_time
            history_df['open_time'] = pd.to_datetime(history_df['timestamp'], unit='ms', errors='coerce')
        elif 'open_time' in history_df.columns:
            # Ensure it is datetime (if it was ms int)
            history_df['open_time'] = pd.to_datetime(history_df['open_time'], unit='ms', errors='coerce')
    else:
        history_df = None
    
    # Load event dataset
    event_df = _load_event_dataset(symbol, timeframe)
    
    # Evaluate each annotation
    for ann in approved_anns:
        # Find matching event
        # Find matching event
        event_row = None
        if event_df is not None:
            # 1. Try Strict ID Match
            if 'event_id' in event_df.columns:
                event_matches = event_df[event_df['event_id'] == ann.event_id]
                if not event_matches.empty:
                    event_row = event_matches.iloc[0]
            
            # 2. Key Fallback: Match by Timestamp in ID
            if event_row is None and 'event_time' in event_df.columns:
                try:
                    # ID structure: SYMBOL_TF_TYPE_TIMESTAMP (e.g. ..._B_1709107200)
                    parts = ann.event_id.split('_')
                    ts_part = parts[-1]
                    
                    if ts_part.isdigit():
                        ts_val = int(ts_part)
                        # Detect precision (Seconds vs Ms)
                        # 2024 is ~1.7e9 (Seconds) or 1.7e12 (Ms)
                        is_ms = len(ts_part) > 10
                        
                        # Filter event_df
                        # Convert event_time to compatible int
                        # event_time is datetime64[ns], casting to int gives nanoseconds
                        if is_ms:
                            event_df_ts = event_df['event_time'].astype('int64') // 10**6 # ns to ms
                        else:
                            event_df_ts = event_df['event_time'].astype('int64') // 10**9 # ns to s
                            
                        # Find match
                        matches = event_df[event_df_ts == ts_val]
                        if not matches.empty:
                            event_row = matches.iloc[0]
                except Exception:
                    pass
        
        # Run QC
        report = evaluate(ann, event_row, history_df)
        
        # Add pointers
        report.pointers = {
            "annotation_path": str(repo._file_path(symbol, timeframe)),
            "history_path": str(history_file) if history_file.exists() else None,
            "event_dataset_path": _get_event_dataset_path(symbol, timeframe)
        }
        
        reports.append(report)
    
    return reports


def run_all(timeframes: List[str] = ["15m", "1h", "4h"], symbols: Optional[List[str]] = None) -> List[QCReport]:
    """
    Run QC for multiple timeframes and symbols.
    
    Args:
        timeframes: List of timeframes to process
        symbols: Optional list of symbols (if None, process all with annotations)
    
    Returns:
        List of all QCReports
    """
    all_reports = []
    
    # If symbols not specified, find all symbols with annotations
    if symbols is None:
        repo = SniperAnnotationRepository()
        symbols_set = set()
        for tf in timeframes:
            # Scan annotation directory
            ann_dir = Path(f"data/sniper")
            if ann_dir.exists():
                for symbol_dir in ann_dir.iterdir():
                    if symbol_dir.is_dir():
                        symbols_set.add(symbol_dir.name)
        symbols = list(symbols_set)
    
    # Run QC for each symbol/timeframe combination
    for symbol in symbols:
        for tf in timeframes:
            reports = run_for_symbol(symbol, tf)
            all_reports.extend(reports)
    
    return all_reports


def _load_event_dataset(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """Load event dataset for the given symbol/timeframe."""
    path = _get_event_dataset_path(symbol, timeframe)
    if path and Path(path).exists():
        try:
            df = pd.read_parquet(path)
            # Ensure event_time is datetime
            if 'event_time' in df.columns:
                df['event_time'] = pd.to_datetime(df['event_time'], errors='coerce')
                
                # Generate event_id if missing (for compatibility with legacy datasets)
                if 'event_id' not in df.columns and 'symbol' in df.columns:
                    # ID Format: SYMBOL_TF_YYYYMMDDHHMM (Standard Tezaver ID)
                    # Note: We use the passed 'timeframe' argument
                    df['event_id'] = df.apply(
                        lambda row: f"{row['symbol']}_{timeframe}_{row['event_time'].strftime('%Y%m%d%H%M')}", 
                        axis=1
                    )
            return df
        except:
            return None
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
