#!/usr/bin/env python3
"""
RSI-EMA > 60 TRIGGER - HISTORICAL BACKTEST (PRE-2026)
This script scans all available coin history excluding the year 2026.
Trigger: RSI-EMA (15m) crosses ABOVE 60.
Window: 49 bars (approx 12 hours).
Metrics: Tier counts (Diamond, Gold, Silver, Bronze), Failure rates (<5%), Loss rates (Negative Close).
"""

import pandas as pd
import numpy as np
import os
import json
import warnings

# Suppress warnings
warnings.filterwarnings("ignore")

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
EXCLUDE_YEAR = 2026

def analyze_history():
    print(f"🚀 RSI-EMA > 60 TARIHSEL ANALIZI (2026 HARIÇ)")
    print(f"--------------------------------------------------")
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    total_signals = 0
    tier_counts = {
        'Diamond': 0, # >= 30%
        'Gold': 0,    # 20% - 30%
        'Silver': 0,  # 10% - 20%
        'Bronze': 0,  # 5% - 10%
        'Fail': 0     # < 5%
    }
    
    total_neg_close = 0 # Closed negative after 49 bars
    
    processed_count = 0
    
    for symbol in symbols:
        try:
            # Load 15m Data
            path_15m = f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet"
            if not os.path.exists(path_15m): continue
            
            df_15m = pd.read_parquet(path_15m)
            df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
            df_15m.set_index('dt', inplace=True)
            df_15m = df_15m[~df_15m.index.duplicated(keep='last')].sort_index()
            
            # Filter OUT 2026
            df_15m = df_15m[df_15m.index.year < EXCLUDE_YEAR]
            
            if df_15m.empty: continue
            
            # Calculate Indicators
            # RSI Calculation
            delta = df_15m['close'].diff()
            alpha = 1 / 11
            gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
            df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
            
            # RSI-EMA Calculation
            df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
            
            # Trigger Logic: RSI-EMA > 60
            cond_now = df_15m['rsi_ema'] > 60
            triggers = (cond_now) & (~cond_now.shift(1).fillna(False))
            
            trigger_indices = np.where(triggers)[0]
            
            for idx in trigger_indices:
                # Need at least 1 bar data to calculate entry (open of trigger bar or close of trigger bar?)
                # Standard practice: Signal occurs at close, entry is next open or immediate close.
                # Let's take 'close' of trigger bar as Entry Price for calculating potentials accurately from that moment.
                
                entry_price = df_15m['close'].values[idx]
                
                # Check forward 49 bars
                match_end_idx = min(idx + 49, len(df_15m) - 1)
                
                if match_end_idx <= idx: continue # No future data
                
                future_window = df_15m.iloc[idx+1 : match_end_idx+1]
                
                if future_window.empty: continue
                
                max_price = future_window['high'].max()
                close_price = future_window['close'].iloc[-1]
                
                max_gain_pct = ((max_price - entry_price) / entry_price) * 100
                close_gain_pct = ((close_price - entry_price) / entry_price) * 100
                
                total_signals += 1
                
                # Tier Classification
                if max_gain_pct >= 30.0:
                    tier_counts['Diamond'] += 1
                elif max_gain_pct >= 20.0:
                    tier_counts['Gold'] += 1
                elif max_gain_pct >= 10.0:
                    tier_counts['Silver'] += 1
                elif max_gain_pct >= 5.0:
                    tier_counts['Bronze'] += 1
                else:
                    tier_counts['Fail'] += 1
                    
                # Negative Close Check
                if close_gain_pct < 0:
                    total_neg_close += 1
            
            processed_count += 1
            print(f"Processed {symbol} ({len(trigger_indices)} signals)...", end='\r')
            
        except Exception as e:
            # print(f"Error processing {symbol}: {e}")
            continue

    print(f"\n\n==================================================")
    print(f"🏁 ANALİZ SONUÇLARI (2026 ÖNCESİ)")
    print(f"==================================================")
    print(f"Toplam Sinyal Sayısı: {total_signals}")
    print(f"İncelenen Coin Sayısı: {processed_count}")
    print(f"--------------------------------------------------")
    
    if total_signals > 0:
        print(f"\n🏅 TIER PERFORMANSI (49 Bar / ~12 Saat)")
        print(f"--------------------------------------------------")
        
        # Calculate percentages
        d_rate = (tier_counts['Diamond'] / total_signals) * 100
        g_rate = (tier_counts['Gold'] / total_signals) * 100
        s_rate = (tier_counts['Silver'] / total_signals) * 100
        b_rate = (tier_counts['Bronze'] / total_signals) * 100
        f_rate = (tier_counts['Fail'] / total_signals) * 100
        
        # Cumulative Win Rate (Bronze+)
        win_count = total_signals - tier_counts['Fail']
        win_rate = (win_count / total_signals) * 100
        
        print(f"💎 DIAMOND (>= 30%): {tier_counts['Diamond']:5d}  |  %{d_rate:.2f}")
        print(f"🥇 GOLD    (20-30%): {tier_counts['Gold']:5d}  |  %{g_rate:.2f}")
        print(f"🥈 SILVER  (10-20%): {tier_counts['Silver']:5d}  |  %{s_rate:.2f}")
        print(f"🥉 BRONZE  (5-10%) : {tier_counts['Bronze']:5d}  |  %{b_rate:.2f}")
        print(f"--------------------------------------------------")
        print(f"❌ FAIL    (< 5%)  : {tier_counts['Fail']:5d}  |  %{f_rate:.2f}")
        print(f"--------------------------------------------------")
        print(f"✅ TOPLAM WIN RATE : %{win_rate:.2f} (Bronze ve üzeri)")
        
        print(f"\n⚠️ RİSK ANALİZİ")
        print(f"--------------------------------------------------")
        neg_rate = (total_neg_close / total_signals) * 100
        print(f"📉 Negatif Kapanış : {total_neg_close:5d}  |  %{neg_rate:.2f}")
        print(f"(Sinyalden 12 saat sonra zararda kapatanlar)")
        
    else:
        print("Veri bulunamadı veya sinyal üretilmedi.")

if __name__ == "__main__":
    analyze_history()
