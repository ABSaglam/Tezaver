"""
Enrich History with GEN-RADAR Status
=====================================
Processes 2 years of 1D history for all coins and appends:
- radar_category (TREND, NINJA, BREAKOUT, WATCH, or NONE)
- radar_score (0-100)
"""

import pandas as pd
import numpy as np
import json
import os
from pathlib import Path
from tezaver.core import coin_cell_paths
from tezaver.mining.daily_radar_engine import DailyRadarEngine

def enrich_all_coins():
    print("=== 🧪 GEN-RADAR HISTORY ENRICHMENT STARTED ===")
    
    engine = DailyRadarEngine()
    
    # Load DNA
    try:
        with open('library/coin_dna_definitive.json', 'r') as f:
            dna_profiles = {p['symbol']: p for p in json.load(f)}
    except:
        print("Error: DNA record not found.")
        return

    # Get all coins from coin_cells directory
    coin_cells_dir = Path("/Users/alisaglam/TezaverMac/coin_cells")
    coins = [d.name for d in coin_cells_dir.iterdir() if d.is_dir()]
    
    total_coins = len(coins)
    print(f"Total coins to process: {total_coins}")

    for idx, symbol in enumerate(coins):
        if idx % 20 == 0:
            print(f"Processing ({idx}/{total_coins}): {symbol}")
            
        dna = dna_profiles.get(symbol)
        if not dna:
            continue
            
        try:
            # 1. Load Data
            path_1d = coin_cell_paths.get_history_file(symbol, "1d")
            path_4h = coin_cell_paths.get_history_file(symbol, "4h")
            if idx == 0:
                print(f"DEBUG: path_1d={path_1d}, exists={path_1d.exists()}")
            if not path_1d.exists() or not path_4h.exists(): continue
            
            df_1d = pd.read_parquet(path_1d)
            df_4h = pd.read_parquet(path_4h)
            
            if len(df_1d) < 40 or len(df_4h) < 100: continue
            
            # Clean up old columns if they exist to avoid confusion
            for col in ['radar_category', 'radar_score']:
                if col in df_1d.columns:
                    df_1d = df_1d.drop(columns=[col])

            # 2. Vectorized Indicator Pre-calculation for 1D
            # (Mimicking DailyRadarEngine.calculate_daily_structure)
            # ATR
            high, low, close = df_1d['high'], df_1d['low'], df_1d['close']
            tr = np.maximum(high - low, np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))))
            df_1d['atr_val'] = tr.rolling(14).mean()
            df_1d['atr_pct'] = (df_1d['atr_val'] / close) * 100
            
            # Midpoint
            df_1d['h_5d'] = high.rolling(5).max()
            df_1d['l_5d'] = low.rolling(5).min()
            df_1d['midpoint_pct'] = ((close - df_1d['l_5d']) / (df_1d['h_5d'] - df_1d['l_5d'])) * 100
            
            # BB Squeeze
            df_1d['sma20'] = close.rolling(20).mean()
            df_1d['std20'] = close.rolling(20).std()
            df_1d['bb_width'] = (df_1d['std20'] * 4) / df_1d['sma20'] * 100
            df_1d['bb_squeeze'] = df_1d['bb_width'] < (df_1d['bb_width'].rolling(100).mean() * 0.8)
            
            # Resistance
            df_1d['near_res'] = close > (df_1d['h_5d'] * 0.98)
            
            # Green Days
            df_1d['is_green'] = close > df_1d['open']
            df_1d['green_days'] = df_1d['is_green'].rolling(3).sum()

            # 3. Vectorized Indicators for 4H
            # (Mimicking DailyRadarEngine.calculate_4h_momentum)
            delta = df_4h['close'].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=13, adjust=False).mean()
            ema_down = down.ewm(com=13, adjust=False).mean()
            df_4h['rsi_val'] = 100 - (100 / (1 + (ema_up / ema_down)))
            df_4h['rsi_rising'] = df_4h['rsi_val'] > df_4h['rsi_val'].shift(6)
            
            ema12 = df_4h['close'].ewm(span=12, adjust=False).mean()
            ema26 = df_4h['close'].ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            sig = macd.ewm(span=9, adjust=False).mean()
            df_4h['macd_hist'] = macd - sig
            df_4h['macd_positive'] = df_4h['macd_hist'] > 0
            df_4h['macd_rising'] = df_4h['macd_hist'] > df_4h['macd_hist'].shift(3)
            df_4h['is_green'] = df_4h['close'] > df_4h['open']
            df_4h['green_bars'] = df_4h['is_green'].rolling(3).sum()

            # Prepare for merging 4H data into 1D days
            df_1d['dt_key'] = pd.to_datetime(df_1d['datetime']).dt.date
            df_4h['dt_key'] = pd.to_datetime(df_4h['datetime']).dt.date
            
            # Take the LAST 4H bar of each day
            df_4h_daily = df_4h.groupby('dt_key').last().reset_index()
            
            # Merge
            df_merged = pd.merge(df_1d, df_4h_daily[['dt_key', 'rsi_val', 'rsi_rising', 'macd_positive', 'macd_hist', 'macd_rising', 'green_bars']], on='dt_key', how='left')

            # 4. Final Iterative Categorization (Using Engine Logic)
            categories = []
            scores = []
            
            # We must wrap metrics in a class-like object if we want to reuse engine methods,
            # or just call functions if we make them standalone. 
            # For speed, we apply logic directly here.
            
            for i, row in df_merged.iterrows():
                if pd.isna(row['rsi_val']) or pd.isna(row['atr_pct']) or pd.isna(row['midpoint_pct']):
                    categories.append("NONE")
                    scores.append(0)
                    continue
                
                # Create dummy metric objects to reuse engine filters if needed
                from tezaver.mining.daily_radar_engine import DailyMetrics, MomentumMetrics
                
                # Handle NaNs and types
                g_bars = 0 if pd.isna(row['green_bars']) else int(row['green_bars'])
                g_days = 0 if pd.isna(row['green_days']) else int(row['green_days'])
                
                dm = DailyMetrics(symbol=symbol, atr_pct=row['atr_pct'], midpoint_pct=row['midpoint_pct'], 
                                 green_days=g_days, bb_squeeze=row['bb_squeeze'], near_resistance=row['near_res'])
                mm = MomentumMetrics(rsi=row['rsi_val'], rsi_rising=row['rsi_rising'], 
                                   macd_positive=row['macd_positive'], macd_rising=row['macd_rising'], 
                                   green_bars=g_bars)
                
                is_ninja = engine.is_ninja_candidate(dm, mm, dna)
                cat = "NONE"
                
                if is_ninja:
                    cat = "NINJA"
                elif engine.passes_daily_filter(dm, dna) and engine.passes_momentum_filter(mm, dna):
                    cat = engine.categorize(dm, mm, dna)
                else:
                    cat = "NONE"
                
                score = engine.calculate_score(dm, mm)
                # Add DNA bonus
                tier_bonuses = {'S': 20, 'A': 15, 'B+': 10, 'B': 5, 'B-': 2}
                score += tier_bonuses.get(dna.get('tier'), 0)
                
                categories.append(cat)
                scores.append(min(100, score) if cat != "NONE" else 0)

            df_1d['radar_category'] = categories
            df_1d['radar_score'] = scores
            
            # Save Enriched Data (Overwrite with caution, but user asked to 'add')
            # To be safe, we only keep the key enrichment columns + original ones
            cols_to_keep = ['timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume', 'radar_category', 'radar_score']
            df_final = df_1d[cols_to_keep]
            df_final.to_parquet(path_1d)

        except Exception as e:
            import traceback
            print(f"Error processing {symbol}: {e}")
            traceback.print_exc()
            continue

    print("\n=== ✅ ENRICHMENT COMPLETE! ===")

if __name__ == "__main__":
    enrich_all_coins()
