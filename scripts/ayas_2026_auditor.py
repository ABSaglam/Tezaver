#!/usr/bin/env python3
"""
🏛️ AYAŞ TÜNELİ 2026 DİSİPLİN RAPORU (v2026.1)
=============================================
Ali Beyim'in emriyle:
- Sadece 2026 verileri.
- Geleceği görme (Data Leakage) yasaktır.
- Standart V17 Rapor Formu.
"""

import pandas as pd
import numpy as np
import os
import json
import math
from datetime import datetime

# CONFIG
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
KEYS_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys" # Ana DNA Key dizini
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/AYAS_2026_DISIPLIN_RAPORU.md"

# 2026 Sınırları
START_DATE = pd.Timestamp("2026-01-01 00:00:00")
END_DATE = pd.Timestamp.now()

MONTHS_TR = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
}

def get_turkish_date(dt):
    return f"{dt.day} {MONTHS_TR[dt.month]} {dt.year}"

def load_clean(path):
    if not os.path.exists(path): return pd.DataFrame()
    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df = df[~df.index.duplicated(keep='last')]
    return df.sort_index()

def get_angle(series, period=5):
    if len(series) < period: return 0.0
    y = series.tail(period).values
    x = np.arange(period)
    slope, _ = np.polyfit(x, y, 1)
    return math.degrees(math.atan(slope))

def get_dna_profile_strict(day, df_w, df_h1, df_d, df_h4):
    """Geleceği görmeyen DNA profili (Strict Yesterday's Close)"""
    try:
        daily_cutoff = day.normalize() # Bugünün 00:00'ı
        
        # Sadece dünkü kapanışa kadar olan veri
        sub_d = df_d[df_d.index < daily_cutoff].tail(100)
        h4_cutoff = day - pd.Timedelta(hours=4)
        sub_h4 = df_h4[df_h4.index <= h4_cutoff].tail(42)
        h1_cutoff = day - pd.Timedelta(hours=1)
        sub_h1_24 = df_h1[df_h1.index <= h1_cutoff].tail(24)
        weekly_cutoff = day - pd.Timedelta(days=7)
        sub_w = df_w[df_w.index < weekly_cutoff].tail(52)
        
        if sub_w.empty or sub_d.empty or sub_h1_24.empty: return "neutral"
        
        # FAZ
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean().replace(0, 0.001)
        w_rsi = (100 - (100 / (1 + (gain / loss)))).iloc[-1]
        
        if w_rsi <= 35: faz = "derin_dip"
        elif w_rsi <= 45: faz = "birikim_fazi"
        elif w_rsi <= 55: faz = "notr_alan"
        elif w_rsi <= 65: faz = "momentum_artisi"
        elif w_rsi <= 75: faz = "guclu_trend"
        else: faz = "asiri_alim"
        
        # ACC
        sub_h1_24['ema9'] = sub_h1_24['close'].ewm(span=9, adjust=False).mean()
        sub_h1_24['ema21'] = sub_h1_24['close'].ewm(span=21, adjust=False).mean()
        sq_pct = abs(sub_h1_24['ema9'].iloc[-1] - sub_h1_24['ema21'].iloc[-1]) / sub_h1_24['close'].iloc[-1] * 100
        acc = "tight_squeeze" if sq_pct <= 0.3 else "micro_squeeze" if sq_pct <= 0.8 else "normal_gap" if sq_pct <= 1.5 else "expanded_gap"
        
        # HARM
        sub_d['ema21'] = sub_d['close'].ewm(span=21, adjust=False).mean()
        sub_h4['ema21'] = sub_h4['close'].ewm(span=21, adjust=False).mean()
        sub_h1_24['ema21'] = sub_h1_24['close'].ewm(span=21, adjust=False).mean()
        t_count = sum([sub_d.iloc[-1]['close'] > sub_d.iloc[-1]['ema21'],
                       sub_h4.iloc[-1]['close'] > sub_h4.iloc[-1]['ema21'],
                       sub_h1_24.iloc[-1]['close'] > sub_h1_24.iloc[-1]['ema21']])
        harm = f"harmony_L{t_count}"
        
        # Ritim
        vol_ratio = sub_d['volume'].iloc[-1] / sub_d['volume'].rolling(21).mean().iloc[-1]
        ritim = "volume_explosion" if vol_ratio >= 2.5 else "volume_surge" if vol_ratio >= 1.5 else "volume_normal" if vol_ratio >= 0.8 else "volume_dry"
        
        # CTX
        max_52w = sub_d['high'].max()
        dist = ((sub_d.iloc[-1]['close'] / max_52w) - 1) * 100
        ctx = "near_ath" if dist >= -10 else "mid_range" if dist >= -30 else "discounted" if dist >= -50 else "deep_discount"
        
        # Enerji
        vol_5 = sub_d['volume'].tail(5).mean()
        vol_10 = sub_d['volume'].tail(10).mean()
        enerji = "rising_energy" if vol_5 > vol_10 * 1.2 else "fading_energy" if vol_5 < vol_10 * 0.8 else "stable_energy"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except: return "neutral"

def run_2026_audit():
    print(f"🏛️ AYAŞ TÜNELİ 2026 DİSİPLİN OPERASYONU BAŞLADI...")
    
    golden_map = {}
    if os.path.exists(KEYS_DIR):
        for f_name in os.listdir(KEYS_DIR):
            if f_name.endswith("_key.json"):
                with open(os.path.join(KEYS_DIR, f_name), "r") as f:
                    data = json.load(f)
                    golden_map[data['symbol']] = set(data.get('golden_dna_list', []))

    symbols = sorted([d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))])
    report_rows = []

    for symbol in symbols:
        if symbol not in golden_map: continue
        
        try:
            df_15m = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet")
            df_1h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
            df_4h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
            df_1d = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
            df_1w = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")
            
            if df_15m.empty: continue
            
            # --- Indicators ---
            delta = df_15m['close'].diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/11, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/11, adjust=False).mean().replace(0, 0.001)
            df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
            df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
            
            rib_periods = [20, 25, 30, 35, 40, 45, 50, 55]
            for p in rib_periods:
                df_15m[f'rib_{p}'] = df_15m['rsi_ema'].ewm(span=p, adjust=False).mean()
            
            # ADX & Daily ATR for Tooltip
            d_tr = np.maximum(df_1d['high'] - df_1d['low'], np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), abs(df_1d['low'] - df_1d['close'].shift(1))))
            df_1d['atr_pct'] = (d_tr.rolling(14).mean() / df_1d['close']) * 100
            
            # Triggers: RSI-EMA > All Ribbons
            rsi_ema_vals = df_15m['rsi_ema'].values
            all_above = np.ones(len(df_15m), dtype=bool)
            for p in rib_periods:
                all_above &= (rsi_ema_vals > df_15m[f'rib_{p}'].values)
            
            trigger_indices = np.where(all_above & (~np.roll(all_above, 1)))[0]
            
            for idx in trigger_indices:
                trig_time = df_15m.index[idx]
                if trig_time < START_DATE or trig_time > END_DATE: continue
                
                # DNA Check (Yesterday's Close)
                dna = get_dna_profile_strict(trig_time, df_1w, df_1h, df_1d, df_4h)
                if dna not in golden_map[symbol]: continue
                
                # --- Metrics ---
                current_p = df_15m['close'].iloc[idx]
                future = df_15m.iloc[idx:idx+22]
                max_high = future['high'].max()
                p21_pct = ((max_high / current_p) - 1) * 100
                peak_dist = future['high'].argmax()
                
                # Daily Stats
                try:
                    d_row = df_1d.loc[df_1d.index == trig_time.normalize()]
                    if not d_row.empty:
                        d_open = d_row['open'].iloc[0]
                        max_d = ((d_row['high'].iloc[0] / d_open) - 1) * 100
                        close_d = ((d_row['close'].iloc[0] / d_open) - 1) * 100
                        atr_v = d_row['atr_pct'].iloc[0]
                    else: max_d=0; close_d=0; atr_v=0
                except: max_d=0; close_d=0; atr_v=0

                tier = "💎" if p21_pct >= 30 else "🥇" if p21_pct >= 20 else "🥈" if p21_pct >= 10 else "🥉" if p21_pct >= 5 else ""
                
                def fmt(v, is_max=False):
                    c = "green" if v > 0 else ("red" if v < 0 else "gray")
                    s = f"{v:+.1f}%"
                    if is_max and v >= 10: s = f"**{s}**"
                    return f"<font color='{c}'>{s}</font>"

                row = {
                    'date': trig_time.normalize(),
                    'time': trig_time.strftime("%H:%M"),
                    'sym': symbol,
                    'MAX': fmt(max_d, True),
                    'CLOSE': fmt(close_d),
                    'P': fmt(((current_p / df_15m.iloc[idx]['open']) - 1) * 100),
                    'TIER': tier,
                    'P-21': fmt(p21_pct),
                    'BAR': f"<font color='red'>**0**</font>" if peak_dist == 0 else str(peak_dist),
                    'ATR%': f"{atr_v:.1f}%",
                    'DNA': dna
                }
                report_rows.append(row)
        except: continue
        
    report_rows.sort(key=lambda x: (x['date'], x['sym'], x['time']))
    
    with open(OUTPUT_FILE, "w") as f:
        f.write("# 🏛️ AYAŞ TÜNELİ 2026 DİSİPLİN RAPORU (V17)\n")
        f.write(f"Süreç: 1 Ocak 2026 - {get_turkish_date(datetime.now())}\n\n")
        
        curr_d = None
        curr_s = None
        no_c = 1
        
        for r in report_rows:
            dt_tr = get_turkish_date(r['date'])
            if dt_tr != curr_d:
                f.write(f"\n## 📅 {dt_tr}\n\n")
                f.write("| NO | SYM | MAX | CLOSE | TIME | P | TIER | P-21 | BAR | ATR% | DNA |\n")
                f.write("|----|-----------|--------|--------|-------|-------|------|--------|-----|------|-----|\n")
                curr_d = dt_tr
                curr_s = None
                no_c = 1
            
            disp_no = str(no_c) if r['sym'] != curr_s else ""
            disp_sym = r['sym'] if r['sym'] != curr_s else ""
            disp_max = r['MAX'] if r['sym'] != curr_s else ""
            disp_close = r['CLOSE'] if r['sym'] != curr_s else ""
            
            cols = [disp_no, disp_sym, disp_max, disp_close, r['time'], r['P'], r['TIER'], r['P-21'], r['BAR'], r['ATR%'], r['DNA']]
            f.write("| " + " | ".join(cols) + " |\n")
            
            if r['sym'] != curr_s:
                curr_s = r['sym']
                no_c += 1
                
    print(f"✅ Rapor Hazır: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_2026_audit()
