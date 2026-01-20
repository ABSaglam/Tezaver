
import sys
import os
import pandas as pd
import numpy as np
import itertools

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

def calculate_mtf_indicators(df_4h):
    # 1. 4H Indicators
    df_4h['h4_rsi'] = calc_rsi(df_4h['close'])
    df_4h['h4_vol_ratio'] = df_4h['volume'] / df_4h['volume'].rolling(20).mean()
    df_4h['h4_ema21'] = df_4h['close'].ewm(span=21).mean()
    df_4h['h4_ema50'] = df_4h['close'].ewm(span=50).mean()
    df_4h['h4_trend'] = (df_4h['h4_ema21'] / df_4h['h4_ema50'] - 1) * 100
    
    # 2. Resample to Daily
    df_d = df_4h.set_index('datetime').resample('1D').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    })
    df_d['d_rsi'] = calc_rsi(df_d['close'])
    
    # 3. Resample to Weekly
    df_w = df_4h.set_index('datetime').resample('1W').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    })
    df_w['w_rsi'] = calc_rsi(df_w['close'])
    
    # 4. Merge Back to 4H (Forward Fill)
    df_4h['date'] = df_4h['datetime'].dt.date
    
    df_d_re = df_d.reindex(df_4h['datetime'], method='ffill')
    df_4h['d_rsi'] = df_d_re['d_rsi'].values
    
    df_w_re = df_w.reindex(df_4h['datetime'], method='ffill')
    df_4h['w_rsi'] = df_w_re['w_rsi'].values
    
    return df_4h

def main():
    symbol = 'ALPACAUSDT'
    print(f"🧬 AŞAMA 1-6 SIMULATION: {symbol}")
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
    
    # 2. Add Timeframe Context
    df = calculate_mtf_indicators(df)
    df['hour'] = df['datetime'].dt.hour
    
    # 3. Target Mapping
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    rally_dates = set(rally_results.keys())
    
    # Check at Midnight (00:00)
    midnight = df[df['hour'] == 0].copy().reset_index(drop=True)
    midnight['is_rally_day'] = midnight['datetime'].dt.date.isin(rally_dates)
    
    target_count = midnight['is_rally_day'].sum()
    print(f"Day Count: {len(midnight)}")
    print(f"Rally Count: {target_count}")
    
    # 4. EVOLUTION (AŞAMA 5 - Durma Yok - SCORCHED EARTH)
    
    best_perf = (0, 0) # precision, hits
    best_rule = ""
    
    # Expanded Grid for ALPACA
    w_rsi_mins = [30, 40, 50, 60]
    d_rsi_mins = [30, 40, 50, 60, 70]
    h4_trend_mins = [-5, 0, 5, 10, 20]
    h4_vol_limits = [1.5, 2.0, 3.0, 5.0]
    
    print(f"Running SCORCHED EARTH MTF Evolution...")
    
    # MODE 1: QUIET LOCK (Vol <= X)
    for w, d, t, v in itertools.product(w_rsi_mins, d_rsi_mins, h4_trend_mins, h4_vol_limits):
        mask = (
            (midnight['w_rsi'] >= w) &
            (midnight['d_rsi'] >= d) &
            (midnight['h4_trend'] >= t) &
            (midnight['h4_vol_ratio'] <= v)
        )
        h = midnight[mask & midnight['is_rally_day']].shape[0]
        f = midnight[mask & ~midnight['is_rally_day']].shape[0]
        total = h + f
        
        if total > 0:
            p = h / total * 100
            if p > best_perf[0]:
                best_perf = (p, h)
                best_rule = f"QUIET LOCK: W_RSI>={w} & D_RSI>={d} & H4_Trend>={t} & H4_Vol<={v}"
                
                if p == 100 and h >= 3:
                     print(f"💎 FOUND PERFECT QUIET KEY: {best_rule} -> {h}/{total}")

    # MODE 2: CHAOS LOCK (Vol >= X)
    for w, d, t, v in itertools.product(w_rsi_mins, d_rsi_mins, h4_trend_mins, h4_vol_limits):
        mask = (
            (midnight['w_rsi'] >= w) &
            (midnight['d_rsi'] >= d) &
            (midnight['h4_trend'] >= t) &
            (midnight['h4_vol_ratio'] >= v) # INVERTED
        )
        h = midnight[mask & midnight['is_rally_day']].shape[0]
        f = midnight[mask & ~midnight['is_rally_day']].shape[0]
        total = h + f
        
        if total > 0:
            p = h / total * 100
            if p > best_perf[0] or (p == best_perf[0] and h > best_perf[1]):
                best_perf = (p, h)
                best_rule = f"CHAOS LOCK: W_RSI>={w} & D_RSI>={d} & H4_Trend>={t} & H4_Vol>={v}"
                
                if p == 100 and h >= 3:
                    print(f"🔥 FOUND PERFECT CHAOS KEY: {best_rule} -> {h}/{total}")
    
    # 5. FINAL REPORT (AŞAMA 6 Format)
    print("\n" + "="*70)
    print("AŞAMA 6: RAPOR")
    print("="*70)
    
    print(f"1. Nihai ANAHTAR TANIMI:\n   {best_rule}")
    print(f"2. Aktif Gün Sayısı: {best_perf[1]}")
    
    if best_perf[0] == 100:
        print(f"4. SONUÇ:\n   'Bu anahtar, geçmiş veride ralli olmayan hiçbir günü geçirmedi.'")
    else:
        print(f"4. SONUÇ:\n   ⚠️ %100 BULUNAMADI. En iyi: {best_perf[0]:.1f}%")

if __name__ == "__main__":
    main()
