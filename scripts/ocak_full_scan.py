#!/usr/bin/env python3
"""
OCAK FULL SCAN - Tezaver 2.0 Architecture
Tüm Ocak ayını Ayaş Tüneli + Aysenti Geçidi mantığıyla tarar.
"""

import pandas as pd
import numpy as np
import os
import json
import re
import math
from datetime import datetime

# CONFIG
START_DATE = pd.Timestamp("2026-01-01")
END_DATE = pd.Timestamp("2026-01-28")
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
OUTPUT_REPORT = "refined_global_report_v17.md"

def get_profile_simple(day, df_w, df_h1, df_d, df_h4, strict_before=True):
    """
    DNA Profile Calculator.
    strict_before=True: Use data strictly BEFORE day (for Ayaş Tüneli)
    strict_before=False: Use data UP TO and INCLUDING day (for Aysenti)
    """
    try:
        if strict_before:
            sub_w = df_w[df_w.index < day].tail(30)
            sub_d = df_d[df_d.index < day]
            sub_h4 = df_h4[df_h4.index < day]
            sub_h1 = df_h1[df_h1.index < day]
        else:
            sub_w = df_w[df_w.index <= day].tail(30)
            sub_d = df_d[df_d.index <= day]
            sub_h4 = df_h4[df_h4.index <= day]
            sub_h1 = df_h1[df_h1.index <= day]
        
        if sub_w.empty: return "neutral"
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
        
        sub_h1_24 = sub_h1.tail(24)
        if sub_h1_24.empty or 'ema9' not in sub_h1_24: return "neutral"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        
        if sub_d.empty or sub_h4.empty or sub_h1.empty: return "neutral"
        if 'ema21' not in sub_d or 'ema21' not in sub_h4 or 'ema21' not in sub_h1: return "neutral"

        s = int(sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21']) + \
            int(sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21']) + \
            int(sub_h1.iloc[-1]['close']>sub_h1.iloc[-1]['ema21'])
        harm = f"harmony_L{s}"
        
        sub_d_tail = sub_d.tail(10)
        vol_p = sub_d.iloc[-1]['volume'] / (sub_d_tail['volume'].mean()+1)
        ritim = "ignited" if vol_p > 2.0 else "active" if vol_p > 1.0 else "sleeping"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
        retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
        ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except: return "neutral"

def strip_tags(s):
    return re.sub(r'<[^>]+>', '', str(s))

def format_cell(val, width):
    s = str(val)
    content_len = len(strip_tags(s))
    padding = max(0, width - content_len)
    return " " + s + " " * padding + " "

def write_aligned_table(f, rows, headers):
    if not rows: return
    col_widths = [len(h) for h in headers]
    for r in rows:
        for i, val in enumerate(r):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(strip_tags(str(val))))
    
    header_line = "|"
    sep_line = "|"
    for i, h in enumerate(headers):
        header_line += format_cell(h, col_widths[i]) + "|"
        sep_line += "-" * (col_widths[i] + 2) + "|"
    
    f.write(header_line + "\n")
    f.write(sep_line + "\n")
    
    for r in rows:
        row_line = "|"
        for i, val in enumerate(r):
            if i < len(col_widths):
                row_line += format_cell(val, col_widths[i]) + "|"
        f.write(row_line + "\n")

def run_full_scan():
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    # Pre-load all data once
    print("📦 VERİ YÜKLENİYOR...")
    all_data = {}
    for symbol in symbols:
        try:
            key_path = f"/Users/alisaglam/TezaverMac/data/golden_keys/{symbol}_key.json"
            if not os.path.exists(key_path): continue
            
            with open(key_path, "r") as f:
                golden_dna_list = set(json.load(f).get('golden_dna_list', []))
            
            def load_clean(path):
                if not os.path.exists(path): return pd.DataFrame()
                df = pd.read_parquet(path)
                df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('dt', inplace=True)
                df = df[~df.index.duplicated(keep='last')]
                return df.sort_index()

            df_1d = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
            if df_1d.empty: continue
            
            df_4h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
            df_1h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
            df_1w = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")
            df_15m = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet")

            if not df_1d.empty: df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
            if not df_4h.empty: df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
            if not df_1h.empty:
                for p in [9, 21, 50]: df_1h[f'ema{p}'] = df_1h['close'].ewm(span=p, adjust=False).mean()
            
            # 15m indicators
            if not df_15m.empty:
                df_15m['ema12'] = df_15m['close'].ewm(span=12, adjust=False).mean()
                df_15m['ema26'] = df_15m['close'].ewm(span=26, adjust=False).mean()
                df_15m['macd_hist'] = (df_15m['ema12'] - df_15m['ema26']) - (df_15m['ema12'] - df_15m['ema26']).ewm(span=9, adjust=False).mean()
                
                delta = df_15m['close'].diff()
                gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
                loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean().replace(0, 0.001)
                df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
                df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=14, adjust=False).mean()

                ribbon_periods = [20, 25, 30, 35, 40, 45, 50, 55]
                for p in ribbon_periods:
                    df_15m[f'rsi_rib_{p}'] = df_15m['rsi_ema'].ewm(span=p, adjust=False).mean()
                
                tr = np.maximum(df_15m['high'] - df_15m['low'], np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)), abs(df_15m['low'] - df_15m['close'].shift(1))))
                df_15m['atr100'] = tr.rolling(window=100).mean()
                df_15m['atr21'] = tr.rolling(window=21).mean()
                df_15m['tr'] = tr

            all_data[symbol] = {
                'golden_dna_list': golden_dna_list,
                'df_1d': df_1d, 'df_4h': df_4h, 'df_1h': df_1h, 'df_1w': df_1w, 'df_15m': df_15m
            }
        except Exception as e:
            continue
    
    print(f"✅ {len(all_data)} Coin Yüklendi.")

    # Iterate each day
    all_results = []
    current_date = START_DATE
    
    while current_date <= END_DATE:
        print(f"📅 {current_date.strftime('%Y-%m-%d')} taranıyor...")
        
        ayas_candidates = []
        aysenti_candidates = []
        
        for symbol, data in all_data.items():
            golden_dna_list = data['golden_dna_list']
            df_1d, df_4h, df_1h, df_1w, df_15m = data['df_1d'], data['df_4h'], data['df_1h'], data['df_1w'], data['df_15m']
            
            # Date range check
            if df_1d.empty or current_date > df_1d.index[-1] + pd.Timedelta(days=2):
                continue
            
            # AYAŞ TÜNELİ (00:00 - strict before)
            dna_ayas = get_profile_simple(current_date, df_1w, df_1h, df_1d, df_4h, strict_before=True)
            is_ayas = dna_ayas in golden_dna_list
            
            # AYSENTİ GEÇİDİ (Gün sonu - including day)
            dna_aysenti = get_profile_simple(current_date, df_1w, df_1h, df_1d, df_4h, strict_before=False)
            is_aysenti = (not is_ayas) and (dna_aysenti in golden_dna_list)
            
            source = None
            dna = None
            entry_time = "00:00"  # Default for Ayaş
            
            if is_ayas:
                source = "AYAS"
                dna = dna_ayas
                ayas_candidates.append(symbol)
            elif is_aysenti:
                source = "AYSENTI"
                dna = dna_aysenti
                aysenti_candidates.append(symbol)
                # Find exact entry time for Aysenti coins
                day_start = current_date.normalize()
                for hour in range(1, 24):
                    check_time = day_start + pd.Timedelta(hours=hour)
                    dna_check = get_profile_simple(check_time, df_1w, df_1h, df_1d, df_4h, strict_before=False)
                    if dna_check in golden_dna_list:
                        entry_time = f"{hour:02d}:00"
                        break
            
            if source:
                # Generate signals for this coin on this day
                current_utc = current_date.normalize()
                day_mask = (df_15m.index.normalize() == current_utc)
                target_day_data = df_15m[day_mask]
                
                if target_day_data.empty: continue
                
                open_p, max_h, close_p = target_day_data.iloc[0]['open'], target_day_data['high'].max(), target_day_data.iloc[-1]['close']
                
                rsi_vals = df_15m['rsi'].values
                all_trigger_indices = np.where((rsi_vals[:-1] <= 70) & (rsi_vals[1:] > 70))[0] + 1
                
                trigger_events = []
                day_indices = np.where(day_mask)[0]
                
                for i in day_indices:
                    is_trigger = i in all_trigger_indices
                    if is_trigger:
                        trig_time = df_15m.index[i]
                        last_4h = df_4h[df_4h.index <= trig_time]
                        t4 = "🟢" if not last_4h.empty and 'ema21' in last_4h and last_4h.iloc[-1]['close'] > last_4h.iloc[-1]['ema21'] else "🔴"
                        last_1h = df_1h[df_1h.index <= trig_time]
                        t1 = "🟢" if not last_1h.empty and 'ema21' in last_1h and last_1h.iloc[-1]['close'] > last_1h.iloc[-1]['ema21'] else "🔴"
                        m_tr = f"{t4}{t1}"

                        next_triggers = all_trigger_indices[all_trigger_indices > i]
                        next_t_idx = next_triggers[0] if len(next_triggers) > 0 else len(df_15m)
                        search_limit = min(i + 22, next_t_idx)
                        
                        h_t = df_15m['macd_hist'].values[i]
                        h_p = df_15m['macd_hist'].values[i-1] if i > 0 else 0
                        mac_c = "🟢" if h_t > 0 and h_t > h_p else "🟣" if h_t > 0 else "🔴" if h_t < h_p else "🟡"
                        
                        v_t = df_15m['volume'].values[i]
                        v_p = df_15m['volume'].values[i-1] if i > 0 else 0.001
                        v_a21 = np.mean(df_15m['volume'].values[max(0,i-21):i]) or 0.001
                        v_idx = min(10.0, (df_15m['tr'].values[i] / (df_15m['atr100'].values[i] or 0.001)) * 3.33)
                        v_dyn = min(10.0, (df_15m['tr'].values[i] / (df_15m['atr21'].values[i] or 0.001)) * 3.33)
                        
                        past_vidx = []
                        for k in range(1, 4):
                            if i-k >= 0:
                                p_tr = df_15m['tr'].values[i-k]
                                p_atr = df_15m['atr100'].values[i-k] or 0.001
                                past_vidx.append((p_tr/p_atr)*3.33)
                        avg_past_vidx = np.mean(past_vidx) if past_vidx else 0.001
                        v_mom = (v_idx / avg_past_vidx) if avg_past_vidx > 0 else 0
                        
                        body_size = abs(df_15m['close'].values[i] - df_15m['open'].values[i])
                        candle_range = df_15m['tr'].values[i] or 0.001
                        v_eff = (body_size / candle_range) * 10.0
                        rsi_power = df_15m['rsi'].values[i] / 50.0
                        v_hyb = min(15.0, v_idx * rsi_power)
                        
                        if i + 1 < len(df_15m):
                            val_slice = df_15m['high'].values[i + 1 : search_limit + 1]
                            if len(val_slice) > 0:
                                peak_idx_rel = np.argmax(val_slice)
                                peak_p = val_slice[peak_idx_rel]
                                peak_dist = peak_idx_rel + 1
                            else:
                                peak_p = df_15m['close'].values[i]; peak_dist = 0
                        else:
                            peak_p = df_15m['close'].values[i]; peak_dist = 0
                        
                        strat_signal = "🚀" if v_idx >= 7.0 and (v_t/(v_p or 0.001) > 11 or v_t/v_a21 > 11) else ""
                        is_stuck = df_15m['close'].values[i] < df_15m['open'].values[i]
                        is_limited = (next_t_idx - i <= 21)

                        next_idx = i + peak_dist + 1
                        if next_idx < len(df_15m):
                            n_c = df_15m['close'].values[next_idx]
                            next_pct = ((n_c - peak_p) / peak_p) * 100
                        else:
                            next_pct = None
                        
                        candle_open = df_15m['open'].values[i]
                        trig_pct = ((df_15m['close'].values[i] - candle_open) / candle_open) * 100

                        val_20 = df_15m['rsi_rib_20'].values[i] if 'rsi_rib_20' in df_15m else 50
                        val_55 = df_15m['rsi_rib_55'].values[i] if 'rsi_rib_55' in df_15m else 50
                        val_20_prev = df_15m['rsi_rib_20'].values[i-1] if i>=1 and 'rsi_rib_20' in df_15m else val_20
                        val_55_prev = df_15m['rsi_rib_55'].values[i-1] if i>=1 and 'rsi_rib_55' in df_15m else val_55
                        
                        if val_20 > val_55:
                            curr_v = val_20; prev_v = val_20_prev; src_icon = "🟢"
                        else:
                            curr_v = val_55; prev_v = val_55_prev; src_icon = "🔴"

                        slope = (curr_v - prev_v) / 2.0 if i>=1 else 0.0
                        angle_deg = math.degrees(math.atan(slope))
                        ang_score = angle_deg / 4.5
                        val_str = f"{ang_score:+.1f}"
                        num_color = "green" if ang_score >= 0 else "red"
                        src_heart = "❤️" if src_icon == "🔴" else "💚"
                        
                        if abs(ang_score) > 5.0: ang_e = f"<font color='{num_color}'>**{val_str}**</font>"
                        else: ang_e = f"<font color='{num_color}'>{val_str}</font>"

                        if curr_v < 30: pos_icon = "⚫"
                        elif curr_v < 50: pos_icon = "🔴"
                        elif curr_v < 60: pos_icon = "🟡"
                        elif curr_v < 70: pos_icon = "🟢"
                        else: pos_icon = "🟠"
                        
                        ribbon_periods = [20, 25, 30, 35, 40, 45, 50, 55]
                        rsi_ribbon_cols = [f'rsi_rib_{p}' for p in ribbon_periods]
                        rsi_rib_check = all(col in df_15m and df_15m['rsi_ema'].values[i] > df_15m[col].values[i] for col in rsi_ribbon_cols)

                        trigger_events.append({
                            'time': df_15m.index[i].strftime("%H:%M"), 'mac_color': mac_c, 'v_index': v_idx,
                            'strat': strat_signal,
                            'rsi_rib': "Yes" if rsi_rib_check else "",
                            'v_ch': ((v_t/(v_p or 0.001))-1)*100, 'v_avg': ((v_t/v_a21)-1)*100,
                            'peak': ((peak_p/df_15m['close'].values[i])-1)*100,
                            'peak_dist': peak_dist, 'is_stuck': is_stuck, 'is_limited': is_limited,
                            'v_dyn': v_dyn, 'v_mom': v_mom, 'v_eff': v_eff, 'v_hyb': v_hyb,
                            'm_tr': m_tr, 'next_pct': next_pct, 'trig_pct': trig_pct,
                            'ang_emoji': ang_e, 'val_icon': src_heart, 'pos_icon': pos_icon
                        })

                all_results.append({
                    'date': current_date, 'symbol': symbol, 'dna': dna, 'source': source,
                    'entry_time': entry_time,
                    'peak': ((max_h/open_p)-1)*100, 'ret': ((close_p/open_p)-1)*100,
                    'triggers': trigger_events,
                    'is_stuck_day': (close_p < open_p),
                    'prio': min([{"🟢":1,"🟣":2,"🟡":3,"🔴":4}.get(t['mac_color'],5) for t in trigger_events]) if trigger_events else 5
                })
        
        print(f"   Ayaş: {len(ayas_candidates)}, Aysenti: {len(aysenti_candidates)}")
        current_date += pd.Timedelta(days=1)

    # Generate Report
    print("📝 RAPOR YAZILIYOR...")
    df = pd.DataFrame(all_results)
    if df.empty:
        print("Boş Rapor.")
        return
    
    df.sort_values(by=['date', 'source', 'prio', 'peak'], ascending=[True, True, True, False], inplace=True)

    months = {1:"Ocak", 2:"Şubat", 3:"Mart"}
    
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("# TEZAVER GLOBAL AUDIT REPORT (v17 - Ayaş + Aysenti)\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        curr_d = None
        curr_source = None
        day_rows = []
        idx = 1
        
        for _, r in df.iterrows():
            d_str = f"{r['date'].day:02d} {months[r['date'].month]} {r['date'].year}"
            
            # New Day
            if d_str != curr_d:
                # Flush previous
                if curr_d is not None and day_rows:
                    hdrs = ["NO", "SYM", "ENTRY", "MAX", "CLOSE", "TIME", "SIG", "TREND", "POS", "ANG", "VAL", "P", "P-21", "BAR", "NEXT", "R-Rib", "Vrsi", "V100", "V21", "V-Mom", "VBoy", "V-Ch", "V-Avg"]
                    write_aligned_table(f, day_rows, hdrs)
                    f.write("\n")
                    day_rows = []
                
                day_df = df[df['date'] == r['date']]
                ayas_count = len(day_df[day_df['source'] == 'AYAS'])
                aysenti_count = len(day_df[day_df['source'] == 'AYSENTI'])
                
                f.write(f"## 📅 {d_str} (Ayaş: {ayas_count}, Aysenti: {aysenti_count})\n\n")
                curr_d = d_str
                curr_source = None
                idx = 1
                day_rows = []
            
            # New Source Section
            if r['source'] != curr_source:
                if day_rows:
                    hdrs = ["NO", "SYM", "ENTRY", "MAX", "CLOSE", "TIME", "SIG", "TREND", "POS", "ANG", "VAL", "P", "P-21", "BAR", "NEXT", "R-Rib", "Vrsi", "V100", "V21", "V-Mom", "VBoy", "V-Ch", "V-Avg"]
                    write_aligned_table(f, day_rows, hdrs)
                    f.write("\n")
                    day_rows = []
                    idx = 1
                
                if r['source'] == 'AYAS':
                    f.write("### 🚇 AYAŞ TÜNELİ (00:00 Gatekeeper)\n\n")
                else:
                    f.write("### 🌉 AYSENTİ GEÇİDİ (Gün İçi Katılanlar)\n\n")
                curr_source = r['source']
            
            # Skip if no triggers or all stuck
            if not r['triggers']: continue
            if all(t['is_stuck'] for t in r['triggers']): continue
            
            p_s = f"<font color='green'>+{r['peak']:.1f}%</font>" if r['peak']>10 else f"+{r['peak']:.1f}%"
            c_s = f"<font color='red'>{r['ret']:.1f}%</font>" if r['ret']<0 else f"+{r['ret']:.1f}%"
            
            for i, t in enumerate(r['triggers']):
                v_ch_val = t['v_ch']
                if v_ch_val > 1000: v_c = f"<font color='green'>+{v_ch_val:.1f}%</font>"
                elif v_ch_val > 500: v_c = f"<font color='orange'>+{v_ch_val:.1f}%</font>"
                else: v_c = f"+{v_ch_val:.1f}%"

                v_avg_val = t['v_avg']
                if v_avg_val > 1000: v_a = f"<font color='green'>+{v_avg_val:.1f}%</font>"
                elif v_avg_val > 500: v_a = f"<font color='orange'>+{v_avg_val:.1f}%</font>"
                else: v_a = f"+{v_avg_val:.1f}%"
                
                v_index = t['v_index']
                v_idx_s = f"{v_index:.1f}"
                if v_index >= 10.0: v_i = f"<font color='#00FF00'>**{v_idx_s}**</font>"
                elif v_index >= 8.0: v_i = f"<font color='green'>{v_idx_s}</font>"
                elif v_index >= 4.0: v_i = v_idx_s
                elif v_index >= 2.0: v_i = f"<font color='gray'>{v_idx_s}</font>"
                else: v_i = f"<font color='#888888'>{v_idx_s}</font>"

                pk_val = t['peak']
                if pk_val < 0: pk = f"<font color='red'>{pk_val:.1f}%</font>"
                elif pk_val > 0: pk = f"<font color='green'>+{pk_val:.1f}%</font>"
                else: pk = f"0.0%"
                
                bar_val = str(t['peak_dist'])
                if t['peak_dist'] == 0: bar_val = f"<font color='red'>**0**</font>"
                elif t['is_limited']: bar_val = f"<font color='blue'>{bar_val}</font>"
                
                s1_val = t['strat']
                s2_val = "⛔" if t['is_stuck'] else ""
                sig_val = f"{s1_val}{s2_val}"
                
                vd_s = f"{t['v_dyn']:.1f}"
                if t['v_dyn'] >= 8.0: vd_f = f"<font color='green'>**{vd_s}**</font>"
                else: vd_f = vd_s
                
                vm_s = f"{t['v_mom']:.1f}x"
                if t['v_mom'] > 1.5: vm_f = f"<font color='green'>**{vm_s}**</font>"
                else: vm_f = vm_s
                
                ve_s = f"{t['v_eff']:.1f}"
                if t['v_eff'] >= 7.0: ve_f = f"<font color='green'>**{ve_s}**</font>"
                elif t['v_eff'] < 3.0: ve_f = f"<font color='red'>{ve_s}</font>"
                else: ve_f = ve_s
                
                vh_s = f"{t['v_hyb']:.1f}"
                if t['v_hyb'] >= 10.0: vh_f = f"<font color='#00FF00'>**{vh_s}**</font>"
                elif t['v_hyb'] >= 7.0: vh_f = f"<font color='green'>{vh_s}</font>"
                else: vh_f = vh_s

                next_val = "-"
                if t['next_pct'] is not None:
                    nv = t['next_pct']
                    if nv > 0: val_str_n = f"+{nv:.1f}%"
                    elif nv < 0: val_str_n = f"{nv:.1f}%"
                    else: val_str_n = "0.0%"
                    if abs(nv) > 10.0: val_str_n = f"**{val_str_n}**"
                    if nv > 0: next_val = f"<font color='green'>{val_str_n}</font>"
                    elif nv < 0: next_val = f"<font color='red'>{val_str_n}</font>"
                    else: next_val = val_str_n
                
                r_rib = "🟢" if t['rsi_rib'] == "Yes" else "🔴"
                
                tp = t['trig_pct']
                tp_str = f"+{tp:.1f}%" if tp > 0 else f"{tp:.1f}%"
                if abs(tp) > 20.0: trig_val = f"<font color='red'>**{tp_str}**</font>"
                elif abs(tp) > 10.0: trig_val = f"<font color='red'>{tp_str}</font>"
                else: trig_val = tp_str

                if i==0:
                    # Format entry time (orange for Aysenti, default for Ayaş)
                    ent_str = f"<font color='orange'>{r['entry_time']}</font>" if r['source'] == 'AYSENTI' else r['entry_time']
                    row = [str(idx), r['symbol'], ent_str, p_s, c_s, t['time'], sig_val, t['m_tr'], t['pos_icon'], t['ang_emoji'], t['val_icon'], trig_val, pk, bar_val, next_val, r_rib, vh_f, v_i, vd_f, vm_f, ve_f, v_c, v_a]
                else:
                    row = ["", "", "", "", "", t['time'], sig_val, t['m_tr'], t['pos_icon'], t['ang_emoji'], t['val_icon'], trig_val, pk, bar_val, next_val, r_rib, vh_f, v_i, vd_f, vm_f, ve_f, v_c, v_a]
                day_rows.append(row)
            
            idx += 1
        
        # Flush last day
        if day_rows:
            hdrs = ["NO", "SYM", "ENTRY", "MAX", "CLOSE", "TIME", "SIG", "TREND", "POS", "ANG", "VAL", "P", "P-21", "BAR", "NEXT", "R-Rib", "Vrsi", "V100", "V21", "V-Mom", "VBoy", "V-Ch", "V-Avg"]
            write_aligned_table(f, day_rows, hdrs)
    
    print(f"✅ RAPOR TAMAMLANDI: {OUTPUT_REPORT}")

if __name__ == "__main__":
    run_full_scan()
