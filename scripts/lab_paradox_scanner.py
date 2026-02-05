#!/usr/bin/env python3
"""
TEZAVER LAB: PARADOX SCANNER (v0.1)
"Newtonyen Kahin" Modülü

Bu script, piyasadaki "Fiziksel İmkansızlıkları" (Paradoksları) tarar.
1. SESSİZ ÇIĞLIK (Silent Scream): Fiyat sabit, Hacim patlıyor. (Enerji sıkışması)
2. TÜY DÜŞÜŞÜ (Feather Fall): Fiyat düşüyor, Hacim yok. (Sahte düşüş)
"""

import pandas as pd
import numpy as np
import os
import argparse
import math

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

def analyze_paradoxes(symbol, start_date, end_date):
    p_15m = f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet"
    if not os.path.exists(p_15m): return []

    try:
        df = pd.read_parquet(p_15m)
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        df = df[~df.index.duplicated(keep='last')].sort_index()
        
        # Calculate Base Metrics
        df['vol_ma21'] = df['volume'].rolling(window=21).mean()
        df['vol_ma50'] = df['volume'].rolling(window=50).mean()
        
        # Price Change
        df['pct_change'] = df['close'].pct_change() * 100
        
        # Calculate Additional Indicators for Filtering
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean().replace(0, 0.001)
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))
        
        # RSI-EMA & Ribbon
        df['rsi_ema'] = df['rsi'].ewm(span=14, adjust=False).mean()
        df['rib_21'] = df['rsi_ema'].ewm(span=21, adjust=False).mean()
        df['rib_55'] = df['rsi_ema'].ewm(span=55, adjust=False).mean()
        
        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd_hist'] = (ema12 - ema26) - (ema12 - ema26).ewm(span=9, adjust=False).mean()
        
        # Slice for date
        mask = (df.index >= start_date) & (df.index <= end_date)
        df_target = df[mask]
        
        if df_target.empty: return []
        
        paradox_events = []
        
        # Iterate (Skip first 50 for warm-up)
        for i in range(50, len(df_target)):
            curr_time = df_target.index[i]
            ts = df_target.index[i]
            
            # Context Metrics
            rsi_val = df_target.iloc[i]['rsi']
            is_ribbon_bull = df_target.iloc[i]['rib_21'] > df_target.iloc[i]['rib_55']
            macd_val = df_target.iloc[i]['macd_hist']
            
            # --- PARADOX 1: SILENT SCREAM (Sessiz Çığlık) ---
            # Condition A: Price is Flat over last 5 bars (Abs change < 1%)
            last_5 = df_target.iloc[i-4:i+1] # 5 bars
            p_range = (last_5['high'].max() - last_5['low'].min()) / last_5['open'].iloc[0] * 100
            is_flat = p_range < 2.0 # Looser initial filter, let optimizer tighten it
            
            # Condition B: Volume is IGNITED (> 2x MA50)
            vol_curr = df_target.iloc[i]['volume']
            vol_avg = df_target.iloc[i]['vol_ma50']
            vol_ratio = vol_curr / (vol_avg + 0.001)
            is_high_vol = vol_ratio > 2.0 # Looser initial filter
            
            if is_flat and is_high_vol:
                # Outcome Check (Next 24h max gain)
                outcome_max = 0
                if i + 96 < len(df_target): # next 96 bars = 24h
                    future = df_target.iloc[i+1:i+97]
                    curr_close = df_target.iloc[i]['close']
                    outcome_max = ((future['high'].max() - curr_close) / curr_close) * 100
                
                paradox_events.append({
                    'time': ts,
                    'type': 'SILENT_SCREAM 🤫🔊',
                    'desc': f"R={p_range:.1f}%, V={vol_ratio:.1f}x",
                    'outcome_24h': outcome_max,
                    'vol_ratio': vol_ratio,
                    'p_range': p_range,
                    # Extra Dimensions for Optimizer
                    'rsi': rsi_val,
                    'ribbon_bull': is_ribbon_bull,
                    'macd': macd_val
                })

            # --- PARADOX 2: FEATHER FALL (Tüy Düşüşü) ---
            # Condition A: Hard Drop (Close < -2%)
            is_drop = df_target.iloc[i]['pct_change'] < -2.0
            
            # Condition B: Low Volume (< 0.6x MA21)
            vol_avg_short = df_target.iloc[i]['vol_ma21']
            vol_ratio_s = vol_curr / (vol_avg_short + 0.001)
            is_low_vol = vol_ratio_s < 0.6
            
            if is_drop and is_low_vol:
                outcome_max = 0
                if i + 96 < len(df_target):
                    future = df_target.iloc[i+1:i+97]
                    curr_close = df_target.iloc[i]['close']
                    outcome_max = ((future['high'].max() - curr_close) / curr_close) * 100

                paradox_events.append({
                    'time': ts,
                    'type': 'FEATHER_FALL 🪶🔻',
                    'desc': f"Drop={df_target.iloc[i]['pct_change']:.1f}%, V={vol_ratio_s:.1f}x",
                    'outcome_24h': outcome_max,
                    'vol_ratio': vol_ratio_s
                })
                
        return paradox_events

    except Exception as e:
        # print(f"Error {symbol}: {e}")
        return []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default="2026-01-01")
    parser.add_argument('--end', default="2026-01-31")
    args = parser.parse_args()
    
    print(f"🔬 PARADOX LABORATORY SCAN: {args.start} -> {args.end}")
    print("-" * 60)
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    all_events = []
    
    for sym in symbols:
        events = analyze_paradoxes(sym, args.start, args.end)
        for e in events:
            e['symbol'] = sym
            all_events.append(e)
            
    if not all_events:
        print("No paradoxes found in this reality.")
        return

    # Sort by Outcome for now to see best examples
    all_events.sort(key=lambda x: x['outcome_24h'], reverse=True)
    
    # Print Top 50 Results
    print(f"{'TIME':<20} | {'SYMBOL':<10} | {'TYPE':<20} | {'DESC':<25} | {'24H_MAX':<10}")
    print("-" * 95)
    
    avg_win = 0
    count = 0
    
    for e in all_events:
        # Filter noise? Let's show influential ones
        print(f"{e['time'].strftime('%Y-%m-%d %H:%M'):<20} | {e['symbol']:<10} | {e['type']:<20} | {e['desc']:<25} | {e['outcome_24h']:+.1f}%")
        avg_win += e['outcome_24h']
        count += 1
        
    print("-" * 95)
    print(f"RAW Paradoxes: {len(all_events)}")
    
    # DUMP TO JSON FOR OPTIMIZER
    import json
    # Convert timestamps to string
    json_events = []
    for e in all_events:
        ec = e.copy()
        ec['time'] = str(ec['time'])
        if 'ribbon_bull' in ec: ec['ribbon_bull'] = bool(ec['ribbon_bull'])
        json_events.append(ec)
        
    with open("temp_paradox_raw.json", "w") as f:
        json.dump(json_events, f)
    print(f"Saved raw events to temp_paradox_raw.json for optimization.")

    # --- TIER ANALIZI ---
    tiers = {
        '💎 DIAMOND (>30%)': 0,
        '🥇 GOLD (>20%)': 0,
        '🥈 SILVER (>10%)': 0,
        '🥉 BRONZE (>5%)': 0,
        '💩 GARBAGE (<5%)': 0
    }
    
    for e in all_events:
        gain = e['outcome_24h']
        if gain >= 30.0: tiers['💎 DIAMOND (>30%)'] += 1
        elif gain >= 20.0: tiers['🥇 GOLD (>20%)'] += 1
        elif gain >= 10.0: tiers['🥈 SILVER (>10%)'] += 1
        elif gain >= 5.0: tiers['🥉 BRONZE (>5%)'] += 1
        else: tiers['💩 GARBAGE (<5%)'] += 1

    print("\n📊 TIER DISTRIBUTION (RAW ANOMALIES)")
    print("-" * 40)
    total = len(all_events)
    for t_name, t_count in tiers.items():
        ratio = (t_count / total) * 100
        print(f"{t_name:<20} : {t_count:>4}  ({ratio:.1f}%)")
    print("-" * 40)
    
    # Tier Win Rate (Bronze+)
    win_count = total - tiers['💩 GARBAGE (<5%)']
    print(f"WIN RATE (Gain > 5%): {win_count}/{total} = {(win_count/total)*100:.1f}%")

if __name__ == "__main__":
    main()
