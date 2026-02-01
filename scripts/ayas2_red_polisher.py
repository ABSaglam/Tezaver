#!/usr/bin/env python3
"""
KIRMIZI LİSTE: CLONE V17 FORMAT
===============================
Hedef: refined_global_report_v17.md ile birebir aynı format.
"""

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime
import locale
import math

INPUT_FILE = "/Users/alisaglam/TezaverMac/refined_global_report_v2.md"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/KIRMIZI_LISTE_FULL_V17.md"
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

sys.path.insert(0, '/Users/alisaglam/TezaverMac/scripts')
try:
    from portakal_sikacagi import calculate_cgs_score
    CGS_AVAILABLE = True
except ImportError:
    CGS_AVAILABLE = False

# Turkish Date Helper
MONTHS_TR = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
}

def get_turkish_date(dt):
    return f"{dt.day} {MONTHS_TR[dt.month]} {dt.year}"

def load_clean(path):
    try:
        df = pd.read_parquet(path)
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        df = df[~df.index.duplicated(keep='last')]
        return df.sort_index()
    except: return pd.DataFrame()

def process_signal(sym, trig_time_str):
    try:
        trig_time = pd.Timestamp(trig_time_str)
        base_path = f"{COIN_CELLS_DIR}/{sym}/data"
        df_15m = load_clean(f"{base_path}/history_15m.parquet")
        if df_15m.empty: return None

        df_1h = load_clean(f"{base_path}/history_1h.parquet")
        df_4h = load_clean(f"{base_path}/history_4h.parquet")
        df_1d = load_clean(f"{base_path}/history_1d.parquet")

        # Indicators
        delta = df_15m['close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean().replace(0, 0.001)
        df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
        df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
        
        for p in [20, 25, 30, 35, 40, 45, 50, 55]:
            df_15m[f'rsi_rib_{p}'] = df_15m['rsi_ema'].ewm(span=p, adjust=False).mean()
            
        tr = np.maximum(df_15m['high'] - df_15m['low'], np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)), abs(df_15m['low'] - df_15m['close'].shift(1))))
        df_15m['tr'] = tr
        df_15m['atr100'] = tr.rolling(100).mean()
        df_15m['atr21'] = tr.rolling(21).mean()
        
        # Trigger Index
        if trig_time not in df_15m.index: return None
        i = df_15m.index.get_loc(trig_time)
        if isinstance(i, slice) or isinstance(i, np.ndarray): i = i[0]
        
        entry_close = df_15m['close'].iloc[i]
        candle_open = df_15m['open'].iloc[i]
        
        # P: Trigger Candle Body Size
        p_val_num = ((entry_close - candle_open) / candle_open) * 100
        p_s = f"{p_val_num:+.1f}%"
        if p_val_num > 0: p_s = f"<font color='green'>{p_s}</font>"
        elif p_val_num < 0: p_s = f"<font color='red'>{p_s}</font>"
        
        # --- Future / Max ---
        # P-21 Definition: Max Peak within next 21 bars (approx 5.25 hours)
        limit_21 = min(i + 22, len(df_15m))
        p21_peak = 0.0
        
        if i + 1 < limit_21:
            slice_21 = df_15m['high'].iloc[i + 1 : limit_21]
            if len(slice_21) > 0:
                 max_p_21 = slice_21.max()
                 p21_peak = ((max_p_21 - entry_close) / entry_close) * 100
        
        p21_val = f"{p21_peak:+.1f}%"
        if p21_peak > 0: p21_val = f"<font color='green'>{p21_val}</font>"
        
        # MAX Definition: Max Peak in extended range (e.g. 96 bars / 24h)
        limit_max = min(i + 97, len(df_15m))
        peak_dist_real = 0
        peak_p = entry_close
        
        if i + 1 < limit_max:
            val_slice = df_15m['high'].iloc[i + 1 : limit_max]
            if len(val_slice) > 0:
                peak_p = val_slice.max()
                peak_dist_real = np.argmax(val_slice) + 1
            else: peak_p = entry_close; peak_dist_real = 0
            
            # EXIT (Close at limit_21 or end)
            # User implies P-21 is peak, so 'Close' typically refers to result at P-21 horizon?
            # Let's keep Close as Return at 21st bar (Trend result)
            exit_idx = limit_21 - 1
            exit_close = df_15m['close'].iloc[exit_idx]
            exit_ret = ((exit_close - entry_close) / entry_close) * 100
        else: 
            peak_p = entry_close; peak_dist_real = 0
            exit_ret = 0.0

        max_gain = ((peak_p - entry_close) / entry_close) * 100
        if max_gain < p21_peak: max_gain = p21_peak # Max cannot be less than P-21
        
        tier = "-"
        if max_gain >= 30: tier = "💎"
        elif max_gain >= 20: tier = "🥇"
        elif max_gain >= 10: tier = "🥈"
        elif max_gain >= 5: tier = "🥉"
        
        # Format Close Return
        close_s = f"{exit_ret:+.1f}%"
        if exit_ret > 0: close_s = f"<font color='green'>{close_s}</font>"
        elif exit_ret < 0: close_s = f"<font color='red'>{close_s}</font>"

        # --- Metrics ---
        # CVT = Trigger Percent (Close - Open) / Open
        # Wait, P is now Body %. CVT was Body %. 
        # Only one column fits.
        # Let's check Ref Report again. CVT -3.3%, P +0.5%.
        # Maybe CVT is Daily Change? 
        # Let's Calculate Daily Change for CVT.
        df_1d = load_clean(f"{base_path}/history_1d.parquet")
        daily_open = 0
        if not df_1d.empty:
             d_idx = df_1d.index.searchsorted(trig_time)
             if d_idx < len(df_1d):
                 # Normalized date match?
                 # Fast approx: Get open of the day containing trigger
                 # Since 1d index is open time? 
                 # Let's use 15m[open] at 00:00? 
                 # Or just use df_1d closest row.
                 pass
        
        # Simpler CVT: Distance from Daily Open (approx)
        # 15m open at 00:00
        try:
             day_start = pd.Timestamp(trig_time.year, trig_time.month, trig_time.day)
             if day_start in df_15m.index:
                 daily_open = df_15m['open'].loc[day_start]
                 cvt_val = ((entry_close - daily_open) / daily_open) * 100
             else:
                 cvt_val = 0
        except: cvt_val = 0
            
        cvt_s = f"{cvt_val:+.1f}%"
        if cvt_val > 0: cvt_s = f"<font color='green'>{cvt_s}</font>"
        else: cvt_s = f"<font color='red'>**{cvt_s}**</font>"

        # TREND (H4/H1)
        t4 = "⚪"; t1 = "⚪"
        if not df_4h.empty:
            h4_row = df_4h[df_4h.index <= trig_time].tail(1)
            if not h4_row.empty:
                ema21_4h = df_4h['close'].ewm(span=21, adjust=False).mean()
                try:
                    idx_4h = df_4h.index.get_loc(h4_row.index[0])
                    if h4_row['close'].iloc[0] > ema21_4h.iloc[idx_4h]: t4 = "🟢"
                    else: t4 = "🔴"
                except: pass
        if not df_1h.empty:
            h1_row = df_1h[df_1h.index <= trig_time].tail(1)
            if not h1_row.empty:
                ema21_1h = df_1h['close'].ewm(span=21, adjust=False).mean()
                try:
                    idx_1h = df_1h.index.get_loc(h1_row.index[0])
                    if h1_row['close'].iloc[0] > ema21_1h.iloc[idx_1h]: t1 = "🟢"
                    else: t1 = "🔴"
                except: pass
        trend_s = f"{t4}{t1}"

        # P (Previous Bar Change) - UPDATED: Now P is Trigger Body % (Calculated above)
        # Removing old p_chg logic
        # p_s is already defined above


        # V-Mom / V-Index Logic
        tr_val = df_15m['tr'].iloc[i]
        atr100_val = df_15m['atr100'].iloc[i] or 0.001
        v_idx = min(10.0, (tr_val / atr100_val) * 3.33)
        atr21_val = df_15m['atr21'].iloc[i] or 0.001
        v_dyn = min(10.0, (tr_val / atr21_val) * 3.33)
        
        past_vidx = []
        for k in range(1, 4):
            if i-k >= 0:
                p_tr = df_15m['tr'].iloc[i-k]
                p_atr = df_15m['atr100'].iloc[i-k] or 0.001
                past_vidx.append((p_tr/p_atr)*3.33)
        avg_past = np.mean(past_vidx) if past_vidx else 0.001
        v_mom = (v_idx / avg_past) if avg_past > 0 else 0
        
        body = abs(df_15m['close'].iloc[i] - df_15m['open'].iloc[i])
        v_eff = (body / tr_val) * 10.0 if tr_val>0 else 0
        rsi_pow = df_15m['rsi'].iloc[i] / 50.0
        v_hyb = min(15.0, v_idx * rsi_pow) 

        # Next / N-1
        next_val = "-"
        next_next_val = "-"
        if i + peak_dist_real + 1 < len(df_15m):
            n_c = df_15m['close'].iloc[i + peak_dist_real + 1]
            n_pct = ((n_c - peak_p) / peak_p) * 100
            next_val = f"{n_pct:+.1f}%"
            if n_pct>0: next_val = f"<font color='green'>{next_val}</font>"
            else: next_val = f"<font color='red'>{next_val}</font>"
            
            if i + peak_dist_real + 2 < len(df_15m):
                nn_c = df_15m['close'].iloc[i + peak_dist_real + 2]
                nn_pct = ((nn_c - n_c) / n_c) * 100
                next_next_val = f"{nn_pct:+.1f}%"
                if nn_pct>0: next_next_val = f"<font color='green'>{next_next_val}</font>"
                else: next_next_val = f"<font color='red'>{next_next_val}</font>"

        # ANG / POS
        val_20 = df_15m['rsi_rib_20'].iloc[i]
        val_55 = df_15m['rsi_rib_55'].iloc[i]
        val_20_p = df_15m['rsi_rib_20'].iloc[i-1] if i>0 else val_20
        val_55_p = df_15m['rsi_rib_55'].iloc[i-1] if i>0 else val_55
        
        curr = val_20 if val_20 > val_55 else val_55
        prev = val_20_p if val_20 > val_55 else val_55_p
        
        slope = (curr - prev) / 2.0
        angle_deg = math.degrees(math.atan(slope))
        ang_score = angle_deg / 4.5
        ang_f = f"{ang_score:+.1f}"
        if ang_score>=0: ang_f = f"<font color='green'>{ang_f}</font>"
        
        if curr < 30: pos_icon = "⚫"
        elif curr < 50: pos_icon = "🔴"
        elif curr < 60: pos_icon = "🟡"
        elif curr < 70: pos_icon = "🟢"
        else: pos_icon = "🟠"
        
        # R-Ang
        rsi_ema_now = df_15m['rsi_ema'].iloc[i]
        rsi_ema_prev = df_15m['rsi_ema'].iloc[i-1] if i>0 else rsi_ema_now
        r_slope = rsi_ema_now - rsi_ema_prev
        r_ang = math.degrees(math.atan(r_slope))
        r_ang_s = f"{r_ang:+.0f}°"
        if r_ang > 45: r_ang_s = f"<font color='#00FF00'>**{r_ang_s}**</font>"
        elif r_ang > 0: r_ang_s = f"<font color='green'>{r_ang_s}</font>"
        
        # ADX / ATR
        d_cutoff = trig_time.normalize()
        df_1d_cut = df_1d[df_1d.index <= d_cutoff]
        atr_pct = 0; adx_val = 0; d_atr = 0
        if not df_1d_cut.empty:
            d_tr = np.maximum(df_1d_cut['high'] - df_1d_cut['low'], np.maximum(abs(df_1d_cut['high'] - df_1d_cut['close'].shift(1)), abs(df_1d_cut['low'] - df_1d_cut['close'].shift(1))))
            atr14 = d_tr.rolling(14).mean().iloc[-1]
            d_atr = (atr14 / df_1d_cut['close'].iloc[-1]) * 100
            
            plus_dm = df_1d_cut['high'].diff(); minus_dm = -df_1d_cut['low'].diff()
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
            tr14_sum = d_tr.rolling(14).sum()
            dx = 100 * abs((100*(plus_dm.rolling(14).sum()/tr14_sum)) - (100*(minus_dm.rolling(14).sum()/tr14_sum))) / ((100*(plus_dm.rolling(14).sum()/tr14_sum)) + (100*(minus_dm.rolling(14).sum()/tr14_sum)) + 0.001)
            adx_val = dx.rolling(14).mean().iloc[-1]
        
        adx_s = f"{int(adx_val)}"
        if adx_val > 50: adx_s = f"<font color='green'>**{adx_s}**</font>"
        elif adx_val > 25: adx_s = f"<font color='green'>{adx_s}</font>"
        
        atr_s = f"{d_atr:.1f}%"
        atr_tooltip = f"<span title='Tetik ATR: {atr_pct:.1f}% &#013;Günlük ATR: {d_atr:.1f}%'>{atr_s}</span>"
        if d_atr > 5: atr_tooltip = f"<span title='Tetik ATR: ...'><font color='green'>{atr_s}</font></span>"

        # CGS
        cgs_val = 50
        if CGS_AVAILABLE:
            cgs_val = calculate_cgs_score({
                'd_atr': d_atr, 'd_adx': adx_val, 'rsi': df_15m['rsi'].iloc[i],
                'ang_score': ang_score, 'ribbon_above': True, 'trend_score': 2, 'pos': "green" if pos_icon == "🟢" else "red"
            })
        else:
             if r_ang > 10: cgs_val += 10
             if v_mom > 1: cgs_val += 10
        
        cgs_s = f"{cgs_val}%"
        if cgs_val >= 80: cgs_s = f"<font color='#00FF00'>**{cgs_s}**</font>"
        elif cgs_val >= 50: cgs_s = f"<font color='green'>**{cgs_s}**</font>"

        max_s = f"{max_gain:+.1f}%"
        if max_gain > 5: max_s = f"<font color='green'>{max_s}</font>"
        
        # Volume Format
        vrsi_s = f"{v_dyn:.1f}"; veff_s = f"{v_eff:.1f}"; vhyb_s = f"{v_hyb:.1f}"; vmom_s = f"{v_mom:.1f}x"
        if v_dyn >= 8: vrsi_s = f"<font color='green'>**{vrsi_s}**</font>"
        if v_eff >= 7: veff_s = f"<font color='green'>**{veff_s}**</font>"
        if v_hyb >= 7: vhyb_s = f"<font color='green'>{vhyb_s}</font>"
        if v_mom > 1.5: vmom_s = f"<font color='green'>**{vmom_s}**</font>"
        
        v21_val = "-"
        if i >= 21:
            v_ma21 = df_15m['volume'].iloc[i-21:i].mean()
            v_now = df_15m['volume'].iloc[i]
            if v_ma21 > 0:
                ratio = v_now / v_ma21; v21_str = f"{ratio:.1f}x"
                if ratio > 2.0: v21_val = f"<font color='green'>**{v21_str}**</font>"
                else: v21_val = f"<font color='gray'>{v21_str}</font>"

        return {
            "max": max_s, "tier": tier, "cgs": cgs_s, "r_ang": r_ang_s, "ang": ang_f,
            "pos": pos_icon, "adx": adx_s, "atr": atr_tooltip, "vrsi": vrsi_s, "vboy": veff_s, "v100": vhyb_s, "vmom": vmom_s,
            "bar": f"{peak_dist_real}", "next": next_val, "n_1": next_next_val, "val": "❤️", "p": p_s, 
            "p21": p21_val, "trend": trend_s, "cvt": cvt_s, "v21": v21_val,
            "close_ret": close_s
        }

    except Exception: return None

def main():
    print("🔴 RED POLISHER PRO (CLONE V17 + REAL CLOSE) BAŞLIYOR...")
    
    with open(INPUT_FILE, "r") as f:
        lines = f.readlines()
    
    all_rows = []
    
    seen_signals = set()
    current_date_from_header = None
    for line in lines:
        line = line.strip()
        if line.startswith("## 📅"):
            # Header format: ## 📅 25 Ekim 2025 (Ayaş-2: 8)
            try:
                header_date_str = line.split("📅")[1].split("(")[0].strip()
                # Parse "25 Ekim 2025" -> standard date
                day, month_tr, year = header_date_str.split()
                month_num = [k for k, v in MONTHS_TR.items() if v == month_tr][0]
                current_date_from_header = pd.Timestamp(year=int(year), month=int(month_num), day=int(day))
            except:
                continue
            continue
            
        if not line.startswith("|") or "---" in line or "NO" in line: continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 10: continue
        
        # We need the date from the header because common lines only have time (HH:MM)
        if current_date_from_header is None: continue
        
        sym = parts[2].strip()
        time_only = parts[5].strip() # 00:45 etc
        no = parts[1].strip()
        sig_raw = parts[6].strip()
        if sig_raw == "-" or sig_raw == "": sig_raw = "RSI-EMA"
        
        try:
            h, m = time_only.split(":")
            dt = current_date_from_header.replace(hour=int(h), minute=int(m))
        except:
            continue
        
        day_key = dt.strftime("%Y-%m-%d")
        sig_key = (sym, dt)
        if sig_key in seen_signals: continue
        seen_signals.add(sig_key)
        
        all_rows.append({
            "dt": dt,
            "day_key": day_key,
            "sym": sym,
            "time_str": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "no": no,
            "sig": sig_raw
        })

    # Sort ASCENDING (Chronological)
    all_rows.sort(key=lambda x: (x['dt'], x['sym']))
    
    grouped_lines = []
    grouped_lines.append("# TEZAVER GLOBAL AUDIT REPORT (AYAŞ TÜNELİ + KIRMIZI LİSTE) v17\n")
    grouped_lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    # Process all signals first to count valid outcomes
    processed_results = []
    day_counts = {}
    
    print(f"Processing {len(all_rows)} signals...")
    for idx_p, r in enumerate(all_rows):
        res = process_signal(r['sym'], r['time_str'])
        if not res: continue
        
        processed_results.append({
            "meta": r,
            "data": res
        })
        
        day_tr = get_turkish_date(r['dt'])
        day_counts[day_tr] = day_counts.get(day_tr, 0) + 1
        
        if (idx_p + 1) % 50 == 0:
            print(f"  Processed: {idx_p + 1}/{len(all_rows)}")

    processed = 0
    current_day = None
    current_sym = None
    for item in processed_results:
        r = item['meta']
        res = item['data']
        # Use a more reliable day key for comparison
        day_key = r['dt'].strftime("%Y-%m-%d")
        day_tr = get_turkish_date(r['dt'])
        
        if day_key != current_day:
            if current_day is not None: 
                grouped_lines.append("\n")
            grouped_lines.append(f"## 📅 {day_tr} (Ayaş: {day_counts.get(day_tr, 0)})\n\n")
            grouped_lines.append("### 🚇 AYAŞ TÜNELİ\n\n")
            grouped_lines.append("| NO | SYM | MAX | CLOSE | TIME | SIG | CVT | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-21 | BAR | NEXT | N-1 | CGS | ADX | ATR% | Vrsi | VBoy | V100 | V21 | V-Mom |\n")
            grouped_lines.append("|----|-----------|--------|--------|-------|-----|-----------|-------|-----|------|----------|-----|-------|------|--------|-----|-------|-------|---------|--------|------|------|----------|------|-----|----------|\n")
            current_day = day_key
            current_sym = None  # Reset symbol grouping for new day
        
        is_same = (r['sym'] == current_sym)
        current_sym = r['sym']
        
        d_no = r['no'] if not is_same else ""
        d_sym = r['sym'] if not is_same else ""
        d_close = res['close_ret']
        d_max = res['max']
        
        row = f"| {d_no} | {d_sym} | {d_max} | {d_close} | {r['time_str'][-5:]} | {r['sig']} | {res['cvt']} | {res['trend']} | {res['pos']} | {res['ang']} | {res['r_ang']} | {res['val']} | {res['p']} | {res['tier']} | {res['p21']} | {res['bar']} | {res['next']} | {res['n_1']} | {res['cgs']} | {res['adx']} | {res['atr']} | {res['vrsi']} | {res['vboy']} | {res['v100']} | {res['v21']} | {res['vmom']} |"
        grouped_lines.append(row + "\n")
        processed += 1

    with open(OUTPUT_FILE, "w") as f:
        f.writelines(grouped_lines)
    print(f"✅ Rapor Tamamlandı: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
