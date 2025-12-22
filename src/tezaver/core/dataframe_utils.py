"""
Dataframe utilities for Tezaver Mac.
"""
import pandas as pd
import streamlit as st

def ensure_open_time(df: pd.DataFrame) -> pd.DataFrame:
    """
    Guarantee df has an 'open_time' column usable for merges.
    
    Accepts:
      - df with 'open_time' already
      - df with 'open_ts' or 'timestamp' or 'ts' or 'date'
      - df with datetime/int index (converts to column if no other candidate found)
      
    Output:
      - df copy (not in-place) with 'open_time' column present
      - 'open_time' type normalized to naive datetime64[ns]
    """
    if df is None or df.empty:
        return df
        
    df = df.copy()
    
    # 1. Identify source column
    source_col = None
    candidates = ['open_time', 'open_ts', 'timestamp', 'ts', 'date', 'datetime']
    
    for col in candidates:
        if col in df.columns:
            source_col = col
            break
            
    # 2. If no column, check index
    if source_col is None:
        if isinstance(df.index, pd.DatetimeIndex):
            df['open_time'] = df.index
            source_col = 'open_time'
        else:
            # Last resort: if index looks like timestamp, try to use it
            return df

    # 3. Rename or Copy to 'open_time'
    if source_col != 'open_time':
        df['open_time'] = df[source_col]
        
    # 4. Normalize Type (Datetime, Naive)
    try:
        # Convert to datetime
        if not pd.api.types.is_datetime64_any_dtype(df['open_time']):
            df['open_time'] = pd.to_datetime(df['open_time'], errors='coerce')
            
        # Remove timezone if present (normalize to naive)
        if df['open_time'].dt.tz is not None:
             df['open_time'] = df['open_time'].dt.tz_localize(None)
             
    except Exception:
        pass
        
    return df

def safe_merge_features(df_bars: pd.DataFrame, df_feats: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Safely merge features into bars dataframe.
    Attempts:
    1. Exact merge on 'open_time'
    2. If exact leads to empty result (shouldn't happen on left merge unless bars empty) OR no matches:
       Attempt merge_asof if configured.
    
    Returns:
        (merged_df, diag_info_dict)
    """
    diag = {
        "bars_len": len(df_bars) if df_bars is not None else 0,
        "feats_len": len(df_feats) if df_feats is not None else 0,
        "merged_len": 0,
        "mode": "none",
        "msg": ""
    }
    
    if df_bars is None or df_bars.empty:
        diag["msg"] = "Bar data empty"
        return df_bars, diag
        
    # Normalize
    df_bars_norm = ensure_open_time(df_bars)
    
    if df_feats is None or df_feats.empty:
        diag["msg"] = "Features empty"
        return df_bars_norm, diag
        
    df_feats_norm = ensure_open_time(df_feats)
    
    # Check keys
    if 'open_time' not in df_bars_norm.columns or 'open_time' not in df_feats_norm.columns:
        diag["msg"] = "Missing open_time key"
        return df_bars_norm, diag
        
    # Sort for asof/merge safety
    df_bars_norm = df_bars_norm.sort_values('open_time')
    df_feats_norm = df_feats_norm.sort_values('open_time')
    
    # Select available columns
    cols = ['open_time']
    for c in ['rsi', 'rsi_ema']:
        if c in df_feats_norm.columns:
            cols.append(c)
            
    # Attempt 1: Exact Left Merge
    try:
        merged_exact = pd.merge(
            df_bars_norm,
            df_feats_norm[cols],
            on='open_time',
            how='left'
        )
        
        # Check if we actually matched anything? 
        # Left merge keeps all bar rows, but RSI keys might be null.
        match_count = merged_exact['rsi'].notna().sum() if 'rsi' in merged_exact.columns else 0
        diag["exact_matches"] = int(match_count)
        
        if match_count > 0:
            diag["merged_len"] = len(merged_exact)
            diag["mode"] = "exact"
            return merged_exact, diag
            
        # If no exact matches, try Asof
        # Fallthrough to Asof
        
    except Exception as e:
        diag["exact_err"] = str(e)
        
    # Attempt 2: Merge Asof
    try:
        merged_asof = pd.merge_asof(
            df_bars_norm,
            df_feats_norm[cols],
            on='open_time',
            direction='nearest',
            tolerance=pd.Timedelta("15m") # 15m tolerance
        )
        
        match_count_asof = merged_asof['rsi'].notna().sum() if 'rsi' in merged_asof.columns else 0
        diag["asof_matches"] = int(match_count_asof)
        
        if match_count_asof > 0:
            diag["merged_len"] = len(merged_asof)
            diag["mode"] = "asof"
            return merged_asof, diag
            
    except Exception as e:
        diag["asof_err"] = str(e)
        
    # Fallback: Return bars only (normalized)
    diag["merged_len"] = len(df_bars_norm)
    diag["mode"] = "fallback"
    diag["msg"] = "No features matched (exact or asof)"
    return df_bars_norm, diag
