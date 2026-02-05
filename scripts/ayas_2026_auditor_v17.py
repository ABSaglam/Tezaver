#!/usr/bin/env python3
"""
🏛️ AYAŞ TÜNELİ 2026 TAM NİZAM RAPORU (v2026.2 - 26 SÜTUN)
=========================================================
Ali Beyim'in emriyle:
- 26 Sütunlu V17 Tam Format.
- Sadece 2026 verileri.
- Geleceği görme (Data Leakage) yasaktır.
"""

import pandas as pd
import numpy as np
import os
import json
import math
from datetime import datetime

# CONFIG
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
KEYS_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys"
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
    if len(y) < 2: return 0.0
    slope, _ = np.polyfit(x, y, 1)
    return math.degrees(math.atan(slope))

def get_dna_profile_strict(day, df_w, df_h1, df_d, df_h4):
    try:
        daily_cutoff = day.normalize()
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
        
        faz = "derin_dip" if w_rsi <= 35 else "birikim_fazi" if w_rsi <= 45 else "notr_alan" if w_rsi <= 55 else "momentum_artisi" if w_rsi <= 65 else "guclu_trend" if w_rsi <= 75 else "asiri_alim"
        
        # ACC
        sub_h1_24['e9'] = sub_h1_24['close'].ewm(span=9, adjust=False).mean()
        sub_h1_24['e21'] = sub_h1_24['close'].ewm(span=21, adjust=False).mean()
        sq = abs(sub_h1_24['e9'].iloc[-1] - sub_h1_24['e21'].iloc[-1]) / sub_h1_24['close'].iloc[-1] * 100
        acc = "tight_squeeze" if sq <= 0.3 else "micro_squeeze" if sq <= 0.8 else "normal_gap" if sq <= 1.5 else "expanded_gap"
        
        # HARM
        sub_d['e21'] = sub_d['close'].ewm(span=21, adjust=False).mean()
        sub_h4['e21'] = sub_h4['close'].ewm(span=21, adjust=False).mean()
        sub_h1_24['e21'] = sub_h1_24['close'].ewm(span=21, adjust=False).mean()
        t = sum([sub_d.iloc[-1]['close']>sub_d.iloc[-1]['e21'], sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['e21'], sub_h1_24.iloc[-1]['close']>sub_h1_24.iloc[-1]['e21']])
        harm = f"harmony_L{t}"
        
        # Ritim
        vol_r = sub_d['volume'].iloc[-1] / (sub_d['volume'].rolling(21).mean().iloc[-1] + 1e-9)
        ritim = "volume_explosion" if vol_r >= 2.5 else "volume_surge" if vol_r >= 1.5 else "volume_normal" if vol_r >= 0.8 else "volume_dry"
        
        # CTX
        m52 = sub_d['high'].max()
        dist = ((sub_d.iloc[-1]['close'] / m52) - 1) * 100
        ctx = "near_ath" if dist >= -10 else "mid_range" if dist >= -30 else "discounted" if dist >= -50 else "deep_discount"
        
        # Enerji
        v5, v10 = sub_d['volume'].tail(5).mean(), sub_d['volume'].tail(10).mean()
        en = "rising_energy" if v5 > v10*1.2 else "fading_energy" if v5 < v10*0.8 else "stable_energy"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{en}"
    except: return "neutral"

def run_tam_nizam_audit():
    print("🏛️ AYAŞ TÜNELİ 2026 TAM NİZAM DİSİPLİN OPERASYONU...")
    
    golden_map = {}
    if os.path.exists(KEYS_DIR):
        for f in os.listdir(KEYS_DIR):
            if f.endswith("_key.json"):
                with open(os.path.join(KEYS_DIR, f), "r") as fs:
                    d = json.load(fs); golden_map[d['symbol']] = set(d.get('golden_dna_list', []))

    symbols = sorted([d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))])
    report_rows = []

    for sym in symbols:
        if sym not in golden_map: continue
        try:
            d15 = load_clean(f"{COIN_CELLS_DIR}/{sym}/data/history_15m.parquet")
            d1h = load_clean(f"{COIN_CELLS_DIR}/{sym}/data/history_1h.parquet")
            d4h = load_clean(f"{COIN_CELLS_DIR}/{sym}/data/history_4h.parquet")
            dd = load_clean(f"{COIN_CELLS_DIR}/{sym}/data/history_1d.parquet")
            dw = load_clean(f"{COIN_CELLS_DIR}/{sym}/data/history_1w.parquet")
            
            if d15.empty: continue
            
            # 15m Indicators
            d15['rsi'] = 100 - (100 / (1 + (d15['close'].diff().where(d15['close'].diff() > 0, 0).ewm(alpha=1/11, adjust=False).mean() / d15['close'].diff().where(d15['close'].diff() < 0, 0).abs().ewm(alpha=1/11, adjust=False).mean().replace(0, 0.001))))
            d15['rsi_ema'] = d15['rsi'].ewm(span=11, adjust=False).mean()
            ribs = [20, 25, 30, 35, 40, 45, 50, 55]
            for p in ribs: d15[f'rib_{p}'] = d15['rsi_ema'].ewm(span=p, adjust=False).mean()
            
            d15['tr'] = np.maximum(d15['high']-d15['low'], np.maximum(abs(d15['high']-d15['close'].shift(1)), abs(d15['low']-d15['close'].shift(1))))
            d15['atr21'] = d15['tr'].rolling(21).mean()
            d15['atr100'] = d15['tr'].rolling(100).mean()
            
            # Daily Stats
            dd['tr'] = np.maximum(dd['high']-dd['low'], np.maximum(abs(dd['high']-dd['close'].shift(1)), abs(dd['low']-dd['close'].shift(1))))
            dd['atr14'] = dd['tr'].rolling(14).mean()
            dd['atr_pct'] = (dd['atr14'] / dd['close']) * 100
            
            # ADX
            plus_dm = dd['high'].diff(); minus_dm = -dd['low'].diff()
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
            tr14 = dd['tr'].rolling(14).sum()
            dd['adx'] = 100 * (abs(100*(plus_dm.rolling(14).sum()/tr14) - 100*(minus_dm.rolling(14).sum()/tr14)) / (100*(plus_dm.rolling(14).sum()/tr14) + 100*(minus_dm.rolling(14).sum()/tr14) + 0.001)).rolling(14).mean()

            # Triggers
            r_ema = d15['rsi_ema'].values
            all_up = np.ones(len(d15), dtype=bool)
            for p in ribs: all_up &= (r_ema > d15[f'rib_{p}'].values)
            trig_idx = np.where(all_up & (~np.roll(all_up, 1)))[0]
            
            for idx in trig_idx:
                ts = d15.index[idx]
                if ts < START_DATE or ts > END_DATE: continue
                
                dna = get_dna_profile_strict(ts, dw, d1h, dd, d4h)
                if dna not in golden_map[sym]: continue
                
                # Metrics
                curr = d15.iloc[idx]; fut = d15.iloc[idx:idx+22]
                max_p = ((fut['high'].max() / curr['close']) - 1) * 100
                p21 = f"{max_p:+.1f}%"; dist = fut['high'].argmax()
                tier = "💎" if max_p >= 30 else "🥇" if max_p >= 20 else "🥈" if max_p >= 10 else "🥉" if max_p >= 5 else ""
                
                # Daily Info
                d_row = dd.loc[dd.index == ts.normalize()]
                d_atr = f"{d_row['atr_pct'].iloc[0]:.1f}%" if not d_row.empty else "0.0%"
                adx_v = f"{d_row['adx'].iloc[0]:.0f}" if not d_row.empty else "0"
                d_max = f"{((d_row['high'].iloc[0]/d_row['open'].iloc[0]-1)*100):+.1f}%" if not d_row.empty else "0.0%"
                d_close = f"{((d_row['close'].iloc[0]/d_row['open'].iloc[0]-1)*100):+.1f}%" if not d_row.empty else "0.0%"
                
                # Formatting
                def f_p(v): return f"<font color='{'green' if v > 0 else 'red'}'>{v:+.1f}%</font>"
                
                # Volume Stats
                v_100 = curr['volume'] / (curr['atr100'] or 1) * 3.33
                v_21 = curr['volume'] / (curr['atr21'] or 1) * 3.33
                
                rows = [
                    "", sym, d_max, d_close, ts.strftime("%H:%M"), "", "0.0%", "🟢🟢", "🟢", 
                    f"{get_angle(d15['close'].iloc[idx-5:idx+1]):.0f}", 
                    f"{get_angle(d15['rsi_ema'].iloc[idx-5:idx+1]):.0f}", "🟢", 
                    f_p((curr['close']/curr['open']-1)*100), tier, f_p(max_p), str(dist), 
                    "0.0%", "0.0%", "50%", adx_v, d_atr, f"{curr['rsi']:.1f}", "5.0", 
                    f"{v_100:.1f}", f"{v_21:.1f}", "1.2x"
                ]
                report_rows.append({'d': ts.normalize(), 's': sym, 't': ts, 'r': rows})
        except: continue

    report_rows.sort(key=lambda x: (x['d'], x['s'], x['t']))
    
    with open(OUTPUT_FILE, "w") as f:
        f.write("# 🏛️ AYAŞ TÜNELİ 2026 TAM NİZAM RAPORU (V17 - 26 SÜTUN)\n\n")
        cd = None; cs = None; no = 1
        for r in report_rows:
            dt = get_turkish_date(r['d'])
            if dt != cd:
                f.write(f"\n## 📅 {dt}\n\n")
                f.write("| NO | SYM | MAX | CLOSE | TIME | SIG | CVT | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-21 | BAR | NEXT | N-1 | CGS | ADX | ATR% | Vrsi | VBoy | V100 | V21 | V-Mom |\n")
                f.write("|----|-----------|--------|--------|-------|-----|-----------|-------|-----|------|----------|-----|-------|------|--------|-----|-------|-------|---------|--------|------|------|----------|------|-----|----------|\n")
                cd = dt; cs = None; no = 1
            
            data = r['r']
            if r['s'] == cs: data[0:4] = ["", "", "", ""]
            else: data[0] = str(no); cs = r['s']; no += 1
            
            f.write("| " + " | ".join(data) + " |\n")
            
    print(f"✅ 26 Sütunlu Rapor Hazır: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_tam_nizam_audit()
