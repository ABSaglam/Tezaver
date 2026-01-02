"""
Simyacı Data Access Layer
==========================
"Cerrah Protokolü: Temporal Leakage = Ölümcül Hata"

This module provides SAFE data access for Simyacı feature extraction.
The primary defense against temporal leakage (future data contamination).

CRITICAL RULE: Never expose data beyond T-0 (rally start time).
"""

from typing import Optional, Dict, Any
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

from tezaver.core.rally_store import RallyStore
from tezaver.core import coin_cell_paths
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


class TemporalLeakageError(Exception):
    """Raised when future data is detected in context."""
    pass


def get_rally_context(
    rally_id: str,
    lookback_bars: int = 60,
    strict_mode: bool = True
) -> pd.DataFrame:
    """
    Get safe historical context for a rally (T-60 → T-0).
    
    **TEMPORAL LEAKAGE PROTECTION:**
    - Returns ONLY data from [T-lookback] to [T-0]
    - T-0 = Rally start time (event_time)
    - Future data (T+1, T+2, ...) is NEVER included
    
    Args:
        rally_id: Unique rally identifier
        lookback_bars: Number of bars before rally start (default: 60)
        strict_mode: If True, raise error on any T+future detection
        
    Returns:
        DataFrame with OHLCV + indicators from T-60 to T-0
        
    Raises:
        TemporalLeakageError: If future data detected in strict mode
        ValueError: If rally not found or data unavailable
        
    Example:
        >>> context = get_rally_context("BTCUSDT_15m_D_1735891200", lookback_bars=60)
        >>> assert context.index.max() <= rally_start_time  # Safety check
    """
    # 1. Load Rally Metadata
    store = RallyStore()
    rally_doc = store.get_rally(rally_id)
    
    if not rally_doc:
        raise ValueError(f"Rally not found: {rally_id}")
    
    raw_data = rally_doc.get('raw_data', {}) or {}
    
    symbol = rally_doc['symbol']
    timeframe = rally_doc['timeframe']
    event_time = rally_doc['event_time']
    
    # Convert to Timestamp if string
    if isinstance(event_time, str):
        event_time = pd.Timestamp(event_time)
    
    # Localize to UTC if naive
    if event_time.tz is None:
        event_time = event_time.tz_localize('UTC')
    
    logger.info(f"Loading context for {rally_id}: symbol={symbol}, tf={timeframe}, T-0={event_time}")
    
    # 2. Load Historical Price Data
    # CRITICAL FIX: Use correct path helper function
    tf_file = coin_cell_paths.get_history_file(symbol, timeframe)
    
    if not tf_file.exists():
        raise ValueError(f"Price data not found: {tf_file}")
    
    df_full = pd.read_parquet(tf_file)
    
    # Ensure proper datetime index
    # Price files have 'datetime' column (already formatted) OR 'timestamp' column (unix ms)
    if 'datetime' in df_full.columns:
        df_full['datetime'] = pd.to_datetime(df_full['datetime'])
        df_full = df_full.set_index('datetime')
    elif 'timestamp' in df_full.columns:
        # Timestamp is in milliseconds (unix epoch)
        df_full['datetime'] = pd.to_datetime(df_full['timestamp'], unit='ms')
        df_full = df_full.set_index('datetime')
    
    df_full = df_full.sort_index()
    
    # 3. CRITICAL: Slice to T-0 Boundary
    # Find the exact bar at or before event_time
    valid_bars = df_full[df_full.index <= event_time]
    
    if len(valid_bars) == 0:
        raise ValueError(f"No historical data before event_time {event_time}")
    
    # Get T-0 position
    t0_idx = len(valid_bars) - 1
    t0_timestamp = valid_bars.index[t0_idx]
    
    # Slice context window: [T-lookback, T-0]
    start_idx = max(0, t0_idx - lookback_bars + 1)
    context_window = valid_bars.iloc[start_idx:t0_idx + 1].copy()
    
    # 4. SAFETY CHECK: Verify No Future Data
    max_timestamp = context_window.index.max()
    
    if max_timestamp > event_time:
        error_msg = (
            f"TEMPORAL LEAKAGE DETECTED! "
            f"Context contains future data: max={max_timestamp}, T-0={event_time}"
        )
        logger.error(error_msg)
        
        if strict_mode:
            raise TemporalLeakageError(error_msg)
        else:
            logger.warning("Strict mode OFF - proceeding with caution")
    
    # 5. Log Safety Verification
    logger.info(
        f"Context safe: {len(context_window)} bars, "
        f"range=[{context_window.index.min()} → {max_timestamp}], "
        f"T-0={event_time}, "
        f"gap={(event_time - max_timestamp).total_seconds()}s"
    )
    
    return context_window


def validate_no_future_data(rally_id: str, context: pd.DataFrame) -> bool:
    """
    Audit function: Verify context contains no future data.
    
    This is a TEST/VALIDATION function for the Surgeon Protocol.
    Should be called in unit tests and periodic audits.
    
    Args:
        rally_id: Rally ID to validate
        context: DataFrame returned by get_rally_context()
        
    Returns:
        True if safe, False if future data detected
        
    Example:
        >>> context = get_rally_context(rally_id)
        >>> assert validate_no_future_data(rally_id, context)
    """
    store = RallyStore()
    rally_doc = store.get_rally(rally_id)
    
    if not rally_doc:
        logger.error(f"Rally not found for validation: {rally_id}")
        return False
    
    event_time = rally_doc['event_time']
    if isinstance(event_time, str):
        event_time = pd.Timestamp(event_time)
    
    max_context_time = context.index.max()
    
    if max_context_time > event_time:
        logger.error(
            f"VALIDATION FAILED: {rally_id} - "
            f"Future data detected: context_max={max_context_time}, T-0={event_time}"
        )
        return False
    
    logger.info(f"VALIDATION PASSED: {rally_id} - No future data")
    return True


# Convenience function for batch loading
def get_rally_contexts_batch(
    rally_ids: list,
    lookback_bars: int = 60,
    strict_mode: bool = True
) -> Dict[str, pd.DataFrame]:
    """
    Load contexts for multiple rallies.
    
    Fails fast on first error if strict_mode=True.
    """
    contexts = {}
    
    for rally_id in rally_ids:
        try:
            contexts[rally_id] = get_rally_context(
                rally_id, 
                lookback_bars=lookback_bars,
                strict_mode=strict_mode
            )
        except Exception as e:
            logger.error(f"Failed to load context for {rally_id}: {e}")
            if strict_mode:
                raise
            
    return contexts
