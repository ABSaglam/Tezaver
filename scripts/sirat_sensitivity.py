"""
🌉 Sırat Köprüsü Sensitivity Analysis - ENSUSDT
Testing different strictness levels to find the optimal Risk/Recall balance.
"""
import os
import pandas as pd
import numpy as np

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
SYMBOL = "ENSUSDT"

def load_clean(path):
    try:
        df = pd.read_parquet(path)
        if 'timestamp' in df.columns:
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df = df[~df.index.duplicated(keep='last')]
            return df.sort_index()
    except:
        return pd.DataFrame()

def get_soul_metrics(df_1h, day_close_time):
    start_time = day_close_time - pd.Timedelta(hours=24)
    mask = (df_1h.index > start_time) & (df_1h.index <= day_close_time)
    sub = df_1h[mask]
    
    if len(sub) < 24: return None
    
    open_p = sub['open'].iloc[0]
    close_p = sub['close'].iloc[-1]
    is_positive = close_p > open_p
    
    high_p = sub['high'].max()
    low_p = sub['low'].min()
    range_p = high_p - low_p
    if range_p == 0: pos_pct = 0.5
    else: pos_pct = (close_p - low_p) / range_p
    
    vol_start = sub['volume'].iloc[:6].mean()
    vol_end = sub['volume'].iloc[-6:].mean()
    if vol_start == 0: vol_ratio = 1.0
    else: vol_ratio = vol_end / vol_start
    
    return {
        'is_positive': is_positive,
        'pos_pct': pos_pct,
        'vol_ratio': vol_ratio
    }

def run_sensitivity():
    base_path = os.path.join(COIN_CELLS_DIR, SYMBOL, "data")
    df_1d = load_clean(os.path.join(base_path, "history_1d.parquet"))
    df_1h = load_clean(os.path.join(base_path, "history_1h.parquet"))
    df_15m = load_clean(os.path.join(base_path, "history_15m.parquet"))
    
    if df_1d.empty: return
    
    # Last 100 Days
    end_limit = pd.Timestamp.now() - pd.Timedelta(days=2)
    df_1d = df_1d[df_1d.index <= end_limit]
    last_100 = df_1d.tail(100)
    
    # Levels to test
    levels = [
        {'name': '🔥 STRICT (Mevcut)', 'pos_pct': 0.60, 'vol': 0.85},
        {'name': '⚖️ MEDIUM (Dengeli)', 'pos_pct': 0.50, 'vol': 0.80},
        {'name': '🌊 LOOSE (Gevşek)', 'pos_pct': 0.40, 'vol': 0.70},
        {'name': '🎲 YOLO (Riskli)',   'pos_pct': 0.30, 'vol': 0.60},
    ]
    
    print(f"🌉 SIRAT HASSASİYET ANALİZİ (Sensitivity Risk/Reward)")
    print(f"Coin: {SYMBOL} | Süre: Son 100 Gün")
    print("-" * 80)
    print(f"{'Level':<20} | {'Sinyal':<8} | {'Tier Yakala':<12} | {'Win Rate':<10} | {'Yakalanan % (Recall)'}")
    print("-" * 80)
    
    # 1. Count Total Tiers first
    total_tiers = 0
    for i in range(len(last_100)):
        day = last_100.index[i]
        tomorrow = day + pd.Timedelta(days=1)
        next_day_bars = df_15m[(df_15m.index >= tomorrow) & (df_15m.index < tomorrow + pd.Timedelta(days=1))]
        if not next_day_bars.empty:
            open_p = next_day_bars['open'].iloc[0]
            high_p = next_day_bars['high'].max()
            if ((high_p / open_p) - 1) >= 0.05:
                total_tiers += 1
                
    for lvl in levels:
        signals = 0
        hits = 0
        losses = 0 # Define loss as < 0% gain (negative day)
        
        for i in range(len(last_100)):
            day = last_100.index[i]
            tomorrow = day + pd.Timedelta(days=1)
            metrics = get_soul_metrics(df_1h, tomorrow)
            if not metrics: continue
            
            # Check Rule
            pass_rule = (
                metrics['is_positive'] and
                metrics['pos_pct'] > lvl['pos_pct'] and
                metrics['vol_ratio'] > lvl['vol']
            )
            
            if pass_rule:
                signals += 1
                # Check Result
                next_day_bars = df_15m[(df_15m.index >= tomorrow) & (df_15m.index < tomorrow + pd.Timedelta(days=1))]
                if not next_day_bars.empty:
                    open_p = next_day_bars['open'].iloc[0]
                    high_p = next_day_bars['high'].max()
                    gain = (high_p / open_p) - 1
                    
                    if gain >= 0.05:
                        hits += 1
                    elif gain < 0: # Actual loss? (Checking close vs open)
                        # Let's check CLOSE vs OPEN for 'Loss'
                        close_p = next_day_bars['close'].iloc[-1]
                        if close_p < open_p:
                             losses += 1
                             
        precision = (hits / signals * 100) if signals > 0 else 0
        recall = (hits / total_tiers * 100) if total_tiers > 0 else 0
        
        print(f"{lvl['name']:<20} | {signals:<8} | {hits}/{total_tiers:<12} | {precision:<10.1f}% | {recall:.1f}%")
        
    print("-" * 80)
    print(f"Toplam Tier Fırsatı: {total_tiers}")

if __name__ == "__main__":
    run_sensitivity()
