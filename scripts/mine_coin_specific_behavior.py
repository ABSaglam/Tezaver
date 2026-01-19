"""
Coin-Specific Behavior Miner (Hyper-Personalization)
===================================================
Analyzes 2023-2025 successful rallies to find each coin's unique 
pre-rally signature (RSI, ATR, Vol Ratio).
"""

import sys
import os
import pandas as pd
import numpy as np
import json
import sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"
TRAIN_END = '2025-12-31'

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_pre_rally_state(symbol, start_time, df_1d):
    """gets the indicator values exactly 1 day before the rally start."""
    try:
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        # Find the last daily bar before the rally
        pre_idx = df_1d[df_1d['timestamp'] < start_ts].index
        
        if len(pre_idx) < 20: 
            return None
            
        row = df_1d.loc[pre_idx[-1]]
        
        return {
            'rsi': float(row['rsi']),
            'atr': float(row['atr']),
            'vol_ratio': float(row['vol_ratio']),
            'week_change': float(row['week_change'])
        }
    except Exception:
        return None

def mine_coin_profiles():
    print("=" * 80)
    print("🧠 COIN BEHAVIOR PROFILER START (2023-2025)")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)

    # 1. Load all training rallies
    conn = sqlite3.connect(DB_PATH)
    query = f"""
        SELECT symbol, tier, event_time, raw_data FROM rallies 
        WHERE event_time <= '{TRAIN_END}'
        AND tier IN ('DIAMOND', 'GOLD', 'SILVER')
    """
    df_rallies = pd.read_sql_query(query, conn)
    conn.close()

    print(f"Loaded {len(df_rallies)} rallies for analysis.")

    profiles = {}

    for i, symbol in enumerate(DEFAULT_COINS, 1):
        if i % 50 == 0:
            print(f"Processing: {i}/{len(DEFAULT_COINS)}...")

        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists():
            continue

        # Load and prep 1d indicators
        df_1d = pd.read_parquet(path_1d).sort_values('timestamp').reset_index(drop=True)
        df_1d['rsi'] = calculate_rsi(df_1d['close'])
        df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
        df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
        df_1d['week_change'] = df_1d['close'].pct_change(7) * 100
        df_1d['atr'] = (df_1d['high'] - df_1d['low']) / df_1d['close'] * 100
        
        coin_rallies = df_rallies[df_rallies['symbol'] == symbol]
        if coin_rallies.empty:
            continue

        success_states = []
        for _, row in coin_rallies.iterrows():
            raw = json.loads(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
            state = get_pre_rally_state(symbol, raw['start_time'], df_1d)
            if state:
                state['tier'] = row['tier']
                success_states.append(state)

        if not success_states:
            continue

        # Analysis per coin
        ss_df = pd.DataFrame(success_states)
        
        profiles[symbol] = {
            'sample_size': len(ss_df),
            'rsi': {
                'min': float(ss_df['rsi'].min()),
                'max': float(ss_df['rsi'].max()),
                'median': float(ss_df['rsi'].median()),
                'q25': float(ss_df['rsi'].quantile(0.25)),
                'q75': float(ss_df['rsi'].quantile(0.75))
            },
            'atr': {
                'min': float(ss_df['atr'].min()),
                'median': float(ss_df['atr'].median()),
                'q25': float(ss_df['atr'].quantile(0.25))
            },
            'vol_ratio': {
                'min': float(ss_df['vol_ratio'].min()),
                'median': float(ss_df['vol_ratio'].median()),
                'q25': float(ss_df['vol_ratio'].quantile(0.25))
            },
            'tier_distribution': ss_df['tier'].value_counts().to_dict()
        }

    # Save
    output_path = coin_cell_paths.get_library_root() / "coin_behavior_profiles.json"
    with open(output_path, 'w') as f:
        json.dump(profiles, f, indent=2)

    print("\n✅ PROFILES COMPLETED")
    print(f"Saved to: {output_path}")
    print(f"Total coins profiled: {len(profiles)}")

if __name__ == "__main__":
    mine_coin_profiles()
