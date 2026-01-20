"""
Database Helper - Safe Connection Management
============================================
Prevents database locks and ensures connections are always closed.
Updated: 2026 data filtering for test holdout.
"""

import sqlite3
from contextlib import contextmanager
from datetime import date

# TRAIN DATA CUTOFF: Only use data up to 2025-12-31
# 2026 data (Jan 1-19) is held out for testing
TRAIN_CUTOFF = date(2026, 1, 1)

@contextmanager
def safe_db_connection(db_path='library/rallies.db', timeout=30.0):
    """
    Safe database connection with automatic cleanup.
    
    Usage:
        with safe_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")
            # Connection auto-closes even if error occurs
    
    Args:
        db_path: Path to database file
        timeout: Seconds to wait if database is locked
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=timeout)
        yield conn
    finally:
        if conn:
            conn.close()

def get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True):
    """
    Safely fetch rallies for a symbol.
    
    Args:
        symbol: Coin symbol (e.g. 'AAVEUSDT')
        tiers: List of tiers to include
        train_only: If True, filter out 2026 data (test holdout)
    
    Returns:
        Dictionary mapping dates to (tier, gain) tuples
    """
    import json
    import pandas as pd
    
    with safe_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(tiers))
        query = f"SELECT raw_data, tier FROM rallies WHERE symbol = ? AND tier IN ({placeholders})"
        cursor.execute(query, [symbol] + tiers)
        
        results = {}
        for raw_data, tier in cursor.fetchall():
            raw = json.loads(raw_data)
            # Support both legacy 'start_time' and new 'event_time'
            start_str = raw.get('start_time') or raw.get('event_time')
            if not start_str:
                continue # Skip if no date found
                
            start_date = pd.to_datetime(start_str).date()
            
            # Filter 2026 data if train_only=True
            if train_only and start_date >= TRAIN_CUTOFF:
                continue
            
            gain = raw.get('gain')
            if gain is None:
                 if 'impulse_gain_pct' in raw:
                     gain = raw['impulse_gain_pct'] * 100
                 else:
                     gain = 0.0 # Default fallback
            results[start_date] = (tier, gain)
        
        return results
