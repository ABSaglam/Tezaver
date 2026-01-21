import sys
import os
sys.path.append(os.getcwd())
import pandas as pd
import numpy as np
import json

def generate_aca_atomic_profiles():
    symbol = "ACAUSDT"
    print(f"🧩 GENERATING ACA ATOMIC PROFILES (High Resolution)")
    
    # Load Data
    df_w = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
    df_d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
    df_h4 = pd.read_parquet(f"coin_cells/{symbol}/data/history_4h.parquet")
    df_h1 = pd.read_parquet(f"coin_cells/{symbol}/data/history_1h.parquet")
    
    for df in [df_w, df_d, df_h4, df_h1]:
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        df.sort_index(inplace=True)
        
        # Indicator Math
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['vol_ma'] = df['volume'].rolling(20).mean()
        
        # RSI Harmony
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))

    # 1. FAZ (Refined: Cycle Level)
    def v_faz(day):
        subset = df_w[df_w.index <= day]
        if subset.empty: return "başlangıç"
        w = subset.iloc[-1]
        if w['rsi'] < 40: return "derin_dip"
        if w['rsi'] < 60: return "birikim_fazı"
        if w['rsi'] < 75: return "yükselş_fazı"
        return "aşırı_alım"

    # 2. BİRİKİM (Atomic: 1H Compression Precise)
    def v_birikim(day):
        h1 = df_h1[df_h1.index <= day].tail(24)
        if h1.empty: return "yok"
        comp = (h1[['ema9', 'ema21', 'ema50']].max(axis=1) / h1[['ema9', 'ema21', 'ema50']].min(axis=1) - 1) * 100
        min_c = comp.min()
        if min_c < 0.3: return "micro_squeeze"
        if min_c < 0.6: return "tight_squeeze"
        if min_c < 1.2: return "coiling"
        return "loose"

    # 3. UYUM (Atomic: Tri-TF Harmony)
    def v_uyum(day):
        d_sub = df_d[df_d.index <= day]
        h4_sub = df_h4[df_h4.index <= day]
        h1_sub = df_h1[df_h1.index <= day]
        if d_sub.empty or h4_sub.empty or h1_sub.empty: return "yok"
        
        d = d_sub.iloc[-1]
        h4 = h4_sub.iloc[-1]
        h1 = h1_sub.iloc[-1]
        
        s = sum([d['close'] > d['ema21'], h4['close'] > h4['ema21'], h1['close'] > h1['ema21']])
        return f"harmony_L{s}"

    # 4. RİTİM (Atomic: Volatility pulse)
    def v_ritim(day):
        d_tail = df_d[df_d.index <= day].tail(3)
        vol_pulse = d_tail['volume'].iloc[-1] / d_tail['volume'].mean()
        if vol_pulse > 2.0: return "ignited"
        if vol_pulse > 1.0: return "active"
        return "sleeping"

    # 5. HAFIZA (Atomic: Retracement Level)
    def v_hafıza(day):
        d = df_d[df_d.index <= day].iloc[-1]
        yr_high = df_d[df_d.index <= day].tail(365)['high'].max()
        retr = (d['close'] / yr_high - 1) * 100
        if retr > -20: return "recovery_high"
        if retr > -50: return "mid_zone"
        return "deep_valley"

    # 6. ENERJİ (NEW: Volume DNA)
    def v_enerji(day):
        d_tail = df_d[df_d.index <= day].tail(10)
        # Is volume increasing over last 3 days?
        v_trend = d_tail['volume'].tail(3).mean() > d_tail['volume'].head(7).mean()
        return "building_energy" if v_trend else "depleting_energy"

    target_days = df_d[df_d.index.year.isin([2023, 2024, 2025])].index
    profiles = {}
    print("Mapping Atomic States...")
    for day in target_days:
        profiles[day.strftime('%Y-%m-%d')] = {
            'faz': v_faz(day),
            'birikim': v_birikim(day),
            'uyum': v_uyum(day),
            'ritim': v_ritim(day),
            'hafıza': v_hafıza(day),
            'enerji': v_enerji(day)
        }
        
    with open("data/aca_lockstate_profiles.json", "w") as f:
        json.dump(profiles, f, indent=2)
    print("✅ ACA Atomic Profiles Saved.")

if __name__ == "__main__":
    generate_aca_atomic_profiles()
