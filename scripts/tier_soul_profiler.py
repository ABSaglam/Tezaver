"""
👻 Tier Soul Profiler - ENSUSDT
"Ruha Bakış" (Visual Archetype Discovery)
Goal: Extract the "Average Shape" (Price & Volume) of a Tier Day's precursor.
"""
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
SYMBOL = "ENSUSDT"
REPORT_FILE = f"{SYMBOL}_soul_shape.md"

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

def get_normalized_profile(df_1h, day_close_time):
    """Get the 24h profile ending at day_close_time"""
    # Get last 24 1H candles UP TO the close
    # day_close_time is 00:00 of next day usually (end of prev day)
    
    start_time = day_close_time - pd.Timedelta(hours=24)
    mask = (df_1h.index > start_time) & (df_1h.index <= day_close_time)
    sub = df_1h[mask]
    
    if len(sub) != 24: return None
    
    # Normalize Price (Start = 1.0)
    start_price = sub['open'].iloc[0]
    norm_price = sub['close'] / start_price
    
    # Normalize Volume (vs Avg)
    avg_vol = sub['volume'].mean()
    if avg_vol == 0: avg_vol = 1
    norm_vol = sub['volume'] / avg_vol
    
    return norm_price.values, norm_vol.values

def run_soul_profiler():
    print(f"👻 Tier Soul Profiler: {SYMBOL}")
    
    base_path = os.path.join(COIN_CELLS_DIR, SYMBOL, "data")
    df_1d = load_clean(os.path.join(base_path, "history_1d.parquet"))
    df_1h = load_clean(os.path.join(base_path, "history_1h.parquet"))
    df_15m = load_clean(os.path.join(base_path, "history_15m.parquet"))
    
    if df_1d.empty: return
    
    # Identify Tier Days
    tier_days = []
    non_tier_days = []
    
    # Only 2023-2025
    df_1d = df_1d[df_1d.index >= '2023-01-01']
    
    print("   Tier Günleri Aranıyor...")
    for i in range(len(df_1d) - 1):
        day = df_1d.index[i]
        tomorrow = df_1d.index[i+1] # This is the "Close Time" of 'day' roughly
        
        # Check if next day was Tier
        next_day_bars = df_15m[(df_15m.index >= tomorrow) & (df_15m.index < tomorrow + pd.Timedelta(days=1))]
        if next_day_bars.empty: continue
        
        # Simple Proxy: Did it yield > 5% intra-day?
        # (Using the simplified logic from previous steps to be consistent)
        open_p = next_day_bars['open'].iloc[0]
        high_p = next_day_bars['high'].max()
        gain = (high_p / open_p) - 1
        
        close_time_of_day = tomorrow # Daily index i+1 is the start of tomorrow / end of today
        
        if gain >= 0.05:
            tier_days.append(close_time_of_day)
        else:
            non_tier_days.append(close_time_of_day)
            
    print(f"   Tier Gün: {len(tier_days)} | Normal Gün: {len(non_tier_days)}")
    
    # Extract Profiles
    tier_prices = []
    tier_vols = []
    
    for t in tier_days:
        res = get_normalized_profile(df_1h, t)
        if res:
            tier_prices.append(res[0])
            tier_vols.append(res[1])
            
    norm_prices = []
    norm_vols = []
    # Sample non-tier for comparison (limit to same count)
    import random
    random.shuffle(non_tier_days)
    for t in non_tier_days[:len(tier_days)]:
        res = get_normalized_profile(df_1h, t)
        if res:
            norm_prices.append(res[0])
            norm_vols.append(res[1])
            
    # Calculate Averages
    avg_tier_price = np.mean(tier_prices, axis=0)
    avg_tier_vol = np.mean(tier_vols, axis=0)
    
    avg_norm_price = np.mean(norm_prices, axis=0)
    avg_norm_vol = np.mean(norm_vols, axis=0)
    
    # Analyze the SHAPE
    # 1. Price Shape
    # Does it curve up?
    tier_start = avg_tier_price[0]
    tier_mid = avg_tier_price[11]
    tier_end = avg_tier_price[23]
    
    print("\n🧐 ŞEKİL ANALİZİ (PRICE SHAPE)")
    print(f"   Tier Price: Start={tier_start:.3f} -> Mid={tier_mid:.3f} -> End={tier_end:.3f}")
    print(f"   Norm Price: Start={avg_norm_price[0]:.3f} -> Mid={avg_norm_price[11]:.3f} -> End={avg_norm_price[23]:.3f}")
    
    # 2. Volume Shape
    # Is volume rising at end?
    tier_vol_start = np.mean(avg_tier_vol[:6])
    tier_vol_end = np.mean(avg_tier_vol[-6:])
    norm_vol_start = np.mean(avg_norm_vol[:6])
    norm_vol_end = np.mean(avg_norm_vol[-6:])
    
    print("\n   Tier Volume: StartAvg={:.2f} -> EndAvg={:.2f} (Ratio: {:.2f})".format(
        tier_vol_start, tier_vol_end, tier_vol_end/tier_vol_start))
    print("   Norm Volume: StartAvg={:.2f} -> EndAvg={:.2f} (Ratio: {:.2f})".format(
        norm_vol_start, norm_vol_end, norm_vol_end/norm_vol_start))
        
    # Generate Report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 👻 ENSUSDT 'Ruh' Profili (The Soul Shape)\n")
        f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Analiz Edilen Tier Gün Sayısı: {len(tier_prices)}\n\n")
        
        f.write("## 1. Fiyatın Ruhu (Trajectory)\n")
        if tier_end > tier_mid > tier_start:
            f.write("📈 **Profil:** Güçlü, lineer bir yükseliş trendi.\n")
        elif tier_end > tier_start and tier_mid < tier_start:
            f.write("✅ **Profil:** 'U' Dönüşü (Bear Trap). Önce düşüş, gün ortasında toparlanma.\n")
        elif tier_mid > tier_end and tier_end > tier_start:
            f.write("⚠️ **Profil:** Yorulan Boğa. Gün ortası zirve, kapanışa doğru düşüş.\n")
        else:
            f.write("😐 **Profil:** Net bir yön yok (Yatay/Karışık).\n")
            
        f.write(f"- **Başlangıç:** 1.000\n")
        f.write(f"- **Gün Ortası (12:00):** {tier_mid:.3f}\n")
        f.write(f"- **Kapanış (00:00):** {tier_end:.3f}\n\n")
        
        f.write("## 2. Hacmin Ruhu (Pulse)\n")
        vol_ratio = tier_vol_end/tier_vol_start
        if vol_ratio > 1.5:
            f.write("🔊 **Nabız:** Kapanışa doğru GÜÇLENEN hacim (Aggressive Close).\n")
        elif vol_ratio < 0.8:
            f.write("📉 **Nabız:** Kapanışa doğru SÖNEN hacim (Exhaustion).\n")
        else:
            f.write("😐 **Nabız:** Stabil hacim akışı.\n")
            
        f.write(f"- **Sabah Hacmi:** {tier_vol_start:.2f}x\n")
        f.write(f"- **Kapanış Hacmi:** {tier_vol_end:.2f}x\n")
        f.write(f"- **Değişim:** {vol_ratio:.2f}\n\n")
        
        f.write("## 🧠 Dahi Yorumu\n")
        diff = tier_end - avg_norm_price[23]
        if diff > 0.02:
            f.write(f"Tier günleri, normal günlerden **%{diff*100:.1f} daha yukarıda** kapatıyor. Yani 'Güçlü Kapanış' şart.\n")
            
    print(f"\n✅ Rapor: {REPORT_FILE}")

if __name__ == "__main__":
    run_soul_profiler()
