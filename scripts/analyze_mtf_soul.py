#!/usr/bin/env python3
"""
🔭 MTF SOUL SCANNER (1H & 4H)

26 rallinin 1H ve 4H zaman dilimlerindeki haleti ruhiyesini inceler.
Sadece 15M'de değil, büyük resimde ne oluyordu?

- 1H EMA Alignment (9, 21, 50, 200)
- 4H EMA Alignment
- RSI & Vol Context
- Distance to EMA200
"""

import pandas as pd
import json
import os
from datetime import datetime, timedelta

def analyze_mtf_soul():
    # 1. Load 15M Rally Dates
    rally_days_path = "data/algo_rally_days_15m.json"
    with open(rally_days_path, 'r') as f:
        rally_data = json.load(f)
    
    # 2. Load 1H and 4H Historical Data
    h1_path = "coin_cells/ALGOUSDT/data/history_1h.parquet"
    h4_path = "coin_cells/ALGOUSDT/data/history_4h.parquet"
    
    if not os.path.exists(h1_path) or not os.path.exists(h4_path):
        print("❌ 1H or 4H data missing!")
        return

    df_h1 = pd.read_parquet(h1_path)
    df_h4 = pd.read_parquet(h4_path)
    
    def prepare_df(df):
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        return df

    df_h1 = prepare_df(df_h1)
    df_h4 = prepare_df(df_h4)
    
    def add_indicators(df):
        # Use simple moving averages or ewm
        # EMA
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Vol Ratio
        df['vol_ma20'] = df['volume'].rolling(window=20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma20']
        return df

    df_h1 = add_indicators(df_h1)
    df_h4 = add_indicators(df_h4)
    
    print(f"🔬 Analyzing MTF context for {len(rally_data)} rallies...")
    print("="*80)
    
    mtf_souls = []
    
    for rally in rally_data:
        date_str = rally['date']
        start_ts = pd.to_datetime(rally['15m_data'][0]['timestamp'])
        
        # Find the snapshot EXACTLY at or just BEFORE rally start
        # Use asof or filter + tail
        h1_snapshot = df_h1[df_h1.index <= start_ts].tail(1)
        h4_snapshot = df_h4[df_h4.index <= start_ts].tail(1)
        
        if h1_snapshot.empty or h4_snapshot.empty:
            print(f"⚠️ Missing context for {date_str} at {start_ts}")
            continue
            
        h1 = h1_snapshot.iloc[0]
        h4 = h4_snapshot.iloc[0]
        h1_idx = h1_snapshot.index[0]
        
        # EMA Alignments
        h1_align = "NONE"
        if h1['ema9'] > h1['ema21'] > h1['ema50']:
            h1_align = "FULLY_ALIGNED"
            if h1['ema50'] > h1['ema200']:
                h1_align = "BULL_MARKET"
        elif h1['ema9'] > h1['ema21']:
            h1_align = "CROSSING_UP"
        elif h1['close'] > h1['ema200']:
            h1_align = "ABOVE_200"
            
        h4_align = "NONE"
        if h4['ema9'] > h4['ema21'] > h4['ema50']:
            h4_align = "FULLY_ALIGNED"
        elif h4['ema9'] > h4['ema21']:
            h4_align = "CROSSING_UP"
            
        dist_200 = (h1['close'] / h1['ema200'] - 1) * 100
        
        soul = {
            'date': date_str,
            'start_time': str(start_ts),
            'h1_time': str(h1_idx),
            'h1': {
                'align': h1_align,
                'rsi': round(h1['rsi'], 2),
                'dist_200': round(dist_200, 2),
                'vol_ratio': round(h1['vol_ratio'], 2)
            },
            'h4': {
                'align': h4_align,
                'rsi': round(h4['rsi'], 2)
            }
        }
        mtf_souls.append(soul)
        
        print(f"📅 {date_str} | 1H-Time: {h1_idx.strftime('%Y-%m-%d %H:%M')} | 1H: {h1_align:15} | dist200: {dist_200:6.1f}% | RSI1H: {h1['rsi']:4.1f}")

    # Aggregated Summary
    print("\n" + "="*80)
    print("📊 MTF AGGREGATED SOUL SUMMARY")
    print("="*80)
    
    h1_counts = pd.Series([s['h1']['align'] for s in mtf_souls]).value_counts()
    print(f"\n1H Alignments:\n{h1_counts}")
    
    h4_counts = pd.Series([s['h4']['align'] for s in mtf_souls]).value_counts()
    print(f"\n4H Alignments:\n{h4_counts}")
    
    avg_dist_200 = sum(s['h1']['dist_200'] for s in mtf_souls) / len(mtf_souls)
    print(f"\nAvg Distance from 1H EMA200: {avg_dist_200:.2f}%")
    
    # Save to JSON
    with open("data/algo_mtf_soul_context.json", "w") as f:
        json.dump(mtf_souls, f, indent=2)

if __name__ == "__main__":
    analyze_mtf_soul()
