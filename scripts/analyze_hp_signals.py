import pandas as pd
import numpy as np
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict

from tezaver.core import config, coin_cell_paths
from tezaver.mining.daily_radar_engine import DailyRadarEngine
from tezaver.core.rally_store import RallyStore

class HPCorrellator:
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.engine = DailyRadarEngine()
        self.store = RallyStore()

    def analyze_signals(self, days_back: int = 730):
        all_samples = []
        total_coins = len(self.symbols)
        
        for i, symbol in enumerate(self.symbols):
            if i % 50 == 0:
                print(f"[{i}/{total_coins}] Extracting features for {symbol}...")
            
            samples = self.extract_symbol_features(symbol, days_back)
            all_samples.extend(samples)
            
        return pd.DataFrame(all_samples)

    def extract_symbol_features(self, symbol: str, days_back: int):
        # 1. Load Ground Truth Rallies
        db_rallies = self.store.list_rallies(symbol=symbol, timeframe='15m')
        rally_map = {}
        for r in db_rallies:
            t = pd.Timestamp(r['event_time']).tz_localize(None)
            archetype = (r.get('molder_data') or {}).get('archetype', 'UNKNOWN')
            rally_map[t] = {"tier": r.get('tier', 'C'), "arch": archetype}
        rally_times = sorted(rally_map.keys())

        # 2. Load OHLCV
        path_1d = coin_cell_paths.get_history_file(symbol, "1d")
        path_4h = coin_cell_paths.get_history_file(symbol, "4h")
        if not path_1d.exists() or not path_4h.exists(): return []

        try:
            df_1d = pd.read_parquet(path_1d)
            df_1d['datetime'] = df_1d['datetime'].dt.tz_localize(None)
            df_4h = pd.read_parquet(path_4h)
            df_4h['datetime'] = df_4h['datetime'].dt.tz_localize(None)
        except: return []

        if len(df_1d) < 30: return []

        # 3. Calculate Indicators
        def calculate_rsi(series, period=14):
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            return 100 - (100 / (1 + (gain / loss.replace(0, 0.001))))

        df_1d['tr'] = np.maximum(df_1d['high'] - df_1d['low'], 
                                np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), 
                                           abs(df_1d['low'] - df_1d['close'].shift(1))))
        df_1d['atr_pct'] = (df_1d['tr'].rolling(14).mean() / df_1d['close']) * 100
        df_1d['high_5d'] = df_1d['high'].rolling(5).max()
        df_1d['low_5d'] = df_1d['low'].rolling(5).min()
        df_1d['mid_pct'] = (df_1d['close'] - df_1d['low_5d']) / (df_1d['high_5d'] - df_1d['low_5d']) * 100
        df_1d['bb_width'] = (df_1d['close'].rolling(20).std() * 4) / df_1d['close'].rolling(20).mean() * 100
        df_1d['bb_squeeze_val'] = df_1d['bb_width'] / df_1d['bb_width'].rolling(20).min()
        
        df_4h['rsi_4h'] = calculate_rsi(df_4h['close'])
        df_4h_daily = df_4h.copy()
        df_4h_daily['day_ts'] = df_4h_daily['datetime'].dt.floor('D')
        df_4h_daily = df_4h_daily.groupby('day_ts')['rsi_4h'].last().reset_index()

        df_merged = df_1d.merge(df_4h_daily[['day_ts', 'rsi_4h']], left_on='datetime', right_on='day_ts', how='inner')
        test_start = df_merged['datetime'].max() - timedelta(days=days_back)
        df_test = df_merged[df_merged['datetime'] >= test_start].copy()

        dna = self.engine.dna_profiles.get(symbol, {"tier": "C"})
        coin_tier = dna.get('tier', 'C')

        samples = []
        for idx, row in df_test.iterrows():
            # Label as HIT if rally within 72h
            window_start = row['datetime']
            window_end = row['datetime'] + timedelta(hours=72)
            
            is_hit = False
            hit_tier = None
            hit_arch = None
            for r_time in rally_times:
                if window_start <= r_time <= window_end:
                    is_hit = True
                    hit_tier = rally_map[r_time]['tier']
                    hit_arch = rally_map[r_time]['arch']
                    break
            
            # Drawdown check
            df_4h_win = df_4h[(df_4h['datetime'] >= window_start) & (df_4h['datetime'] <= window_end)]
            max_dd = 0
            if not df_4h_win.empty:
                max_dd = (df_4h_win['low'].min() - row['close']) / row['close'] * 100

            samples.append({
                "symbol": symbol,
                "tier": coin_tier,
                "atr_pct": row['atr_pct'],
                "mid_pct": row['mid_pct'],
                "bb_squeeze": row['bb_squeeze_val'],
                "rsi_4h": row['rsi_4h'],
                "is_hit": is_hit,
                "hit_tier": hit_tier,
                "hit_arch": hit_arch,
                "max_dd": max_dd
            })
            
        return samples

if __name__ == "__main__":
    correlator = HPCorrellator(config.DEFAULT_COINS)
    df = correlator.analyze_signals(days_back=730)
    
    # Save for deeper analysis
    df.to_parquet("analysis/signal_correlation_data.parquet")
    print(f"Extracted {len(df)} signal samples for analysis.")
    
    # Simple win rate by DNA tier
    print("\n[Baseline Win Rate by DNA Tier]")
    print(df.groupby('tier')['is_hit'].mean().sort_values(ascending=False))
    
    # Correlation of technicals with success
    print("\n[Feature Correlation with is_hit]")
    numeric_df = df.select_dtypes(include=[np.number, bool])
    print(numeric_df.corr()['is_hit'].sort_values(ascending=False))
