#!/usr/bin/env python3
"""
TEZAVER YENİ SİSTEM RSI-EMA TETİKLEYİCİSİ (V17 RAPOR FORMATI)
Tetik: RSI-EMA'nın Ribbon'daki EN ÜST (MAX) çizgiyi yukarı kestiği an.
Timeframe: 15m
"""

import pandas as pd
import numpy as np
import os
import json
import re
import math
import sys
from datetime import datetime

# Portakal Sıkacağı Entegrasyonu
sys.path.insert(0, '/Users/alisaglam/TezaverMac/scripts')
try:
    from portakal_sikacagi import apply_portakal_sikacagi
    # PORTAKAL_AVAILABLE = True
    PORTAKAL_AVAILABLE = False # User explicitly requested to DISABLE this.
except ImportError:
    PORTAKAL_AVAILABLE = False
    print("⚠️ Portakal Sıkacağı modülü bulunamadı!")

# ==========================================
# 🛠️ KULLANICI AYARLARI
# ==========================================

TARGET_START_DATE = "2026-01-15"
TARGET_END_DATE   = "2026-01-31"

FILTERS = {
    'min_tier': None, 
    'min_cgs': None,
    'min_atr': None,
    'min_adx': None,
    'min_vrsi': None,
    'only_rockets': False,
    'positive_close_only': False
}

DISABLE_AYAS_CHECK = True
OUTPUT_FILE = "yeni_sistem_rsi_ema_v17.md"
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

# ==========================================
# HELPER FUNCTIONS
# ==========================================

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

def get_profile_simple(day, df_w, df_h1, df_d, df_h4, strict_before=True):
    try:
        integrity_cutoff_w = day - pd.Timedelta(days=7)
        sub_w = df_w[df_w.index <= integrity_cutoff_w].tail(30)
        if len(sub_w) < 15: return "neutral"
        
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        
        if np.isnan(rsi_val): return "neutral"
        
        faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
        
        daily_integrity_cutoff = day.normalize()
        
        if strict_before:
            sub_h1_24 = df_h1[df_h1.index < day].tail(24)
            sub_d = df_d[df_d.index < daily_integrity_cutoff]
            sub_h4 = df_h4[df_h4.index < day]
            sub_h1 = df_h1[df_h1.index < day]
        else:
            sub_h1_24 = df_h1[df_h1.index <= day].tail(24)
            sub_d = df_d[df_d.index < daily_integrity_cutoff]
            sub_h4 = df_h4[df_h4.index <= day]
            sub_h1 = df_h1[df_h1.index <= day]
            
        if sub_h1_24.empty or 'ema9' not in sub_h1_24: return "neutral"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        
        if sub_d.empty or sub_h4.empty or sub_h1.empty: return "neutral"
        if sub_d.iloc[-1].isnull().any(): return "neutral"

        s = int(sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21']) + \
            int(sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21']) + \
            int(sub_h1.iloc[-1]['close']>sub_h1.iloc[-1]['ema21'])
        harm = f"harmony_L{s}"
        
        return f"{faz}|{acc}|{harm}"
    except: return "neutral"

def format_row_data(r, t, i, idx):
    p_s = f"<font color='green'>+{r['peak']:.1f}%</font>" if r['peak']>10 else f"+{r['peak']:.1f}%"
    c_s = f"<font color='red'>{r['ret']:.1f}%</font>" if r['ret']<0 else f"+{r['ret']:.1f}%"
    
    # V17 Sütunları
    # NO | SYM | MAX | CLOSE | TIME | SIG | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-21 | BAR | NEXT | N-1 | CGS | ATR% | Vrsi | VBoy | V100 | V21 | V-Mom

    sig_val = f"{t['strat']}{'⛔' if t['is_stuck'] else ''}"
    
    pos_icon = t['pos_icon']
    ang_emoji = t['ang_emoji']
    
    r_ang = t.get('rsi_angle', 0.0)
    ra_str = f"{r_ang:.0f}°"
    if r_ang >= 45: ra_f = f"<font color='#00FF00'>**+{ra_str}**</font>"
    elif r_ang >= 10: ra_f = f"<font color='green'>+{ra_str}</font>"
    elif r_ang <= -45: ra_f = f"<font color='red'>**{ra_str}**</font>"
    elif r_ang <= -10: ra_f = f"<font color='red'>{ra_str}</font>"
    else: ra_f = f"<font color='gray'>{ra_str}</font>"
    
    val_icon = t['val_icon']
    trig_val = f"+{t['trig_pct']:.1f}%" if t['trig_pct'] > 0 else f"{t['trig_pct']:.1f}%"
    
    pk_val = t['peak']
    if pk_val < 0: pk = f"<font color='red'>{pk_val:.1f}%</font>"
    elif pk_val > 0: pk = f"<font color='green'>+{pk_val:.1f}%</font>"
    else: pk = "0.0%"

    tier_icon = ""
    if pk_val >= 30.0: tier_icon = "💎"
    elif pk_val >= 20.0: tier_icon = "🥇"
    elif pk_val >= 10.0: tier_icon = "🥈"
    elif pk_val >= 5.0: tier_icon = "🥉"

    bar_val = str(t['peak_dist'])
    if t['peak_dist'] == 0: bar_val = f"<font color='red'>**0**</font>"
    elif t['is_limited']: bar_val = f"<font color='blue'>{bar_val}</font>"
    
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
        
    nn_val = "-"
    if t.get('next_next_pct') is not None:
        nnv = t['next_next_pct']
        if nnv > 0: nn_str = f"+{nnv:.1f}%"
        elif nnv < 0: nn_str = f"{nnv:.1f}%"
        else: nn_str = "0.0%"
        if nnv > 0: nn_val = f"<font color='green'>{nn_str}</font>"
        elif nnv < 0: nn_val = f"<font color='red'>{nn_str}</font>"
        else: nn_val = nn_str

    cgs_val = t.get('cgs', 0.0)
    if cgs_val >= 50: cgs_f = f"<font color='green'>**{cgs_val:.0f}%**</font>"
    elif cgs_val >= 25: cgs_f = f"<font color='green'>{cgs_val:.0f}%</font>"
    elif cgs_val >= 10: cgs_f = f"{cgs_val:.0f}%"
    elif cgs_val > 0: cgs_f = f"<font color='gray'>{cgs_val:.0f}%</font>"
    else: cgs_f = f"<font color='red'>0%</font>"

    atr_pct = t.get('atr_adj', 0.0)
    d_atr = t.get('daily_atr', 0.0)
    
    # ADX Formatting
    d_adx = t.get('d_adx', 0.0)
    adx_val = f"{d_adx:.1f}"
    if d_adx >= 50: adx_f = f"<font color='#00FF00'>**{adx_val}**</font>"
    elif d_adx >= 25: adx_f = f"<font color='green'>**{adx_val}**</font>"
    elif d_adx >= 20: adx_f = f"<font color='green'>{adx_val}</font>"
    else: adx_f = f"<font color='gray'>{adx_val}</font>"

    tooltip = f"Tetik ATR: {atr_pct:.1f}% &#013;Günlük ATR: {d_atr:.1f}%"
    if atr_pct >= 4.0: atr_f = f"<font color='#00FF00'>**{atr_pct:.1f}%**</font>"
    elif atr_pct >= 2.0: atr_f = f"<font color='DarkGreen'>**{atr_pct:.1f}%**</font>"
    elif atr_pct >= 1.0: atr_f = f"<font color='green'>{atr_pct:.1f}%</font>"
    else: atr_f = f"{atr_pct:.1f}%"
    atr_f = f"<span title='{tooltip}'>{atr_f}</span>"
    
    vh_s = f"{t['v_hyb']:.1f}"
    if t['v_hyb'] >= 9.0: vh_f = f"<font color='#00FF00'>**{vh_s}**</font>"
    elif t['v_hyb'] >= 7.0: vh_f = f"<font color='green'>{vh_s}</font>"
    else: vh_f = vh_s
    
    ve_s = f"{t['v_eff']:.1f}"
    if t['v_eff'] >= 7.0: ve_f = f"<font color='green'>**{ve_s}**</font>"
    elif t['v_eff'] < 3.0: ve_f = f"<font color='red'>{ve_s}</font>"
    else: ve_f = ve_s
    
    v_index = t['v_index']
    v_idx_s = f"{v_index:.1f}"
    if v_index >= 10.0: v_i = f"<font color='#00FF00'>**{v_idx_s}**</font>"
    elif v_index >= 8.0: v_i = f"<font color='green'>{v_idx_s}</font>"
    elif v_index >= 4.0: v_i = v_idx_s
    elif v_index >= 2.0: v_i = f"<font color='gray'>{v_idx_s}</font>"
    else: v_i = f"<font color='#888888'>{v_idx_s}</font>"
    
    vd_s = f"{t['v_dyn']:.1f}"
    vd_f = f"<font color='green'>**{vd_s}**</font>" if t['v_dyn'] >= 8.0 else vd_s
    
    vm_s = f"{t['v_mom']:.1f}x"
    vm_f = f"<font color='green'>**{vm_s}**</font>" if t['v_mom'] > 1.5 else vm_s

    if i == 0:
        return [str(idx), r['symbol'], p_s, c_s, t['time'], sig_val, t['m_tr'], pos_icon, ang_emoji, ra_f, val_icon, trig_val, tier_icon, pk, bar_val, next_val, nn_val, cgs_f, adx_f, atr_f, vh_f, ve_f, v_i, vd_f, vm_f]
    else:
        return ["", "", "", "", t['time'], sig_val, t['m_tr'], pos_icon, ang_emoji, ra_f, val_icon, trig_val, tier_icon, pk, bar_val, next_val, nn_val, cgs_f, adx_f, atr_f, vh_f, ve_f, v_i, vd_f, vm_f]

def run_custom_report():
    print(f"Yeni Sistem Raporu Oluşturuluyor (RSI-EMA > Max Ribbon)...")
    print(f"Tarih Aralığı: {TARGET_START_DATE} -> {TARGET_END_DATE}")

    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    all_passed_days = []
    processed_pairs = set()

    start_d = pd.Timestamp(TARGET_START_DATE)
    end_d = pd.Timestamp(TARGET_END_DATE) + pd.Timedelta(days=1)

    for symbol in symbols:
        try:
            key_path = f"{COIN_CELLS_DIR.replace('/coin_cells','/data/golden_keys')}/{symbol}_key.json"
            if not os.path.exists(key_path):
                 key_path = f"/Users/alisaglam/TezaverMac/data/golden_keys/{symbol}_key.json"
            
            if not os.path.exists(key_path): continue
            
            with open(key_path, "r") as f:
                golden_dna_list = set(json.load(f).get('golden_dna_list', []))
            
            def load_clean(path):
                df = pd.read_parquet(path)
                df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('dt', inplace=True)
                df = df[~df.index.duplicated(keep='last')]
                return df.sort_index()

            df_1d = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
            df_4h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
            df_1h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
            df_1w = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")
            df_15m = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet")

            # Metrics Calc
            df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
            d_tr = np.maximum(df_1d['high'] - df_1d['low'], np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), abs(df_1d['low'] - df_1d['close'].shift(1))))
            df_1d['atr14'] = d_tr.rolling(window=14).mean()
            df_1d['atr_pct'] = (df_1d['atr14'] / df_1d['close']) * 100
            
            plus_dm = df_1d['high'].diff()
            minus_dm = -df_1d['low'].diff()
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
            tr14 = d_tr.rolling(window=14).sum()
            plus_di = 100 * (plus_dm.rolling(window=14).sum() / tr14)
            minus_di = 100 * (minus_dm.rolling(window=14).sum() / tr14)
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.001)
            df_1d['adx14'] = dx.rolling(window=14).mean()

            df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
            for p in [9, 21, 50]: df_1h[f'ema{p}'] = df_1h['close'].ewm(span=p, adjust=False).mean()

            # 15m Indicators (RSI-EMA + Ribbon)
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
            
            ema12 = df_15m['close'].ewm(span=12, adjust=False).mean()
            ema26 = df_15m['close'].ewm(span=26, adjust=False).mean()
            df_15m['macd_hist'] = (ema12 - ema26) - (ema12 - ema26).ewm(span=9, adjust=False).mean()
            tr = np.maximum(df_15m['high'] - df_15m['low'], np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)), abs(df_15m['low'] - df_15m['close'].shift(1))))
            df_15m['atr100'] = tr.rolling(window=100).mean()
            df_15m['atr21'] = tr.rolling(window=21).mean()
            df_15m['tr'] = tr

            # === TRIGGER LOGIC: RSI-EMA CROSSES ABOVE MAX RIBBON ===
            ribbon_max = df_15m[rsi_ribbon_cols].max(axis=1)
            rsi_ema = df_15m['rsi_ema']
            
            cond_now = rsi_ema > ribbon_max
            # Cross means: it is above now, but was NOT above (<=) previously
            triggers = (cond_now) & (~cond_now.shift(1).fillna(False))
            all_trigger_indices = np.where(triggers)[0]

            # === PRE-CALCULATE CGS HISTORY ===
            cgs_map = {}
            total_trigs = 0
            tiered_trigs = 0
            
            for k_idx, t_idx in enumerate(all_trigger_indices):
                # 1. Record CGS for THIS trigger based on PAST performance
                if total_trigs > 0:
                    cgs_map[t_idx] = (tiered_trigs / total_trigs) * 100.0
                else:
                    cgs_map[t_idx] = 0.0
                    
                # 2. Calculate outcome of THIS trigger to update stats for FUTURE
                # Find next trigger index for search limit
                if k_idx + 1 < len(all_trigger_indices):
                    next_t_idx = all_trigger_indices[k_idx+1]
                else:
                    next_t_idx = len(df_15m)
                    
                search_limit = min(t_idx + 22, next_t_idx)
                
                # Calculate Peak
                peak_p_temp = df_15m['close'].values[t_idx] # Default
                if t_idx + 1 < len(df_15m):
                    val_slice = df_15m['high'].values[t_idx + 1 : search_limit + 1]
                    if len(val_slice) > 0:
                        peak_p_temp = np.max(val_slice)
                
                close_val_temp = df_15m['close'].values[t_idx]
                if close_val_temp > 0:
                    peak_curr_temp = ((peak_p_temp / close_val_temp) - 1) * 100
                else:
                    peak_curr_temp = 0
                
                total_trigs += 1
                if peak_curr_temp >= 5.0:
                    tiered_trigs += 1

            current = start_d
            while current <= end_d:
                try:
                    pair_key = (symbol, current)
                    if pair_key in processed_pairs:
                        current += pd.Timedelta(days=1); continue

                    dna_ayas = get_profile_simple(current, df_1w, df_1h, df_1d, df_4h, strict_before=True)
                    
                    if DISABLE_AYAS_CHECK:
                        is_ayas = True 
                    else:
                        is_ayas = (dna_ayas != "neutral") and (dna_ayas in golden_dna_list)
                    
                    if not is_ayas:
                        current += pd.Timedelta(days=1); continue

                    current_utc = current.normalize()
                    day_mask = (df_15m.index.normalize() == current_utc)
                    target_day_data = df_15m[day_mask]
                    if target_day_data.empty:
                        current += pd.Timedelta(days=1); continue

                    open_p, max_h, close_p = target_day_data.iloc[0]['open'], target_day_data['high'].max(), target_day_data.iloc[-1]['close']
                    
                    if FILTERS['positive_close_only'] and close_p < open_p:
                         current += pd.Timedelta(days=1); continue
                    
                    try:
                        daily_atr_val = df_1d.loc[df_1d.index.normalize() == current.normalize(), 'atr_pct']
                        if not daily_atr_val.empty: d_atr = daily_atr_val.values[0]
                        else: d_atr = df_1d['atr_pct'].iloc[-1]
                    except: d_atr = 0.0
                    
                    try:
                        daily_adx_val = df_1d.loc[df_1d.index.normalize() == current.normalize(), 'adx14']
                        if not daily_adx_val.empty: d_adx = daily_adx_val.values[0]
                        else: d_adx = df_1d['adx14'].iloc[-1]
                        if np.isnan(d_adx): d_adx = 0.0
                    except: d_adx = 0.0
                    
                    if FILTERS.get('min_adx') and d_adx < FILTERS['min_adx']:
                        current += pd.Timedelta(days=1); continue
                    
                    trigger_events = []
                    day_indices = np.where(day_mask)[0]
                    for i in day_indices:
                        if i < 21: continue
                        
                        is_trigger = i in all_trigger_indices
                        if is_trigger:
                            trig_time = df_15m.index[i]
                            
                            cutoff_4h = trig_time - pd.Timedelta(hours=4)
                            last_4h = df_4h[df_4h.index <= cutoff_4h]
                            t4 = "🟢" if not last_4h.empty and last_4h.iloc[-1]['close'] > last_4h.iloc[-1]['ema21'] else "🔴"
                            
                            cutoff_1h = trig_time - pd.Timedelta(hours=1)
                            last_1h = df_1h[df_1h.index <= cutoff_1h]
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
                                    peak_p = df_15m['close'].values[i]
                                    peak_dist = 0
                            else:
                                peak_p = df_15m['close'].values[i]
                                peak_dist = 0
                            
                            strat_signal = "🚀" if v_idx >= 7.0 and (v_t/v_p > 11 or v_t/v_a21 > 11) else ""
                            is_stuck = df_15m['close'].values[i] < open_p
                            is_limited = (next_t_idx - i <= 21)

                            next_idx = i + peak_dist + 1
                            if next_idx < len(df_15m):
                                n_c = df_15m['close'].values[next_idx]
                                next_pct = ((n_c - peak_p) / peak_p) * 100
                                
                                nn_idx = next_idx + 1
                                if nn_idx < len(df_15m):
                                    nn_c = df_15m['close'].values[nn_idx]
                                    next_next_pct = ((nn_c - n_c) / n_c) * 100
                                else:
                                    next_next_pct = None
                            else:
                                next_pct = None
                                next_next_pct = None
                            
                            candle_open = df_15m['open'].values[i]
                            trig_pct = ((df_15m['close'].values[i] - candle_open) / candle_open) * 100

                            val_20 = df_15m['rsi_rib_20'].values[i]
                            val_55 = df_15m['rsi_rib_55'].values[i]
                            val_20_prev = df_15m['rsi_rib_20'].values[i-1] if i>=1 else val_20
                            val_55_prev = df_15m['rsi_rib_55'].values[i-1] if i>=1 else val_55
                            
                            if val_20 > val_55:
                                curr_v = val_20
                                prev_v = val_20_prev
                                src_icon = "🟢"
                            else:
                                curr_v = val_55
                                prev_v = val_55_prev
                                src_icon = "🔴"

                            if i >= 1:
                                slope = (curr_v - prev_v) / 2.0
                                angle_deg = math.degrees(math.atan(slope))
                            else:
                                angle_deg = 0.0

                            ang_score = angle_deg / 4.5
                            val_str = f"{ang_score:+.1f}"
                            num_color = "green" if ang_score >= 0 else "red"
                            src_heart = "❤️" if src_icon == "🔴" else "💚"
                            if abs(ang_score) > 5.0: ang_e = f"<font color='{num_color}'>**{val_str}**</font>"
                            else: ang_e = f"<font color='{num_color}'>{val_str}</font>"

                            if curr_v < 30: pos_icon = "⚫"; pos_color = "black"
                            elif curr_v < 50: pos_icon = "🔴"; pos_color = "red"
                            elif curr_v < 60: pos_icon = "🟡"; pos_color = "yellow"
                            elif curr_v < 70: pos_icon = "🟢"; pos_color = "green"
                            else: pos_icon = "🟠"; pos_color = "orange"
                            
                            atr21_val = df_15m['atr21'].values[i]
                            close_val = df_15m['close'].values[i]
                            atr_adj = (atr21_val / close_val) * 100 if close_val > 0 else 0

                            rsi_ema_now = df_15m['rsi_ema'].values[i]
                            rsi_ema_prev = df_15m['rsi_ema'].values[i-1] if i > 0 else rsi_ema_now
                            rsi_slope = rsi_ema_now - rsi_ema_prev
                            rsi_angle = math.degrees(math.atan(rsi_slope))

                            if FILTERS['min_atr'] and atr_adj < FILTERS['min_atr']: continue
                            if FILTERS['min_vrsi'] and v_hyb < FILTERS['min_vrsi']: continue
                            if FILTERS['only_rockets'] and not "🚀" in strat_signal: continue
                            
                            peak_curr = ((peak_p/df_15m['close'].values[i])-1)*100
                            tier_match = True
                            if FILTERS['min_tier']:
                                if FILTERS['min_tier'] == '💎' and peak_curr < 30: tier_match = False
                                elif FILTERS['min_tier'] == '🥇' and peak_curr < 20: tier_match = False
                                elif FILTERS['min_tier'] == '🥈' and peak_curr < 10: tier_match = False
                                elif FILTERS['min_tier'] == '🥉' and peak_curr < 5: tier_match = False
                            if not tier_match: continue
                            
                            t4_val = 1 if t4 == "🟢" else 0
                            t1_val = 1 if t1 == "🟢" else 0
                            trend_str = f"{t4_val}{t1_val}"
                            trend_score = t4_val + t1_val
                            
                            ribbon_above = val_20 > val_55
                            
                            trigger_events.append({
                                'time': df_15m.index[i].strftime("%H:%M"), 'mac_color': mac_c, 'v_index': v_idx,
                                'strat': strat_signal,
                                'peak': peak_curr,
                                'peak_dist': peak_dist,
                                'is_stuck': is_stuck, 'is_limited': is_limited, 'm_tr': m_tr,
                                'next_pct': next_pct, 'next_next_pct': next_next_pct, 'trig_pct': trig_pct,
                                'daily_atr': d_atr, 'ang_emoji': ang_e, 'val_icon': src_heart, 'pos_icon': pos_icon,
                                'v_dyn': v_dyn, 'v_mom': v_mom, 'v_eff': v_eff, 'v_hyb': v_hyb,
                                'atr_adj': atr_adj, 'rng_pos': 50, 'rsi_angle': rsi_angle,
                                # Portakal Sıkacağı Metrics
                                'd_atr': d_atr, 'd_adx': d_adx,
                                'trend_str': trend_str, 'trend_score': trend_score,
                                'pos': pos_color, 'ribbon_above': ribbon_above,
                                'ang_score': ang_score, 'rsi': df_15m['rsi'].values[i],
                                'cgs': cgs_map.get(i, 0.0)
                            })

                    if trigger_events:
                        all_passed_days.append({
                            'date': current, 'symbol': symbol,
                            'peak': ((max_h/open_p)-1)*100, 'ret': ((close_p/open_p)-1)*100,
                            'triggers': trigger_events,
                            'is_stuck_day': (close_p < open_p),
                            'prio': min([{"🟢":1,"🟣":2,"🟡":3,"🔴":4}.get(t['mac_color'],5) for t in trigger_events])
                        })
                        processed_pairs.add(pair_key)
                except Exception as e:
                    pass
                current += pd.Timedelta(days=1)
        except: continue

    # ==========================================
    # 🍊 PORTAKAL SIKACAĞI ENTEGRASYONU
    # ==========================================
    if PORTAKAL_AVAILABLE:
        print(f"\n🍊 Portakal Sıkacağı Filtresi Uygulanıyor...")
        
        flat_triggers = []
        for day_idx, day_data in enumerate(all_passed_days):
            for trig_idx, trig in enumerate(day_data['triggers']):
                trig_data = trig.copy()
                trig_data['__day_idx'] = day_idx
                trig_data['__trig_idx'] = trig_idx
                flat_triggers.append(trig_data)
        
        if flat_triggers:
            df_triggers = pd.DataFrame(flat_triggers)
            print(f"   Filtre Öncesi: {len(df_triggers)} tetik")
            
            df_filtered = apply_portakal_sikacagi(df_triggers, verbose=False)
            print(f"   Filtre Sonrası: {len(df_filtered)} tetik")
            
            survivors = set(zip(df_filtered['__day_idx'], df_filtered['__trig_idx']))
            
            new_passed_days = []
            for day_idx, day_data in enumerate(all_passed_days):
                new_triggers = []
                for trig_idx, trig in enumerate(day_data['triggers']):
                    if (day_idx, trig_idx) in survivors:
                        new_triggers.append(trig)
                
                if new_triggers:
                    day_data['triggers'] = new_triggers
                    day_data['prio'] = min([{"🟢":1,"🟣":2,"🟡":3,"🔴":4}.get(t['mac_color'],5) for t in new_triggers])
                    new_passed_days.append(day_data)
            
            all_passed_days = new_passed_days
        else:
            print("   Hiç tetik bulunamadı.")
    # ==========================================

    df = pd.DataFrame(all_passed_days)
    if df.empty: return print(f"Belirtilen kriterlere uygun veri bulunamadı.")
    
    df.sort_values(by=['date', 'prio', 'peak'], ascending=[True, True, False], inplace=True)
    df['cgs'] = 0.0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"# TEZAVER ÖZEL RAPOR (RSI-EMA > Max Ribbon)\n")
        f.write(f"Tarih: {TARGET_START_DATE} - {TARGET_END_DATE}\n")
        f.write(f"Tetik: RSI-EMA >= Max(Ribbon_20..55)\n\n")
        
        hdrs = ["NO", "SYM", "MAX", "CLOSE", "TIME", "SIG", "TREND", "POS", "ANG", "R-Ang", "VAL", "P", "TIER", "P-21", "BAR", "NEXT", "N-1", "CGS", "ADX", "ATR%", "Vrsi", "VBoy", "V100", "V21", "V-Mom"]
        
        all_dates = df['date'].unique()
        for date in sorted(all_dates):
            day_df = df[df['date'] == date]
            ayas_rows = []
            idx = 1
            for _, r in day_df.iterrows():
                rows_for_candidate = []
                for i, t in enumerate(r['triggers']):
                    row = format_row_data(r, t, i, idx)
                    rows_for_candidate.append(row)
                
                if rows_for_candidate:
                    ayas_rows.extend(rows_for_candidate)
                    idx += 1
            
            d_str = date.strftime("%d %B %Y")
            f.write(f"\n## 📅 {d_str} (Sayaç: {len(ayas_rows)})\n")
            if ayas_rows:
                write_aligned_table(f, ayas_rows, hdrs)

    print(f"Rapor oluşturuldu: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_custom_report()
