#!/usr/bin/env python3
"""
Extract 15M data for 26 ALGO rally days (Ayaş Tunnel PASS days)
Output: JSON format with all indicators for ASM training
"""

import sys
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from db_helper import get_rallies

def load_and_prep_15m_data(symbol='ALGOUSDT'):
    """Load 15M data and calculate all indicators"""
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    df = pd.read_parquet(path)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Calculate EMAs
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    
    # Calculate ATR
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_ma'] = df['atr'].rolling(50).mean()
    
    # Calculate RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Calculate Volume Ratio
    df['vol_ma'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma']
    
    # Initialize state as IDLE
    df['state'] = 'IDLE'
    
    return df

def extract_rally_day_data(df, rally_date):
    """Extract 15M data for a single rally day"""
    rally_day = pd.Timestamp(rally_date).date()
    mask = df['datetime'].dt.date == rally_day
    day_data = df[mask].copy()
    
    if len(day_data) == 0:
        return None
    
    # Convert to list of dicts
    candles = []
    for _, row in day_data.iterrows():
        candle = {
            'timestamp': row['datetime'].isoformat(),
            'open': round(float(row['open']), 6),
            'high': round(float(row['high']), 6),
            'low': round(float(row['low']), 6),
            'close': round(float(row['close']), 6),
            'volume': round(float(row['volume']), 2),
            'ema9': round(float(row['ema9']), 6) if not pd.isna(row['ema9']) else None,
            'ema21': round(float(row['ema21']), 6) if not pd.isna(row['ema21']) else None,
            'ema50': round(float(row['ema50']), 6) if not pd.isna(row['ema50']) else None,
            'atr': round(float(row['atr']), 6) if not pd.isna(row['atr']) else None,
            'atr_ma': round(float(row['atr_ma']), 6) if not pd.isna(row['atr_ma']) else None,
            'rsi': round(float(row['rsi']), 2) if not pd.isna(row['rsi']) else None,
            'vol_ratio': round(float(row['vol_ratio']), 3) if not pd.isna(row['vol_ratio']) else None,
            'state': row['state']
        }
        candles.append(candle)
    
    return candles

def main():
    symbol = 'ALGOUSDT'
    
    print(f"🔄 Extracting 15M data for ALGO rally days...")
    print("="*80)
    
    # Get rally dates (Ayaş Tunnel PASS days)
    # Using top 26 rallies from GOLD + SILVER tiers
    rallies = get_rallies(symbol, tiers=['GOLD', 'SILVER'], train_only=True)
    rally_dates = sorted(list(rallies.keys()))[:26]
    
    print(f"Found {len(rally_dates)} rally dates")
    
    # Load 15M data with indicators
    print("Loading and calculating indicators...")
    df = load_and_prep_15m_data(symbol)
    
    # Extract data for each rally day
    rally_data_collection = []
    
    for rally_date in rally_dates:
        tier, pct = rallies[rally_date]
        print(f"\n📅 {rally_date} ({tier}, {pct:+.1f}%)")
        
        candles = extract_rally_day_data(df, rally_date)
        
        if candles:
            rally_data_collection.append({
                'date': str(rally_date),  # Convert to string for JSON serialization
                'tier': tier,
                'rally_pct': round(pct, 2),
                'candle_count': len(candles),
                '15m_data': candles
            })
            print(f"   ✅ Extracted {len(candles)} candles")
        else:
            print(f"   ⚠️ No data found")
    
    # Save to JSON
    output_path = "data/algo_rally_days_15m.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(rally_data_collection, f, indent=2)
    
    print("\n" + "="*80)
    print(f"✅ Extraction complete!")
    print(f"📁 Saved to: {output_path}")
    print(f"📊 Total rally days: {len(rally_data_collection)}")
    print(f"📊 Total candles: {sum(r['candle_count'] for r in rally_data_collection)}")
    
    # Print sample
    if rally_data_collection:
        print("\n📋 Sample (first rally day, first 3 candles):")
        sample = rally_data_collection[0]
        print(f"Date: {sample['date']}")
        print(f"Candles: {sample['candle_count']}")
        print("\nFirst 3 candles:")
        for i, candle in enumerate(sample['15m_data'][:3]):
            print(f"\nCandle {i+1}:")
            print(f"  Time: {candle['timestamp']}")
            print(f"  OHLC: {candle['open']}/{candle['high']}/{candle['low']}/{candle['close']}")
            print(f"  RSI: {candle['rsi']}, Vol Ratio: {candle['vol_ratio']}")
            print(f"  State: {candle['state']}")

if __name__ == "__main__":
    main()
