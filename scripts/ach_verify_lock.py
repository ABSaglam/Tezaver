
import sys
import os
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths
from db_helper import get_rallies, TRAIN_CUTOFF

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def main():
    symbol = 'ACHUSDT'
    # 1. Load Data & Indicators (Simplified for speed)
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    df = pd.read_parquet(h4_path)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # 4H Indicators
    df['h4_vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    df['h4_ema21'] = df['close'].ewm(span=21).mean()
    df['h4_ema50'] = df['close'].ewm(span=50).mean()
    df['h4_trend'] = (df['h4_ema21'] / df['h4_ema50'] - 1) * 100
    
    # Resample Daily
    df_d = df.set_index('datetime').resample('1D').agg({'close': 'last'})
    df_d['d_rsi'] = calc_rsi(df_d['close'])
    df_d_re = df_d.reindex(df['datetime'], method='ffill')
    df['d_rsi'] = df_d_re['d_rsi'].values
    
    # Resample Weekly
    df_w = df.set_index('datetime').resample('1W').agg({'close': 'last'})
    df_w['w_rsi'] = calc_rsi(df_w['close'])
    df_w_re = df_w.reindex(df['datetime'], method='ffill')
    df['w_rsi'] = df_w_re['w_rsi'].values
    
    df['hour'] = df['datetime'].dt.hour
    midnight = df[df['hour'] == 0].copy().reset_index(drop=True)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    midnight['is_rally_day'] = midnight['datetime'].dt.date.isin(rally_results.keys())
    
    # APPLY KEY
    # QUIET LOCK: W_RSI>=40 & D_RSI>=70 & H4_Trend>=10 & H4_Vol<=1.5
    mask = (
        (midnight['w_rsi'] >= 40) &
        (midnight['d_rsi'] >= 70) &
        (midnight['h4_trend'] >= 10) &
        (midnight['h4_vol_ratio'] <= 1.5)
    )
    
    hits = midnight[mask & midnight['is_rally_day']]
    
    print("\n--- HITS BREAKDOWN ---")
    tier_counts = {'DIAMOND': 0, 'GOLD': 0, 'SILVER': 0}
    
    for _, row in hits.iterrows():
        d = row['datetime'].date()
        tier = rally_results[d][0]
        tier_counts[tier] += 1
        print(f"{d} ({tier})")
        
    print("\n--- SUMMARY ---")
    print(f"DIAMOND: {tier_counts['DIAMOND']}")
    print(f"GOLD:    {tier_counts['GOLD']}")
    print(f"SILVER:  {tier_counts['SILVER']}")

if __name__ == "__main__":
    main()
