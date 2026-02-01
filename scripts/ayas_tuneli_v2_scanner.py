#!/usr/bin/env python3
"""
AYAŞ TÜNELİ-2 SCANNER (v2.2 - TAM V17 FORMAT)
=============================================
V17 Formatına tam uyum:
- MAX/CLOSE: Günlük Yüzde (Sadece ilk satırda)
- P-21: Tetik Sonrası Max Potansiyel (Her satırda)
- ATR: 15m Dinamik ATR (Her satırda farklı)
- Repeating Rows: NO, SYM, MAX, CLOSE, CGS gizle
"""

import pandas as pd
import numpy as np
import os
import json
import math
from datetime import datetime

# CONFIG
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
KEYS_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys_v2"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/refined_global_report_v2.md"

# Turkish Date Helper
MONTHS_TR = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
}

def get_turkish_date(dt):
    return f"{dt.day} {MONTHS_TR[dt.month]} {dt.year}"

# Tarih
END_DATE = pd.Timestamp("2026-02-02 09:00:00")
START_DATE = END_DATE - pd.Timedelta(days=101) 

def load_clean(path):
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

def get_dna_profile(day, df_w, df_h1, df_d, df_h4):
    try:
        daily_integrity_cutoff = day.normalize()
        # 1H Sızıntı Önlemi:
        # Örn: Saat 15:15'teyiz. 15:00 mumu (15:00-16:00) henüz kapanmadı.
        # df.index < 15:15 dersek 15:00 mumunu alırız -> LEAK.
        # Bu yüzden cutoff = day - 1h (14:15). Index <= 14:15 olmalı. (14:00 mumu gelir).
        h1_cutoff = day - pd.Timedelta(hours=1)
        sub_h1_24 = df_h1[df_h1.index <= h1_cutoff].tail(24)
        
        sub_d = df_d[df_d.index < daily_integrity_cutoff].tail(100)
        
        # Haftalık (Weekly) Sızıntı Önlemi:
        weekly_cutoff = day - pd.Timedelta(days=7)
        sub_w = df_w[df_w.index < weekly_cutoff].tail(52)
        
        # 4H Sızıntı Önlemi:
        # Örn: 15:15'teyiz. 12:00 mumu (12:00-16:00) kapanmadı.
        # cutoff = 15:15 - 4h = 11:15.
        # 12:00 <= 11:15 (False) -> Gelmez.
        # 08:00 <= 11:15 (True) -> Gelir (08:00-12:00 mumu).
        h4_cutoff = day - pd.Timedelta(hours=4)
        sub_h4 = df_h4[df_h4.index <= h4_cutoff].tail(42)
        
        if sub_w.empty or sub_d.empty or sub_h1_24.empty: return "neutral"
        
        # Faz
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
        
        # Acc
        if len(sub_h1_24) >= 10:
            sub_h1_24['ema9'] = sub_h1_24['close'].ewm(span=9, adjust=False).mean()
            sub_h1_24['ema21'] = sub_h1_24['close'].ewm(span=21, adjust=False).mean()
            squeeze_pct = abs(sub_h1_24['ema9'].iloc[-1] - sub_h1_24['ema21'].iloc[-1]) / sub_h1_24['close'].iloc[-1] * 100
            if squeeze_pct <= 0.3: acc = "tight_squeeze"
            elif squeeze_pct <= 0.8: acc = "micro_squeeze"
            elif squeeze_pct <= 1.5: acc = "normal_gap"
            else: acc = "expanded_gap"
        else: acc = "no_data"
        
        # Harm
        h1_trend=True; h4_trend=True; d_trend=True
        if len(sub_h1_24) >= 21:
            sub_h1_24['ema21_h'] = sub_h1_24['close'].ewm(span=21, adjust=False).mean()
            h1_trend = sub_h1_24['close'].iloc[-1] > sub_h1_24['ema21_h'].iloc[-1]
        if len(sub_h4) >= 21:
            sub_h4['ema21_4h'] = sub_h4['close'].ewm(span=21, adjust=False).mean()
            h4_trend = sub_h4['close'].iloc[-1] > sub_h4['ema21_4h'].iloc[-1]
        if len(sub_d) >= 21:
            sub_d['ema21_d'] = sub_d['close'].ewm(span=21, adjust=False).mean()
            d_trend = sub_d['close'].iloc[-1] > sub_d['ema21_d'].iloc[-1]
        trend_count = sum([h1_trend, h4_trend, d_trend])
        if trend_count == 3: harm = "harmony_L3"
        elif trend_count == 2: harm = "harmony_L2"
        elif trend_count == 1: harm = "harmony_L1"
        else: harm = "discord"
        
        # Ritim
        if len(sub_d) >= 21:
            vol_ratio = sub_d['volume'].iloc[-1] / sub_d['volume'].rolling(21).mean().iloc[-1]
            if vol_ratio >= 2.5: ritim = "volume_explosion"
            elif vol_ratio >= 1.5: ritim = "volume_surge"
            elif vol_ratio >= 0.8: ritim = "volume_normal"
            else: ritim = "volume_dry"
        else: ritim = "no_data"
        
        # Ctx
        if len(sub_d) >= 50:
            max_52w = sub_d['high'].tail(50).max()
            current_p = sub_d['close'].iloc[-1]
            dist = ((current_p / max_52w) - 1) * 100
            if dist >= -10: ctx = "near_ath"
            elif dist >= -30: ctx = "mid_range"
            elif dist >= -50: ctx = "discounted"
            else: ctx = "deep_discount"
        else: ctx = "no_data"
        
        # Enerji
        if len(sub_d) >= 10:
            vol_5 = sub_d['volume'].tail(5).mean()
            vol_10 = sub_d['volume'].tail(10).mean()
            if vol_5 > vol_10 * 1.2: enerji = "rising_energy"
            elif vol_5 < vol_10 * 0.8: enerji = "fading_energy"
            else: enerji = "stable_energy"
        else: enerji = "no_data"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except: return "neutral"

def run_scanner():
    print("AYAŞ TÜNELİ-2 SCANNER (V17 FORMAT - GÜNCELLENMİŞ) ÇALIŞIYOR...")
    
    golden_map = {}
    if os.path.exists(KEYS_DIR):
        for f_name in os.listdir(KEYS_DIR):
            if f_name.endswith("_key.json"):
                with open(os.path.join(KEYS_DIR, f_name), "r") as f:
                    data = json.load(f)
                    golden_map[data['symbol']] = set(data['golden_dna_list'])

    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    report_rows = []

    for idx_scan, symbol in enumerate(symbols):
        if symbol not in golden_map: continue
        
        try:
            df_15m = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet")
            df_1h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
            df_4h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
            df_1d = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
            df_1w = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")
            
            # --- Indicators ---
            delta = df_15m['close'].diff()
            alpha = 1 / 11
            gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
            df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
            df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
            
            ribbon_periods = [20, 25, 30, 35, 40, 45, 50, 55]
            rsi_ribbon_cols = []
            for p in ribbon_periods:
                df_15m[f'rsi_rib_{p}'] = df_15m['rsi_ema'].ewm(span=p, adjust=False).mean()
                rsi_ribbon_cols.append(f'rsi_rib_{p}')
            
            # 15m ATR for Display (Dynamic)
            df_15m['tr'] = np.maximum(df_15m['high'] - df_15m['low'], np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)), abs(df_15m['low'] - df_15m['close'].shift(1))))
            df_15m['atr21'] = df_15m['tr'].rolling(21).mean()
            df_15m['atr100'] = df_15m['tr'].rolling(100).mean()
            df_15m['atr_dynamic'] = (df_15m['atr21'] / df_15m['close']) * 100
            
            # Daily ATR for Tooltip
            d_tr = np.maximum(df_1d['high'] - df_1d['low'], np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), abs(df_1d['low'] - df_1d['close'].shift(1))))
            df_1d['atr14'] = d_tr.rolling(14).mean()
            df_1d['atr_pct'] = (df_1d['atr14'] / df_1d['close']) * 100
            
            # ADX
            plus_dm = df_1d['high'].diff()
            minus_dm = -df_1d['low'].diff()
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
            tr14_sum = d_tr.rolling(14).sum()
            plus_di = 100 * (plus_dm.rolling(14).sum() / tr14_sum)
            minus_di = 100 * (minus_dm.rolling(14).sum() / tr14_sum)
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.001)
            df_1d['adx14'] = dx.rolling(14).mean()
            
            df_1h['ema21'] = df_1h['close'].ewm(span=21, adjust=False).mean()
            df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()

            # --- Trigger Scan ---
            rsi_ema_vals = df_15m['rsi_ema'].values
            all_above = np.ones(len(df_15m), dtype=bool)
            for col in rsi_ribbon_cols:
                all_above &= (rsi_ema_vals > df_15m[col].values)
            
            prev_not_above = ~np.roll(all_above, 1)
            prev_not_above[0] = True
            trigger_indices = np.where(prev_not_above & all_above)[0]
            
            for idx in trigger_indices:
                trig_time = df_15m.index[idx]
                if trig_time < START_DATE or trig_time > END_DATE: continue
                
                dna = get_dna_profile(trig_time, df_1w, df_1h, df_1d, df_4h)
                if dna not in golden_map[symbol]: continue
                
                # --- METRICS ---
                current_p = df_15m['close'].iloc[idx]
                
                # 1. P-21 (Performance 21 bars) - Was 'max_pct' in v2.1
                future = df_15m.iloc[idx:idx+22]
                if len(future) < 2: # Min 1 bar after trigger needed for peak
                    p21_pct = 0.0; peak_dist = 0; peak_p = current_p
                else:
                    peak_idx_rel = future['high'].argmax()
                    peak_p = future['high'].iloc[peak_idx_rel]
                    peak_dist = peak_idx_rel
                    p21_pct = ((peak_p / current_p) - 1) * 100
                
                # 2. MAX & CLOSE (Daily Stats)
                try:
                    d_idx = df_1d.index.searchsorted(trig_time.normalize())
                    if d_idx < len(df_1d):
                        if df_1d.index[d_idx] == trig_time.normalize():
                           d_open = df_1d['open'].iloc[d_idx]
                           d_high = df_1d['high'].iloc[d_idx]
                           d_close = df_1d['close'].iloc[d_idx]
                           max_pct = ((d_high / d_open) - 1) * 100
                           close_pct = ((d_close / d_open) - 1) * 100
                        else: max_pct=0; close_pct=0 # Should match date
                    else: max_pct=0; close_pct=0
                except: max_pct=0; close_pct=0

                # NEXT
                next_pct = 0.0
                if len(future) > peak_dist + 1:
                    n_c = future['close'].iloc[peak_dist + 1]
                    next_pct = ((n_c - peak_p) / peak_p) * 100
                    
                # N-1
                next_next_pct = 0.0
                if len(future) > peak_dist + 2:
                    nn_c = future['close'].iloc[peak_dist + 2]
                    n_c = future['close'].iloc[peak_dist + 1]
                    next_next_pct = ((nn_c - n_c) / n_c) * 100

                # CVT
                try:
                    yesterday = trig_time - pd.Timedelta(days=1)
                    y_mask = df_15m.index.normalize() == yesterday.normalize()
                    y_data = df_15m[y_mask]
                    if len(y_data) >= 16:
                        last_4h = y_data.tail(16)
                        cvt = ((last_4h['close'].iloc[-1] / last_4h['open'].iloc[0]) - 1) * 100
                    else: cvt = 0.0
                except: cvt = 0.0

                # ADX - ATR
                try:
                    d_row = df_1d.loc[df_1d.index.normalize() == trig_time.normalize()]
                    if not d_row.empty:
                        adx = d_row['adx14'].values[0]
                        d_atr = d_row['atr_pct'].values[0]
                    else:
                        adx = df_1d['adx14'].iloc[-1]
                        d_atr = df_1d['atr_pct'].iloc[-1]
                except: adx=0; d_atr=0
                
                atr_dyn = df_15m['atr_dynamic'].iloc[idx] # Trigger ATR

                # TREND
                cutoff_4h = trig_time - pd.Timedelta(hours=4)
                last_4h = df_4h[df_4h.index <= cutoff_4h]
                t4 = "🟢" if not last_4h.empty and last_4h.iloc[-1]['close'] > last_4h.iloc[-1]['ema21'] else "🔴"
                cutoff_1h = trig_time - pd.Timedelta(hours=1)
                last_1h = df_1h[df_1h.index <= cutoff_1h]
                t1 = "🟢" if not last_1h.empty and last_1h.iloc[-1]['close'] > last_1h.iloc[-1]['ema21'] else "🔴"
                trend_str = f"{t4}{t1}"
                
                # POS/VAL
                ctx = dna.split('|')[4]
                pos_str = "🟢" if ctx == "near_ath" else ("🟡" if ctx == "mid_range" else "🔴")
                acc = dna.split('|')[1]
                val_str = "💚" if "squeeze" in acc else ("🟡" if "normal" in acc else "❤️")
                
                # ANG
                ang_val = get_angle(df_15m['close'].iloc[idx-5:idx+1])
                ang_str = "🟢" if ang_val > 60 else ("🟡" if ang_val > 30 else "🔴")
                r_ang_val = get_angle(df_15m['rsi_ema'].iloc[idx-5:idx+1])
                
                # Volume
                v_idx = (df_15m['tr'].iloc[idx] / (df_15m['atr100'].iloc[idx] or 1)) * 3.33 
                v_dyn = (df_15m['tr'].iloc[idx] / (df_15m['atr21'].iloc[idx] or 1)) * 3.33 
                v_mom = (v_idx / 3.0) 
                v_hyb = min(15.0, v_idx * (df_15m['rsi'].iloc[idx]/50)) 
                tr_val = df_15m['tr'].iloc[idx] if df_15m['tr'].iloc[idx] > 0 else 0.0001
                v_boy = (abs(df_15m['close'].iloc[idx]-df_15m['open'].iloc[idx])/tr_val)*10 
                
                trigger_pct = ((df_15m['close'].iloc[idx] - df_15m['open'].iloc[idx]) / df_15m['open'].iloc[idx]) * 100

                # --- FORMATTING ---
                def fmt_pct(v, bold=False):
                    c = "green" if v > 0 else "red"
                    s = f"{v:+.1f}%"
                    if bold: s = f"**{s}**"
                    return f"<font color='{c}'>{s}</font>"
                
                MAX_f = fmt_pct(max_pct, bold=(max_pct>10))
                CLOSE_f = fmt_pct(close_pct)
                CVT_f = fmt_pct(cvt, bold=(abs(cvt)>=1.0))
                
                ra_s = f"{r_ang_val:.0f}°"
                if r_ang_val >= 45: RAng_f = f"<font color='#00FF00'>**+{ra_s}**</font>"
                elif r_ang_val >= 10: RAng_f = f"<font color='green'>+{ra_s}</font>"
                elif r_ang_val <= -45: RAng_f = f"<font color='red'>**{ra_s}**</font>"
                else: RAng_f = f"<font color='gray'>{ra_s}</font>"
                
                P_f = fmt_pct(trigger_pct, bold=(abs(trigger_pct)>10))
                
                TIER = ""
                if p21_pct >= 30: TIER = "💎"
                elif p21_pct >= 20: TIER = "🥇"
                elif p21_pct >= 10: TIER = "🥈"
                elif p21_pct >= 5: TIER = "🥉"
                
                P21_f = fmt_pct(p21_pct)
                
                BAR_f = str(peak_dist)
                if peak_dist == 0: BAR_f = f"<font color='red'>**0**</font>"
                
                NEXT_f = fmt_pct(next_pct)
                N1_f = fmt_pct(next_next_pct)
                CGS_f = "<font color='gray'>N/A</font>"
                ADX_f = f"<font color='green'>**{adx:.0f}**</font>" if adx>=40 else f"{adx:.0f}"
                
                tooltip = f"Tetik ATR: {atr_dyn:.1f}% &#013;Günlük ATR: {d_atr:.1f}%"
                ATR_v = f"{atr_dyn:.1f}%"
                if atr_dyn >= 4.0: ATR_v = f"<font color='#00FF00'>**{ATR_v}**</font>"
                elif atr_dyn >= 2.0: ATR_v = f"<font color='green'>{ATR_v}</font>"
                ATR_f = f"<span title='{tooltip}'>{ATR_v}</span>"
                
                def fmt_v(v, thr=8.0): return f"<font color='green'>**{v:.1f}**</font>" if v>=thr else f"{v:.1f}"
                
                row = {
                    'date': trig_time.normalize(),
                    'time': trig_time.strftime("%H:%M"),
                    'sym': symbol,
                    'MAX': MAX_f,
                    'CLOSE': CLOSE_f,
                    'SIG': "", 
                    'CVT': CVT_f,
                    'TREND': trend_str,
                    'POS': pos_str,
                    'ANG': ang_str,
                    'R-Ang': RAng_f,
                    'VAL': val_str,
                    'P': P_f,
                    'TIER': TIER,
                    'P-21': P21_f,
                    'BAR': BAR_f,
                    'NEXT': NEXT_f,
                    'N-1': N1_f,
                    'CGS': CGS_f,
                    'ADX': ADX_f,
                    'ATR%': ATR_f,
                    'Vrsi': fmt_v(v_hyb),
                    'VBoy': fmt_v(v_boy),
                    'V100': fmt_v(v_idx),
                    'V21': fmt_v(v_dyn),
                    'V-Mom': f"{v_mom:.1f}x"
                }
                report_rows.append(row)
                
        except: pass
        
    report_rows.sort(key=lambda x: (x['date'], x['sym'], x['time']))
    
    with open(OUTPUT_FILE, "w") as f:
        f.write("# TEZAVER GLOBAL AUDIT REPORT (AYAŞ TÜNELİ-2 RAPORU v2.2)\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        
        current_date = None
        current_sym = None
        idx_counter = 1
        
        for r in report_rows:
            d_tr = get_turkish_date(r['date'])
            if d_tr != current_date:
                dc = len([x for x in report_rows if x['date'] == r['date']])
                f.write(f"\n## 📅 {d_tr} (Ayaş-2: {dc})\n\n")
                f.write("### 🚇 AYAŞ TÜNELİ-2\n\n")
                f.write("| NO | SYM | MAX | CLOSE | TIME | SIG | CVT | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-21 | BAR | NEXT | N-1 | CGS | ADX | ATR% | Vrsi | VBoy | V100 | V21 | V-Mom |\n")
                f.write("|----|-----------|--------|--------|-------|-----|-----------|-------|-----|------|----------|-----|-------|------|--------|-----|-------|-------|---------|--------|------|------|----------|------|-----|----------|\n")
                current_date = d_tr
                current_sym = None
                idx_counter = 1
            
            # Repetition Handling
            if r['sym'] == current_sym:
                disp_no = ""
                disp_sym = ""
                disp_max = ""
                disp_close = ""
                # Keep CGS/ADX/CVT? V17 shows CGS/ADX repeated?
                # V17 line 11: CGS is present (different value? 50%).
                # ADX repeated (54).
                # User complaint: "atr yi böyle yazmana gerek olmadığı gibi".
                # If values are identical, maybe blank them?
                # But ATR is now dynamic, so it changes.
                # ADX (Daily) is static. Let's blank ADX if repeated?
                # V17 repeats ADX. User said "don't write coin name... and don't write ATR LIKE THIS".
                # I interpreted "like this" as "repeating static daily value".
                # Now ATR is dynamic.
                # Safe bet: Blank NO, SYM, MAX, CLOSE. Keep others.
            else:
                disp_no = str(idx_counter)
                disp_sym = r['sym']
                disp_max = r['MAX']
                disp_close = r['CLOSE']
                current_sym = r['sym']
                idx_counter += 1
                
            cols = [
                disp_no,
                disp_sym,
                disp_max,
                disp_close,
                r['time'],
                r['SIG'],
                r['CVT'],
                r['TREND'],
                r['POS'],
                r['ANG'],
                r['R-Ang'],
                r['VAL'],
                r['P'],
                r['TIER'],
                r['P-21'],
                r['BAR'],
                r['NEXT'],
                r['N-1'],
                r['CGS'],
                r['ADX'],
                r['ATR%'],
                r['Vrsi'],
                r['VBoy'],
                r['V100'],
                r['V21'],
                r['V-Mom']
            ]
            f.write("| " + " | ".join(cols) + " |\n")
            
    print(f"Rapor oluşturuldu: {OUTPUT_FILE}")
    print(f"Toplam Satır: {len(report_rows)}")

if __name__ == "__main__":
    run_scanner()
