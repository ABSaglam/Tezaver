
import pandas as pd
import numpy as np
import os
import json
import re
import math
from datetime import datetime

# CONFIG
TARGET_DATE = pd.Timestamp("2026-01-28")
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

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

def get_profile_simple(day, df_w, df_h1, df_d, df_h4):
    try:
        sub_w = df_w[df_w.index <= day].tail(30)
        if sub_w.empty: return "neutral"
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
        
        sub_h1_24 = df_h1[df_h1.index <= day].tail(24)
        if sub_h1_24.empty or 'ema9' not in sub_h1_24: return "neutral"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        
        sub_d = df_d[df_d.index <= day]
        sub_h4 = df_h4[df_h4.index <= day]
        sub_h1_sub = df_h1[df_h1.index <= day]
        if sub_d.empty or sub_h4.empty or sub_h1_sub.empty: return "neutral"
        
        # Guard against missing EMA columns (if DFs were empty and calc skipped)
        if 'ema21' not in sub_d or 'ema21' not in sub_h4 or 'ema21' not in sub_h1_sub: return "neutral"

        s = int(sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21']) + int(sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21']) + int(sub_h1_sub.iloc[-1]['close']>sub_h1_sub.iloc[-1]['ema21'])
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
    except Exception as e:
        if day == pd.Timestamp("2026-01-28"):
            print(f"DEBUG: get_profile_simple error: {e}")
            # print(f"DEBUG: 4h cols: {df_h4.columns}") 
            # print(f"DEBUG: 1h cols: {df_h1.columns}")
            # print(f"DEBUG: 1d cols: {df_d.columns}")
        return "neutral"

def regenerate_jan28():
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    all_passed_days = []

    print(f"Scanning {len(symbols)} coins for {TARGET_DATE}...")

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
            
            # Optimization: Check date range first
            if TARGET_DATE > df_1d.index[-1] + pd.Timedelta(days=2):
                continue

            df_4h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
            df_1h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
            df_1w = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")
            df_15m = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet")

            if df_15m.empty: continue

            if not df_4h.empty:
                df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
            
            if not df_1h.empty:
                for p in [9, 21, 50]: df_1h[f'ema{p}'] = df_1h['close'].ewm(span=p, adjust=False).mean()
            
            # --- INDICATOR CALCULATION ON FULL HISTORY (No Slice Yet) ---
            df_15m['ema12'] = df_15m['close'].ewm(span=12, adjust=False).mean()
            df_15m['ema26'] = df_15m['close'].ewm(span=26, adjust=False).mean()
            df_15m['macd_hist'] = (df_15m['ema12'] - df_15m['ema26']) - (df_15m['ema12'] - df_15m['ema26']).ewm(span=9, adjust=False).mean()
            
            # RSI Calculation
            delta = df_15m['close'].diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean().replace(0, 0.001)
            df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
            df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=14, adjust=False).mean()

            # Ribbon Calculation
            ribbon_periods = [20, 25, 30, 35, 40, 45, 50, 55]
            rsi_ribbon_cols = []
            for p in ribbon_periods:
                df_15m[f'rsi_rib_{p}'] = df_15m['rsi_ema'].ewm(span=p, adjust=False).mean()
                rsi_ribbon_cols.append(f'rsi_rib_{p}')
            
            tr = np.maximum(df_15m['high'] - df_15m['low'], np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)), abs(df_15m['low'] - df_15m['close'].shift(1))))
            df_15m['atr100'] = tr.rolling(window=100).mean()
            df_15m['atr21'] = tr.rolling(window=21).mean()
            df_15m['tr'] = tr

            # Single Date Logic
            dna = get_profile_simple(TARGET_DATE, df_1w, df_1h, df_1d, df_4h)
            if dna not in golden_dna_list: continue

            # --- NOW SLICE FOR TARGET DAY ---
            # Indicators are now "warmed up" from previous history effortlessly.
            current_utc = TARGET_DATE.normalize()
            day_mask = (df_15m.index.normalize() == current_utc)

            target_day_data = df_15m[day_mask]
            
            # Handle potential empty 15m data for that specific day if coin was inactive
            if target_day_data.empty: continue

            open_p, max_h, close_p = target_day_data.iloc[0]['open'], target_day_data['high'].max(), target_day_data.iloc[-1]['close']
            
            rsi_vals = df_15m['rsi'].values
            all_trigger_indices = np.where((rsi_vals[:-1] <= 70) & (rsi_vals[1:] > 70))[0] + 1
            
            trigger_events = []
            day_indices = np.where(day_mask)[0]
            
            for i in day_indices:
                # No skip needed anymore, data is warmed up from history
                is_trigger = i in all_trigger_indices
                
                if is_trigger:
                    trig_time = df_15m.index[i]
                    last_4h = df_4h[df_4h.index <= trig_time]
                    t4 = "🟢" if not last_4h.empty and last_4h.iloc[-1]['close'] > last_4h.iloc[-1]['ema21'] else "🔴"
                    last_1h = df_1h[df_1h.index <= trig_time]
                    t1 = "🟢" if not last_1h.empty and last_1h.iloc[-1]['close'] > last_1h.iloc[-1]['ema21'] else "🔴"
                    m_tr = f"{t4}{t1}"

                    next_triggers = all_trigger_indices[all_trigger_indices > i]
                    next_t_idx = next_triggers[0] if len(next_triggers) > 0 else len(df_15m)
                    search_limit = min(i + 22, next_t_idx) 
                    
                    h_t, h_p = df_15m['macd_hist'].values[i], df_15m['macd_hist'].values[i-1]
                    mac_c = "🟢" if h_t > 0 and h_t > h_p else "🟣" if h_t > 0 else "🔴" if h_t < h_p else "🟡"
                    
                    v_t, v_p = df_15m['volume'].values[i], df_15m['volume'].values[i-1] or 0.001
                    v_a21 = np.mean(df_15m['volume'].values[i-21:i]) or 0.001
                    v_a5 = np.mean(df_15m['volume'].values[i-5:i]) or 0.001
                    v_trend = (v_a5 / v_a21)
                    price_range = df_15m['tr'].values[i]
                    v_spread = (price_range / (v_t or 0.001)) * 1000000 
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
                    
                    is_new = (dna == "neutral")
                    strat_signal = "🚀" if v_idx >= 7.0 and (v_t/v_p > 11 or v_t/v_a21 > 11) else ""
                    if is_new: strat_signal += "🆕"

                    is_stuck = df_15m['close'].values[i] < open_p
                    is_limited = (next_t_idx - i <= 21) 

                    next_idx = i + peak_dist + 1
                    if next_idx < len(df_15m):
                        n_c = df_15m['close'].values[next_idx]
                        next_pct = ((n_c - peak_p) / peak_p) * 100
                    else:
                        next_pct = None
                    
                    candle_open = df_15m['open'].values[i]
                    trig_pct = ((df_15m['close'].values[i] - candle_open) / candle_open) * 100

                    val_20 = df_15m['rsi_rib_20'].values[i]
                    val_55 = df_15m['rsi_rib_55'].values[i]
                    val_20_prev = df_15m['rsi_rib_20'].values[i-1] if i>=1 else val_20
                    val_55_prev = df_15m['rsi_rib_55'].values[i-1] if i>=1 else val_55
                    
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

                    trigger_events.append({
                        'time': df_15m.index[i].strftime("%H:%M"), 'mac_color': mac_c, 'v_index': v_idx,
                        'strat': strat_signal,
                        'rsi_rib': "Yes" if all(df_15m['rsi_ema'].values[i] > df_15m[c].values[i] for c in rsi_ribbon_cols) else "",
                        'v_ch': ((v_t/v_p)-1)*100, 'v_avg': ((v_t/v_a21)-1)*100, 'v_trend': v_trend, 'v_spread': v_spread,
                        'peak': ((peak_p/df_15m['close'].values[i])-1)*100,
                        'peak_dist': peak_dist, 'is_stuck': is_stuck, 'is_limited': is_limited,
                        'v_dyn': v_dyn, 'v_mom': v_mom, 'v_eff': v_eff, 'v_hyb': v_hyb,
                        'm_tr': m_tr, 'next_pct': next_pct, 'trig_pct': trig_pct,
                        'ang_emoji': ang_e, 'val_icon': src_heart, 'pos_icon': pos_icon
                    })

            all_passed_days.append({
                'date': TARGET_DATE, 'symbol': symbol, 'dna': dna, 'peak': ((max_h/open_p)-1)*100, 'ret': ((close_p/open_p)-1)*100,
                'triggers': trigger_events,
                'is_stuck_day': (close_p < open_p),
                'prio': min([{"🟢":1,"🟣":2,"🟡":3,"🔴":4}.get(t['mac_color'],5) for t in trigger_events]) if trigger_events else 5
            })
            
        except Exception as e:
            if symbol == 'KERNELUSDT': print(f"CRITICAL ERROR {symbol}: {e}")
            pass

    # --- FORMATTING ---
    df = pd.DataFrame(all_passed_days)
    if df.empty:
        print("No valid coins found for Jan 28.")
        return
        
    df['frek'] = df.groupby(['date', 'dna'])['symbol'].transform('count')
    df.sort_values(by=['date', 'prio', 'peak'], ascending=[True, True, False], inplace=True)

    with open("jan28_snippet.md", "w", encoding="utf-8") as f:
        months = {1:"Ocak", 2:"Şubat", 3:"Mart"}
        day_rows = []
        d_str = f"{TARGET_DATE.day:02d} {months[TARGET_DATE.month]} {TARGET_DATE.year}"
        
        f.write(f"## 📅 {d_str} (Geçen: {len(df)} Kalan: {len(df[df['prio']<5])})\n")
        
        idx = 1
        for _, r in df.iterrows():
            p_s = f"<font color='green'>+{r['peak']:.1f}%</font>" if r['peak']>10 else f"+{r['peak']:.1f}%"
            c_s = f"<font color='red'>{r['ret']:.1f}%</font>" if r['ret']<0 else f"+{r['ret']:.1f}%"
            
            if not r['triggers']: continue
            if all(t['is_stuck'] for t in r['triggers']): continue

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

                vt_v = t['v_trend']
                if vt_v > 2.0: vt_s = f"<font color='green'>**{vt_v:.1f}x**</font>"
                elif vt_v > 1.2: vt_s = f"<font color='green'>{vt_v:.1f}x</font>"
                elif vt_v < 0.8: vt_s = f"<font color='red'>{vt_v:.1f}x</font>"
                else: vt_s = f"{vt_v:.1f}x"

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
                    if nv > 0: val_str = f"+{nv:.1f}%"
                    elif nv < 0: val_str = f"{nv:.1f}%"
                    else: val_str = "0.0%"
                    if abs(nv) > 10.0: val_str = f"**{val_str}**"
                    if nv > 0: next_val = f"<font color='green'>{val_str}</font>"
                    elif nv < 0: next_val = f"<font color='red'>{val_str}</font>"
                    else: next_val = val_str
                
                r_rib = "🟢" if t['rsi_rib'] == "Yes" else "🔴"
                
                tp = t['trig_pct']
                tp_str = f"+{tp:.1f}%" if tp > 0 else f"{tp:.1f}%"
                if abs(tp) > 20.0: trig_val = f"<font color='red'>**{tp_str}**</font>"
                elif abs(tp) > 10.0: trig_val = f"<font color='red'>{tp_str}</font>"
                else: trig_val = tp_str

                if i==0:
                    row = [str(idx), r['symbol'], p_s, c_s, t['time'], sig_val, t['m_tr'], t['pos_icon'], t['ang_emoji'], t['val_icon'], trig_val, pk, bar_val, next_val, r_rib, vh_f, v_i, vd_f, vm_f, ve_f, v_c, v_a]
                else:
                    row = ["", "", "", "", t['time'], sig_val, t['m_tr'], t['pos_icon'], t['ang_emoji'], t['val_icon'], trig_val, pk, bar_val, next_val, r_rib, vh_f, v_i, vd_f, vm_f, ve_f, v_c, v_a]
                day_rows.append(row)
            
            idx += 1
            
        hdrs = ["NO", "SYM", "MAX", "CLOSE", "TIME", "SIG", "TREND", "POS", "ANG", "VAL", "P", "P-21", "BAR", "NEXT", "R-Rib", "Vrsi", "V100", "V21", "V-Mom", "VBoy", "V-Ch", "V-Avg"]
        write_aligned_table(f, day_rows, hdrs)

if __name__ == "__main__":
    regenerate_jan28()
