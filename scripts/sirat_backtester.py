"""
🌉 Sırat Köprüsü Backtester - ENSUSDT (Last 100 Days)
Checks how many times ENS crossed the "Soul Bridge" and the result.
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

def run_backtest():
    base_path = os.path.join(COIN_CELLS_DIR, SYMBOL, "data")
    df_1d = load_clean(os.path.join(base_path, "history_1d.parquet"))
    df_1h = load_clean(os.path.join(base_path, "history_1h.parquet"))
    df_15m = load_clean(os.path.join(base_path, "history_15m.parquet"))
    
    if df_1d.empty: return
    
    # Get last 100 days (ensure we have next day data)
    # Filter to valid range
    end_limit = pd.Timestamp.now() - pd.Timedelta(days=2) # Leave buffer for 'next day' results
    df_1d = df_1d[df_1d.index <= end_limit]
    
    last_100 = df_1d.tail(100)
    
    cross_count = 0
    success = 0
    fail = 0
    
    print(f"🌉 SIRAT KÖPRÜSÜ BACKTEST (Son 100 Gün) - {SYMBOL}")
    print(f"   Koşullar: 1. Yeşil Gün | 2. Sprint Kapanış (>%60) | 3. Diri Hacim (>0.85 Ratio)")
    print("-" * 65)
    print(f"{'Tarih':<12} | {'Durum':<10} | {'Sonuç':<10} | {'Kazanç'}")
    print("-" * 65)
    
    for i in range(len(last_100)):
        day = last_100.index[i]
        tomorrow = day + pd.Timedelta(days=1)
        
        # Check Soul Metrics (The Bridge)
        metrics = get_soul_metrics(df_1h, day + pd.Timedelta(days=1)) # 1h index aligns to end? Need to align correctly.
        # Usually df_1d index is open time 00:00. 
        # So close of day is day + 1 day
        metrics = get_soul_metrics(df_1h, tomorrow)
        
        if not metrics: continue
        
        # THE BRIDGE RULES (Sırat Kuralları)
        bridge_pass = (
            metrics['is_positive'] and
            metrics['pos_pct'] > 0.6 and
            metrics['vol_ratio'] > 0.85
        )
        
        status = "GEÇTİ 🌉" if bridge_pass else "YIKILDI"
        
        # Check Result (Next Day)
        # Using 5% intra-day peak logic
        next_day_bars = df_15m[(df_15m.index >= tomorrow) & (df_15m.index < tomorrow + pd.Timedelta(days=1))]
        
        res_str = "-"
        gain_str = "-"
        
        if not next_day_bars.empty:
            open_p = next_day_bars['open'].iloc[0]
            high_p = next_day_bars['high'].max()
            gain = (high_p / open_p) - 1
            gain_pct = gain * 100
            gain_str = f"+{gain_pct:.1f}%"
            
            is_tier = gain >= 0.05
            
            if bridge_pass:
                if is_tier:
                    success += 1
                    res_str = "✅ TIER"
                else:
                    fail += 1
                    res_str = "❌ BOŞ"
                    
                print(f"{day.strftime('%Y-%m-%d')} | {status}   | {res_str:<10} | {gain_str}")
        
    print("-" * 65)
    print(f"Toplam Geçiş Denemesi: {cross_count + success + fail if False else (success+fail)}") # success/fail count is strictly from crossed
    print(f"🌉 Köprüden Geçen Gün: {success + fail}")
    print(f"✅ Başarılı (Tier):     {success}")
    print(f"❌ Başarısız (Düştü):   {fail}")
    
    total_tiers_in_period = 0
    # Re-scan for total tiers in the 100 day period
    for i in range(len(last_100)):
        day = last_100.index[i]
        tomorrow = day + pd.Timedelta(days=1)
        next_day_bars = df_15m[(df_15m.index >= tomorrow) & (df_15m.index < tomorrow + pd.Timedelta(days=1))]
        if not next_day_bars.empty:
            open_p = next_day_bars['open'].iloc[0]
            high_p = next_day_bars['high'].max()
            gain = (high_p / open_p) - 1
            if gain >= 0.05:
                total_tiers_in_period += 1
                
    print("-" * 65)
    print(f"📊 GERÇEK PERFORMANS:")
    print(f"   Toplam Tier Günü:     {total_tiers_in_period}")
    print(f"   Yakalanan Tier:       {success}")
    print(f"   Kaçırılan Tier:       {total_tiers_in_period - success}")
    if total_tiers_in_period > 0:
        print(f"   RECALL (Yakalama):    {success / total_tiers_in_period:.1%}")
    if (success + fail) > 0:
        print(f"   PRECISION (İsabet):   {success / (success + fail):.1%}")

if __name__ == "__main__":
    run_backtest()
