"""
GÖZCÜ Rally Detection Engine

Hierarchical top-down rally filtering system:
1. 4h rallies = Master timeline (ana dalgalar)
2. 1h rallies = Filtered to only exist within 4h windows
3. 15m rallies = Filtered to only exist within 1h windows

Philosophy: Focus on rallies that occur during larger trend movements for better context.
"""

import pandas as pd
from typing import Tuple, Optional
from datetime import timedelta


# Timeframe bar deltas
TF_DELTAS = {
    '4h': timedelta(hours=4),
    '1h': timedelta(hours=1),
    '15m': timedelta(minutes=15)
}


def calculate_rally_end_time(rally: pd.Series, timeframe: str) -> pd.Timestamp:
    """
    Calculate rally end time based on event_time + bars_to_peak.
    
    Args:
        rally: Rally row with event_time and bars_to_peak
        timeframe: '4h', '1h', or '15m'
    
    Returns:
        End timestamp of the rally
    """
    start_time = pd.to_datetime(rally['event_time'])
    bars = int(rally['bars_to_peak'])
    delta = TF_DELTAS[timeframe]
    
    return start_time + (delta * bars)


def is_within_window(
    child_time: pd.Timestamp,
    parent_start: pd.Timestamp,
    parent_end: pd.Timestamp
) -> bool:
    """
    Check if child rally starts within parent rally window.
    
    Args:
        child_time: Child rally event_time
        parent_start: Parent rally start time
        parent_end: Parent rally end time
    
    Returns:
        True if child is within parent window
    """
    return parent_start <= child_time <= parent_end


def filter_rallies_by_parent_windows(
    child_rallies: pd.DataFrame,
    parent_rallies: pd.DataFrame,
    parent_tf: str,
    child_tf: str,
    parent_id_col: str = 'parent_rally_id',
    parent_start_col: str = 'parent_rally_start'
) -> pd.DataFrame:
    """
    Filter child rallies to only those within parent rally windows.
    Also adds parent_rally_id and parent_rally_start columns.
    
    Args:
        child_rallies: Child timeframe rallies
        parent_rallies: Parent timeframe rallies
        parent_tf: Parent timeframe ('4h' or '1h')
        child_tf: Child timeframe ('1h' or '15m')
        parent_id_col: Column name for parent ID
        parent_start_col: Column name for parent start time
    
    Returns:
        Filtered child rallies with parent linking
    """
    if child_rallies.empty or parent_rallies.empty:
        return pd.DataFrame()
    
    # Ensure datetime
    child_rallies = child_rallies.copy()
    parent_rallies = parent_rallies.copy()
    
    child_rallies['event_time'] = pd.to_datetime(child_rallies['event_time'])
    parent_rallies['event_time'] = pd.to_datetime(parent_rallies['event_time'])
    
    # Add index to parent rallies for ID assignment
    parent_rallies = parent_rallies.reset_index(drop=True)
    parent_rallies['_parent_id'] = parent_rallies.index
    
    # Filter and link
    filtered_rows = []
    
    for idx, child in child_rallies.iterrows():
        child_time = child['event_time']
        
        # Find parent window containing this child
        parent_match = None
        
        for _, parent in parent_rallies.iterrows():
            parent_start = parent['event_time']
            parent_end = calculate_rally_end_time(parent, parent_tf)
            
            if is_within_window(child_time, parent_start, parent_end):
                parent_match = parent
                break  # Take first matching parent
        
        # Include only if parent found
        if parent_match is not None:
            child_copy = child.copy()
            child_copy[parent_id_col] = int(parent_match['_parent_id'])
            child_copy[parent_start_col] = parent_match['event_time']
            filtered_rows.append(child_copy)
    
    if not filtered_rows:
        return pd.DataFrame()
    
    result = pd.DataFrame(filtered_rows)
    return result.reset_index(drop=True)


def build_hierarchical_rallies(
    rallies_4h: pd.DataFrame,
    rallies_1h: pd.DataFrame,
    rallies_15m: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build hierarchical rally structure with parent-child linking.
    
    Process:
    1. Keep all 4h rallies (master timeline)
    2. Filter 1h → only those within 4h windows + add parent_4h_id
    3. Filter 15m → only those within 1h windows + add parent_1h_id + parent_4h_id
    
    Args:
        rallies_4h: 4h rallies (master)
        rallies_1h: 1h rallies (to be filtered)
        rallies_15m: 15m rallies (to be filtered)
    
    Returns:
        Tuple of (4h_rallies, filtered_1h, filtered_15m) with parent links
    """
    # Step 1: 4h rallies remain unchanged (master timeline)
    rallies_4h_out = rallies_4h.copy() if not rallies_4h.empty else pd.DataFrame()
    
    # Step 2: Filter 1h rallies within 4h windows
    rallies_1h_filtered = filter_rallies_by_parent_windows(
        child_rallies=rallies_1h,
        parent_rallies=rallies_4h,
        parent_tf='4h',
        child_tf='1h',
        parent_id_col='parent_4h_rally_id',
        parent_start_col='parent_4h_rally_start'
    )
    
    # Step 3: Filter 15m rallies within 1h windows (the filtered 1h)
    rallies_15m_filtered = filter_rallies_by_parent_windows(
        child_rallies=rallies_15m,
        parent_rallies=rallies_1h_filtered,
        parent_tf='1h',
        child_tf='15m',
        parent_id_col='parent_1h_rally_id',
        parent_start_col='parent_1h_rally_start'
    )
    
    # Step 4: Add indirect 4h parent link to 15m rallies
    if not rallies_15m_filtered.empty and 'parent_1h_rally_id' in rallies_15m_filtered.columns:
        # For each 15m rally, find its 1h parent's 4h parent
        parent_4h_ids = []
        parent_4h_starts = []
        
        for _, rally_15m in rallies_15m_filtered.iterrows():
            parent_1h_id = rally_15m['parent_1h_rally_id']
            
            # Find the 1h rally with this ID
            parent_1h = rallies_1h_filtered[rallies_1h_filtered.index == parent_1h_id]
            
            if not parent_1h.empty:
                parent_4h_id = parent_1h.iloc[0].get('parent_4h_rally_id', None)
                parent_4h_start = parent_1h.iloc[0].get('parent_4h_rally_start', None)
            else:
                parent_4h_id = None
                parent_4h_start = None
            
            parent_4h_ids.append(parent_4h_id)
            parent_4h_starts.append(parent_4h_start)
        
        rallies_15m_filtered['parent_4h_rally_id'] = parent_4h_ids
        rallies_15m_filtered['parent_4h_rally_start'] = parent_4h_starts
    
    return rallies_4h_out, rallies_1h_filtered, rallies_15m_filtered


def get_gozcu_statistics(
    rallies_4h_orig: pd.DataFrame,
    rallies_1h_orig: pd.DataFrame,
    rallies_15m_orig: pd.DataFrame,
    rallies_4h_filtered: pd.DataFrame,
    rallies_1h_filtered: pd.DataFrame,
    rallies_15m_filtered: pd.DataFrame
) -> dict:
    """
    Generate statistics comparing GÖZCÜ filtered vs original rallies.
    
    Returns:
        Dict with counts, averages, retention rates
    """
    stats = {
        '4h': {
            'original': len(rallies_4h_orig),
            'filtered': len(rallies_4h_filtered),
            'retention_pct': 100.0  # 4h always 100%
        },
        '1h': {
            'original': len(rallies_1h_orig),
            'filtered': len(rallies_1h_filtered),
            'retention_pct': (len(rallies_1h_filtered) / len(rallies_1h_orig) * 100) if len(rallies_1h_orig) > 0 else 0
        },
        '15m': {
            'original': len(rallies_15m_orig),
            'filtered': len(rallies_15m_filtered),
            'retention_pct': (len(rallies_15m_filtered) / len(rallies_15m_orig) * 100) if len(rallies_15m_orig) > 0 else 0
        }
    }
    
    # Calculate average gains
    for tf, df_orig, df_filt in [
        ('15m', rallies_15m_orig, rallies_15m_filtered),
        ('1h', rallies_1h_orig, rallies_1h_filtered),
        ('4h', rallies_4h_orig, rallies_4h_filtered)
    ]:
        if not df_orig.empty and 'future_max_gain_pct' in df_orig.columns:
            stats[tf]['avg_gain_orig'] = df_orig['future_max_gain_pct'].mean() * 100
        else:
            stats[tf]['avg_gain_orig'] = 0
        
        if not df_filt.empty and 'future_max_gain_pct' in df_filt.columns:
            stats[tf]['avg_gain_filtered'] = df_filt['future_max_gain_pct'].mean() * 100
        else:
            stats[tf]['avg_gain_filtered'] = 0
    
    return stats
