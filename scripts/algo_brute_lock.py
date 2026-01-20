
import sys
import os
import pandas as pd
import numpy as np
import itertools

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ALGOUSDT'
    print(f"🔒 FINAL BRUTE LOCK: {symbol}")
    print("="*70)

    # 1. Load Data
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    if not os.path.exists(h4_path):
        print("❌ 4H Data not found")
        return
        
    df = pd.read_parquet(h4_path)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # 2. Features
    df['rsi'] = 100 - (100 / (1 + (df['close'].diff().where(df['close'].diff() > 0, 0).rolling(14).mean() / (-df['close'].diff().where(df['close'].diff() < 0, 0).rolling(14).mean()))))
    df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    df['ema_21'] = df['close'].ewm(span=21).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    df['trend'] = (df['ema_21'] / df['ema_50'] - 1) * 100
    df['hour'] = df['datetime'].dt.hour
    
    # ATR
    df['tr'] = np.maximum(df['high'] - df['low'], abs(df['close'].shift(1) - df['close']))
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_ratio'] = df['atr'] / df['close'] * 100
    
    # 3. Target Mapping (DEBUGGED)
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    rally_dates = set(rally_results.keys()) # These are datetime.date objects
    
    # We want to check signals that happen:
    # A) On the Start of Rally Day (00:00)
    # B) On the Day Before Rally (Preparation)
    
    # Let's verify type
    sample_key = next(iter(rally_dates))
    print(f"Rally Date Type: {type(sample_key)}") # Expected: datetime.date
    
    # Map 'is_today_rally'
    df['date'] = df['datetime'].dt.date
    df['is_today_rally'] = df['date'].isin(rally_dates)
    
    # Map 'is_tomorrow_rally'
    df['next_date'] = (df['datetime'] + pd.Timedelta(days=1)).dt.date
    df['is_tomorrow_rally'] = df['next_date'].isin(rally_dates)
    
    # We will filter for Midnight candles
    midnight = df[df['hour'] == 0].copy().reset_index(drop=True)
    
    # Target: Either Today OR Tomorrow is a rally.
    # We want a lock state that precedes a rally.
    midnight['target'] = midnight['is_today_rally'] # | midnight['is_tomorrow_rally']
    # Let's stick to "Today is Rally" for now (00:00 check for that day)
    
    print(f"Total Midnight Candles: {len(midnight)}")
    print(f"Total Targets: {midnight['target'].sum()}")
    
    # 4. SCORCHED EARTH BRUTE FORCE
    # We will search for any range [min, max] of indicators that captures at least 1 rally with 0 failures.
    
    best_perf = (0, 0) # (precision, hits)
    best_rule = ""
    
    # Variables to sweep
    # We iterate thresholds.
    
    # RSI: Lower Bound
    rsi_mins = [30, 40, 50, 60, 65, 70]
    # Trend: Lower Bound
    trend_mins = [-5, 0, 5, 10, 20]
    # Vol: Upper Bound (Quiet) OR Lower Bound (Chaos)
    # Let's try "Quiet" first (Vol <= X)
    vol_maxs = [1.5, 2.0, 3.0, 5.0]
    # ATR: Upper Bound (Squeeze)
    atr_maxs = [2.0, 3.0, 5.0, 100]
    
    print("Searching Quiet Lock...")
    for r, t, v, a in itertools.product(rsi_mins, trend_mins, vol_maxs, atr_maxs):
        mask = (
            (midnight['rsi'] >= r) &
            (midnight['trend'] >= t) &
            (midnight['vol_ratio'] <= v) &
            (midnight['atr_ratio'] <= a)
        )
        h = midnight[mask & midnight['target']].shape[0]
        f = midnight[mask & ~midnight['target']].shape[0]
        total = h + f
        
        if total > 0:
            prec = h / total * 100
            if prec > best_perf[0] and h > 0:
                best_perf = (prec, h)
                best_rule = f"QUIET: RSI>={r} Trend>={t} Vol<={v} ATR<={a}"
                if prec == 100:
                    print(f"💎 FOUND 100%: {best_rule} ({h}/{total})")
    
    # Chaos Search (Vol >= X)
    print("Searching Chaos Lock...")
    vol_mins = [1.5, 2.0, 3.0, 5.0]
    for r, t, v in itertools.product(rsi_mins, trend_mins, vol_mins):
        mask = (
            (midnight['rsi'] >= r) &
            (midnight['trend'] >= t) &
            (midnight['vol_ratio'] >= v)
        )
        h = midnight[mask & midnight['target']].shape[0]
        f = midnight[mask & ~midnight['target']].shape[0]
        total = h + f
        
        if total > 0:
            prec = h / total * 100
            if prec > best_perf[0] and h > 0:
                best_perf = (prec, h)
                best_rule = f"CHAOS: RSI>={r} Trend>={t} Vol>={v}"
                if prec == 100:
                     print(f"💎 FOUND 100%: {best_rule} ({h}/{total})")
                     
    print("\n" + "="*70)
    print(f"🏆 FINAL RESULT: {best_rule}")
    print(f"   Precision: {best_perf[0]:.1f}% (Hits: {best_perf[1]})")

if __name__ == "__main__":
    main()
