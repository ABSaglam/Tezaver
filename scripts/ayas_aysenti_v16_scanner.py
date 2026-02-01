#!/usr/bin/env python3
"""
AYAŞ TÜNELİ + AYSENTİ GEÇİDİ v16 FORMAT SCANNER
Ocak 2026 için Ayaş/Aysenti ayrımlı rapor üretir.
"""

import pandas as pd
import numpy as np
import os
import json
import re
import math
from datetime import datetime

# CONFIG
# CONFIG
# Dynamic Last 100 Days
now_ts = pd.Timestamp.now().normalize()
END_DATE = now_ts + pd.Timedelta(days=1)
START_DATE = now_ts - pd.Timedelta(days=100)
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
OUTPUT_FILE = "refined_global_report_v17.md"

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
    """
    DNA Profile Calculator.
    strict_before=True: Use data strictly BEFORE day (for Ayaş Tüneli - 00:00)
    strict_before=False: Use data UP TO and INCLUDING day (for Aysenti - EOD)
    
    CRITICAL LAW (AYAŞ TÜNELİ ANAYASASI):
    "Ayaş Tüneli'ne ASLA kapanmamış veriyle işlem yapılmaz."
    
    Implementation:
    1. WEEKLY: Must enforce strict cutoff (day - 7 days) to exclude current open week.
       Reason: Weekly candle timestamp is Monday open. If scan is on Wed, Monday row exists but is incomplete.
    2. DAILY/HOURLY (Ayaş Mode): Must use strict_before=True (index < day).
       Reason: At 00:00 scan time, the candle starting at 00:00 is just opening. Must look at yesterday's close.
    """
    try:
        # --- AYAŞ INTEGRITY CHECK (WEEKLY) ---
        # Kanun: Haftalık mumun tamamen kapanmış olması şarttır.
        integrity_cutoff_w = day - pd.Timedelta(days=7)
        sub_w = df_w[df_w.index <= integrity_cutoff_w].tail(30)
        
        # MIN DATA INTEGRITY:
        if len(sub_w) < 15: return "neutral"
        
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        
        # NaN CHECK: Yeni coinlerde rolling window yetmezse NaN döner
        if np.isnan(rsi_val): return "neutral"
        
        faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
        
        # HOURLY/DAILY LOGIC
        # CRITICAL LAW: Daily Data must NEVER include the current running day.
        # Regardless of scan hour (00:00 or 14:00), we only trust YESTERDAY'S Daily Close.
        daily_integrity_cutoff = day.normalize()
        
        if strict_before:
            # Ayaş (00:00) or Intraday Check (e.g. 04:00)
            # 4H/1H: Use closed candles < day.
            # (e.g. at 04:00, we use 00:00 4H candle which is < 04:00)
            sub_h1_24 = df_h1[df_h1.index < day].tail(24)
            sub_d = df_d[df_d.index < daily_integrity_cutoff]
            sub_h4 = df_h4[df_h4.index < day]
            sub_h1 = df_h1[df_h1.index < day]
        else:
            # Fallback for EOD checks (if used), but enforcing Daily Integrity is safer generally.
            sub_h1_24 = df_h1[df_h1.index <= day].tail(24)
            sub_d = df_d[df_d.index < daily_integrity_cutoff] # Still strict on daily!
            sub_h4 = df_h4[df_h4.index <= day]
            sub_h1 = df_h1[df_h1.index <= day]
            
        if sub_h1_24.empty or 'ema9' not in sub_h1_24: return "neutral"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        
        if sub_d.empty or sub_h4.empty or sub_h1.empty: return "neutral"
        # Check last available candle validity (avoid empties)
        if sub_d.iloc[-1].isnull().any(): return "neutral"

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

def format_row_data(r, t, i, idx):
    """Format row data for table output"""
    p_s = f"<font color='green'>+{r['peak']:.1f}%</font>" if r['peak']>10 else f"+{r['peak']:.1f}%"
    c_s = f"<font color='red'>{r['ret']:.1f}%</font>" if r['ret']<0 else f"+{r['ret']:.1f}%"
    
    # Vol-Change
    v_ch_val = t['v_ch']
    if v_ch_val > 1000: v_c = f"<font color='green'>+{v_ch_val:.1f}%</font>"
    elif v_ch_val > 500: v_c = f"<font color='orange'>+{v_ch_val:.1f}%</font>"
    else: v_c = f"+{v_ch_val:.1f}%"

    # Vol-Avg
    v_avg_val = t['v_avg']
    if v_avg_val > 1000: v_a = f"<font color='green'>+{v_avg_val:.1f}%</font>"
    elif v_avg_val > 500: v_a = f"<font color='orange'>+{v_avg_val:.1f}%</font>"
    else: v_a = f"+{v_avg_val:.1f}%"
        
    # V-Index
    v_index = t['v_index']
    v_idx_s = f"{v_index:.1f}"
    if v_index >= 10.0: v_i = f"<font color='#00FF00'>**{v_idx_s}**</font>"
    elif v_index >= 8.0: v_i = f"<font color='green'>{v_idx_s}</font>"
    elif v_index >= 4.0: v_i = v_idx_s
    elif v_index >= 2.0: v_i = f"<font color='gray'>{v_idx_s}</font>"
    else: v_i = f"<font color='#888888'>{v_idx_s}</font>"

    # V-Trend
    vt_v = t['v_trend']
    if vt_v > 2.0: vt_s = f"<font color='green'>**{vt_v:.1f}x**</font>"
    elif vt_v > 1.2: vt_s = f"<font color='green'>{vt_v:.1f}x</font>"
    elif vt_v < 0.8: vt_s = f"<font color='red'>{vt_v:.1f}x</font>"
    else: vt_s = f"{vt_v:.1f}x"

    # P-21
    pk_val = t['peak']
    if pk_val < 0: pk = f"<font color='red'>{pk_val:.1f}%</font>"
    elif pk_val > 0: pk = f"<font color='green'>+{pk_val:.1f}%</font>"
    else: pk = "0.0%"

    # Tier Symbols
    tier_icon = ""
    if pk_val >= 30.0: tier_icon = "💎"
    elif pk_val >= 20.0: tier_icon = "🥇"
    elif pk_val >= 10.0: tier_icon = "🥈"
    elif pk_val >= 5.0: tier_icon = "🥉"
    
    # BAR
    bar_val = str(t['peak_dist'])
    if t['peak_dist'] == 0: bar_val = f"<font color='red'>**0**</font>"
    elif t['is_limited']: bar_val = f"<font color='blue'>{bar_val}</font>"
    
    sig_val = f"{t['strat']}{'⛔' if t['is_stuck'] else ''}"
    
    # V-Dyn
    vd_s = f"{t['v_dyn']:.1f}"
    vd_f = f"<font color='green'>**{vd_s}**</font>" if t['v_dyn'] >= 8.0 else vd_s
    
    # V-Mom
    vm_s = f"{t['v_mom']:.1f}x"
    vm_f = f"<font color='green'>**{vm_s}**</font>" if t['v_mom'] > 1.5 else vm_s
    
    # V-Eff
    ve_s = f"{t['v_eff']:.1f}"
    if t['v_eff'] >= 7.0: ve_f = f"<font color='green'>**{ve_s}**</font>"
    elif t['v_eff'] < 3.0: ve_f = f"<font color='red'>{ve_s}</font>"
    else: ve_f = ve_s
    
    # V-Hyb
    vh_s = f"{t['v_hyb']:.1f}"
    if t['v_hyb'] >= 9.0: vh_f = f"<font color='#00FF00'>**{vh_s}**</font>"
    elif t['v_hyb'] >= 7.0: vh_f = f"<font color='green'>{vh_s}</font>"
    else: vh_f = vh_s

    # NEXT
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
    
    # N-1 (Next + 1 candle change)
    nn_val = "-"
    if t.get('next_next_pct') is not None:
        nnv = t['next_next_pct']
        if nnv > 0: nn_str = f"+{nnv:.1f}%"
        elif nnv < 0: nn_str = f"{nnv:.1f}%"
        else: nn_str = "0.0%"
        if nnv > 0: nn_val = f"<font color='green'>{nn_str}</font>"
        elif nnv < 0: nn_val = f"<font color='red'>{nn_str}</font>"
        else: nn_val = nn_str
    
    r_rib = "🟢" if t['rsi_rib'] == "Yes" else "🔴"
    
    # P (Trigger Size)
    tp = t['trig_pct']
    tp_str = f"+{tp:.1f}%" if tp > 0 else f"{tp:.1f}%"
    if abs(tp) > 20.0: trig_val = f"<font color='red'>**{tp_str}**</font>"
    elif abs(tp) > 10.0: trig_val = f"<font color='red'>{tp_str}</font>"
    else: trig_val = tp_str

    sym_str = r['symbol']
    if i == 0 and r.get('gate_time'):
         sym_str += f" ({r['gate_time']})"

    # === NEW COLUMN FORMATTING ===
    # Harmony: Correlation indicator
    harmony = t.get('harmony', 0.0)
    if harmony >= 0.7: harmony_f = "🎵"
    elif harmony >= 0.3: harmony_f = "🎶"
    elif harmony <= -0.3: harmony_f = "🔇"
    else: harmony_f = ""
    
    # RngPos: Range position indicator
    rng_pos = t.get('rng_pos', 50.0)
    if rng_pos >= 80: rngpos_f = f"🔝{rng_pos:.0f}"
    elif rng_pos <= 20: rngpos_f = f"🔻{rng_pos:.0f}"
    else: rngpos_f = f"{rng_pos:.0f}"
    
    # RSI-V: RSI-Volume sync
    rsi_v = t.get('rsi_v', '')
    if rsi_v == "DipBuy": rsiv_f = "💚DipBuy"
    elif rsi_v == "TopSell": rsiv_f = "🔴TopSell"
    else: rsiv_f = ""
    
    # ATR%: Volatility as % of price
    atr_pct = t.get('atr_adj', 0.0)
    d_atr = t.get('daily_atr', 0.0)
    
    # Tooltip with Daily ATR
    tooltip = f"Tetik ATR: {atr_pct:.1f}% &#013;Günlük ATR: {d_atr:.1f}%"
    
    if atr_pct >= 4.0: atr_f = f"<font color='#00FF00'>**{atr_pct:.1f}%**</font>"
    elif atr_pct >= 2.0: atr_f = f"<font color='DarkGreen'>**{atr_pct:.1f}%**</font>"
    elif atr_pct >= 1.0: atr_f = f"<font color='green'>{atr_pct:.1f}%</font>"
    else: atr_f = f"{atr_pct:.1f}%"
    
    # Wrap in span with title
    atr_f = f"<span title='{tooltip}'>{atr_f}</span>"
    
    # R-Ang (RSI Angle)
    r_ang = t.get('rsi_angle', 0.0)
    ra_str = f"{r_ang:.0f}°"
    if r_ang >= 45: ra_f = f"<font color='#00FF00'>**+{ra_str}**</font>" # Steep Up
    elif r_ang >= 10: ra_f = f"<font color='green'>+{ra_str}</font>" # Up
    elif r_ang <= -45: ra_f = f"<font color='red'>**{ra_str}**</font>" # Steep Down
    elif r_ang <= -10: ra_f = f"<font color='red'>{ra_str}</font>" # Down
    else: ra_f = f"<font color='gray'>{ra_str}</font>" # Flat

    # CGS (Coin Güvenilirlik Skoru) - passed via r dict
    cgs_val = r.get('cgs', 0.0)
    if cgs_val >= 50: cgs_f = f"<font color='green'>**{cgs_val:.0f}%**</font>"
    elif cgs_val >= 25: cgs_f = f"<font color='green'>{cgs_val:.0f}%</font>"
    elif cgs_val >= 10: cgs_f = f"{cgs_val:.0f}%"
    elif cgs_val > 0: cgs_f = f"<font color='gray'>{cgs_val:.0f}%</font>"
    else: cgs_f = "<font color='red'>0%</font>"

    # CVT (Conviction): Dünün son 4 saat sprinti
    cvt_val = t.get('cvt', 0.0)
    if cvt_val >= 1.0: cvt_f = f"<font color='green'>**+{cvt_val:.1f}%**</font>"
    elif cvt_val > 0: cvt_f = f"<font color='green'>+{cvt_val:.1f}%</font>"
    elif cvt_val <= -1.0: cvt_f = f"<font color='red'>**{cvt_val:.1f}%**</font>"
    elif cvt_val < 0: cvt_f = f"<font color='red'>{cvt_val:.1f}%</font>"
    else: cvt_f = "0.0%"

    # ADX (Trend Gücü)
    adx_val = t.get('adx', 0.0)
    if adx_val >= 40: adx_f = f"<font color='green'>**{adx_val:.0f}**</font>"
    elif adx_val >= 25: adx_f = f"<font color='green'>{adx_val:.0f}</font>"
    elif adx_val >= 20: adx_f = f"{adx_val:.0f}"
    else: adx_f = f"<font color='gray'>{adx_val:.0f}</font>"

    if i == 0:
        return [str(idx), sym_str, p_s, c_s, t['time'], sig_val, cvt_f, t['m_tr'], t['pos_icon'], t['ang_emoji'], ra_f, t['val_icon'], trig_val, tier_icon, pk, bar_val, next_val, nn_val, cgs_f, adx_f, atr_f, vh_f, ve_f, v_i, vd_f, vm_f]
    else:
        return ["", "", "", "", t['time'], sig_val, cvt_f, t['m_tr'], t['pos_icon'], t['ang_emoji'], ra_f, t['val_icon'], trig_val, tier_icon, pk, bar_val, next_val, nn_val, cgs_f, adx_f, atr_f, vh_f, ve_f, v_i, vd_f, vm_f]

def run_audit():
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    all_passed_days = []
    processed_pairs = set()

    for symbol in symbols:
        try:
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

            df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
            # Calculate Daily ATR for "Coin ATR" context
            d_tr = np.maximum(df_1d['high'] - df_1d['low'], np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), abs(df_1d['low'] - df_1d['close'].shift(1))))
            df_1d['atr14'] = d_tr.rolling(window=14).mean()
            df_1d['atr_pct'] = (df_1d['atr14'] / df_1d['close']) * 100
            
            # === ADX-14 HESAPLAMA ===
            plus_dm = df_1d['high'].diff()
            minus_dm = -df_1d['low'].diff()
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
            
            tr14_sum = d_tr.rolling(window=14).sum()
            plus_di = 100 * (plus_dm.rolling(window=14).sum() / tr14_sum)
            minus_di = 100 * (minus_dm.rolling(window=14).sum() / tr14_sum)
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.001)
            df_1d['adx14'] = dx.rolling(window=14).mean()
            # === ADX SONU ===

            df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
            for p in [9, 21, 50]: df_1h[f'ema{p}'] = df_1h['close'].ewm(span=p, adjust=False).mean()

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
            df_15m['atr14'] = tr.rolling(window=14).mean()
            df_15m['tr'] = tr

            current = START_DATE
            while current <= END_DATE:
                try:
                    pair_key = (symbol, current)
                    if pair_key in processed_pairs:
                        current += pd.Timedelta(days=1); continue

                    # AYAŞ TÜNELİ: 00:00'da Golden mi? (strict_before=True)
                    dna_ayas = get_profile_simple(current, df_1w, df_1h, df_1d, df_4h, strict_before=True)
                    is_ayas = (dna_ayas != "neutral") and (dna_ayas in golden_dna_list)
                    
                    # AYSENTİ GEÇİDİ: Gün içinde (4'er saatlik mumlarla) tünele girenler
                    # Ayaş değilse, günün ilerleyen saatlerine bak (04:00, 08:00, 12:00, 16:00, 20:00)
                    is_aysenti = False
                    dna_aysenti = "neutral"
                    aysenti_time = "00:00"
                    
                    if not is_ayas:
                        # Intraday Scan Loop
                        pass
                    
                    # Kaynak ve DNA belirleme
                    if is_ayas:
                        source = "AYAŞ"
                        dna = dna_ayas
                    elif is_aysenti:
                        source = "AYSENTİ"
                        dna = dna_aysenti
                        # Aysenti giriş saatini trigger'a eklemek (opsiyonel) veya raporda belirtmek gerekebilir
                        # Şimdilik satır verisi olarak kalsın, trigger time zaten sinyal saatini gösterecek.
                    else:
                        current += pd.Timedelta(days=1); continue

                    current_utc = current.normalize()
                    day_mask = (df_15m.index.normalize() == current_utc)
                    target_day_data = df_15m[day_mask]
                    if target_day_data.empty:
                        current += pd.Timedelta(days=1); continue

                    open_p, max_h, close_p = target_day_data.iloc[0]['open'], target_day_data['high'].max(), target_day_data.iloc[-1]['close']
                    
                    # Get Daily ATR for this specific date (use previous day to be safe/realistic or current if EOD)
                    try:
                        daily_atr_val = df_1d.loc[df_1d.index.normalize() == current.normalize(), 'atr_pct']
                        if not daily_atr_val.empty:
                            d_atr = daily_atr_val.values[0]
                        else:
                            d_atr = df_1d['atr_pct'].iloc[-1]
                    except:
                        d_atr = 0.0

                    # Get Daily ADX for this specific date
                    try:
                        daily_adx_val = df_1d.loc[df_1d.index.normalize() == current.normalize(), 'adx14']
                        if not daily_adx_val.empty:
                            d_adx = daily_adx_val.values[0]
                            if np.isnan(d_adx): d_adx = 0.0
                        else:
                            d_adx = df_1d['adx14'].iloc[-1]
                            if np.isnan(d_adx): d_adx = 0.0
                    except:
                        d_adx = 0.0

                    # === CVT (CONVICTION): DÜNÜN SON 4 SAAT SPRİNTİ ===
                    cvt_yesterday = 0.0
                    try:
                        yesterday = current - pd.Timedelta(days=1)
                        yesterday_mask = df_15m.index.normalize() == yesterday.normalize()
                        yesterday_data = df_15m[yesterday_mask]
                        if len(yesterday_data) >= 20:
                            # Son 4 saat = son 16 bar (15m * 16)
                            last_4h = yesterday_data.tail(16)
                            if len(last_4h) >= 10:
                                evening_start = last_4h.iloc[0]['open']
                                evening_end = last_4h.iloc[-1]['close']
                                cvt_yesterday = ((evening_end / evening_start) - 1) * 100
                    except:
                        cvt_yesterday = 0.0
                    # === CVT SONU ===

                    # === YENİ TETİK: RSI-EMA tüm Ribbon çizgilerinin üzerine çıkınca ===
                    # Ribbon çizgileri: rsi_rib_20, 25, 30, 35, 40, 45, 50, 55
                    rsi_ema_vals = df_15m['rsi_ema'].values
                    
                    # Her bar için: RSI-EMA tüm ribbon'ların üzerinde mi?
                    all_above = np.ones(len(df_15m), dtype=bool)
                    for col in rsi_ribbon_cols:
                        all_above &= (rsi_ema_vals > df_15m[col].values)
                    
                    # Kesişim anı: Önceki bar üstte değil, şimdiki bar üstte
                    prev_not_above = ~np.roll(all_above, 1)
                    prev_not_above[0] = True  # İlk bar için edge case
                    
                    # Tetik indeksleri: Kesişim anları
                    all_trigger_indices = np.where(prev_not_above & all_above)[0]
                    # === TETİK SONU ===
                    
                    trigger_events = []
                    day_indices = np.where(day_mask)[0]
                    for i in day_indices:
                        if i < 21: continue
                        
                        is_trigger = i in all_trigger_indices
                        if is_trigger:
                            trig_time = df_15m.index[i]
                            
                            # 4H/1H Trend Look-Ahead Fix
                            # Only use FULLY CLOSED candles.
                            # Condition: candle_timestamp <= trig_time - duration
                            
                            # 4H
                            cutoff_4h = trig_time - pd.Timedelta(hours=4)
                            last_4h = df_4h[df_4h.index <= cutoff_4h]
                            t4 = "🟢" if not last_4h.empty and last_4h.iloc[-1]['close'] > last_4h.iloc[-1]['ema21'] else "🔴"
                            
                            # 1H
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
                                
                                # Next + 1 calculation
                                nn_idx = next_idx + 1
                                if nn_idx < len(df_15m):
                                    nn_c = df_15m['close'].values[nn_idx]
                                    # Change from NEXT close to NEXT+1 close? Or from peak?
                                    # Usually "next candle change" implies change of that specific candle (Close - Open) / Open
                                    # OR change relative to previous candle close.
                                    # Given NEXT is calculated as change from Peak to Next_Close.
                                    # Let's calculate N-1 as change from Next_Close to Next_Next_Close.
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
                            
                            if abs(ang_score) > 5.0:
                                ang_e = f"<font color='{num_color}'>**{val_str}**</font>"
                            else:
                                ang_e = f"<font color='{num_color}'>{val_str}</font>"

                            if curr_v < 30: pos_icon = "⚫"
                            elif curr_v < 50: pos_icon = "🔴"
                            elif curr_v < 60: pos_icon = "🟡"
                            elif curr_v < 70: pos_icon = "🟢"
                            else: pos_icon = "🟠"

                            # === NEW METRICS ===
                            # 1. Harmony Index: Correlation of Volume Change vs Price Change (last 5 bars)
                            harmony_val = 0.0
                            if i >= 5:
                                vol_changes = np.diff(df_15m['volume'].values[i-5:i+1])
                                price_changes = np.diff(df_15m['close'].values[i-5:i+1])
                                if len(vol_changes) >= 2 and np.std(vol_changes) > 0 and np.std(price_changes) > 0:
                                    harmony_val = np.corrcoef(vol_changes, price_changes)[0, 1]
                                    if np.isnan(harmony_val): harmony_val = 0.0
                            
                            # 2. Range Position: Where is price in 21-day range? (0-100)
                            rng_pos = 50.0
                            if len(df_1d) >= 21:
                                cutoff_day = trig_time.normalize()
                                d_sub = df_1d[df_1d.index < cutoff_day].tail(21)
                                if len(d_sub) >= 5:
                                    high_21 = d_sub['high'].max()
                                    low_21 = d_sub['low'].min()
                                    if high_21 > low_21:
                                        current_close = df_15m['close'].values[i]
                                        rng_pos = ((current_close - low_21) / (high_21 - low_21)) * 100
                                        rng_pos = max(0, min(100, rng_pos))
                            
                            # 3. RSI-V Sync: RSI zone + Volume spike detection
                            rsi_val_now = df_15m['rsi'].values[i]
                            vol_spike = (v_t / v_a21) > 1.5
                            if rsi_val_now < 35 and vol_spike:
                                rsi_v_sync = "DipBuy"
                            elif rsi_val_now > 70 and vol_spike:
                                rsi_v_sync = "TopSell"
                            else:
                                rsi_v_sync = ""
                            
                            # 4. ATR-Adj: Volatility score (ATR21 relative to price)
                            atr_adj = 0.0
                            atr21_val = df_15m['atr21'].values[i]
                            close_val = df_15m['close'].values[i]
                            if close_val > 0:
                                atr_adj = (atr21_val / close_val) * 100  # ATR as % of price

                            # 5. RSI-EMA Angle (Horizontal = 0, Up = +, Down = -)
                            rsi_ema_now = df_15m['rsi_ema'].values[i]
                            rsi_ema_prev = df_15m['rsi_ema'].values[i-1] if i > 0 else rsi_ema_now
                            rsi_slope = rsi_ema_now - rsi_ema_prev
                            rsi_angle = math.degrees(math.atan(rsi_slope))

                            trigger_events.append({
                                'time': df_15m.index[i].strftime("%H:%M"), 'mac_color': mac_c, 'v_index': v_idx,
                                'strat': strat_signal,
                                'rsi_rib': "Yes" if all(df_15m['rsi_ema'].values[i] > df_15m[c].values[i] for c in rsi_ribbon_cols) else "",
                                'v_ch': ((v_t/v_p)-1)*100, 'v_avg': ((v_t/v_a21)-1)*100, 'v_trend': v_trend, 'v_spread': v_spread,
                                'peak': ((peak_p/df_15m['close'].values[i])-1)*100,
                                'peak_dist': peak_dist,
                                'is_stuck': is_stuck,
                                'is_limited': is_limited,
                                'm_tr': m_tr,
                                'next_pct': next_pct,
                                'next_next_pct': next_next_pct,
                                'trig_pct': trig_pct,
                                'daily_atr': d_atr,  # Pass daily ATR
                                'rsi_angle': rsi_angle, # Pass RSI Angle
                                'ang_emoji': ang_e,
                                'val_icon': src_heart,
                                'pos_icon': pos_icon,
                                'v_dyn': v_dyn, 'v_mom': v_mom, 'v_eff': v_eff, 'v_hyb': v_hyb,
                                'harmony': harmony_val, 'rng_pos': rng_pos, 'rsi_v': rsi_v_sync, 'atr_adj': atr_adj,
                                'cvt': cvt_yesterday,  # Conviction: Dün gece sprinti
                                'adx': d_adx,  # ADX-14 Trend Gücü
                            })

                    all_passed_days.append({
                        'date': current, 'symbol': symbol, 'dna': dna, 'source': source,
                        'gate_time': aysenti_time if source == "AYSENTİ" else None,
                        'peak': ((max_h/open_p)-1)*100, 'ret': ((close_p/open_p)-1)*100,
                        'triggers': trigger_events,
                        'is_stuck_day': (close_p < open_p),
                        'prio': min([{"🟢":1,"🟣":2,"🟡":3,"🔴":4}.get(t['mac_color'],5) for t in trigger_events]) if trigger_events else 5
                    })
                    processed_pairs.add(pair_key)
                except Exception as e:
                    print(f"Error processing {symbol}: {e}")
                current += pd.Timedelta(days=1)
        except: continue

    df = pd.DataFrame(all_passed_days)
    if df.empty: return print("Boş Rapor.")
    
    # Sort
    df['frek'] = df.groupby(['date', 'dna'])['symbol'].transform('count')
    df.sort_values(by=['date', 'source', 'prio', 'peak'], ascending=[True, True, True, False], inplace=True)

    # === CGS (Coin Güvenilirlik Skoru) HESAPLAMA ===
    # Her coin için: toplam gün sayısı ve tier yapmış gün sayısını hesapla
    coin_tier_stats = {}
    for _, row in df.iterrows():
        sym = row['symbol']
        if sym not in coin_tier_stats:
            coin_tier_stats[sym] = {'total': 0, 'tiered': 0}
        coin_tier_stats[sym]['total'] += 1
        # Check if any trigger in this day has tier (peak >= 5%)
        if row['triggers']:
            if any(t['peak'] >= 5.0 for t in row['triggers']):
                coin_tier_stats[sym]['tiered'] += 1
    
    # CGS hesapla
    coin_cgs = {}
    for sym, stats in coin_tier_stats.items():
        if stats['total'] > 0:
            coin_cgs[sym] = (stats['tiered'] / stats['total']) * 100
        else:
            coin_cgs[sym] = 0.0
    
    # DataFrame'e CGS ekle
    df['cgs'] = df['symbol'].map(coin_cgs)
    # === CGS HESAPLAMA SONU ===

    # Save to file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# TEZAVER GLOBAL AUDIT REPORT (AYAŞ TÜNELİ + AYSENTİ GEÇİDİ) v17\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (ONLY AYAŞ MODE)\n")
        months = {1:"Ocak", 2:"Şubat", 3:"Mart", 4:"Nisan", 5:"Mayıs", 6:"Haziran", 7:"Temmuz", 8:"Ağustos", 9:"Eylül", 10:"Ekim", 11:"Kasım", 12:"Aralık"}
        hdrs = ["NO", "SYM", "MAX", "CLOSE", "TIME", "SIG", "CVT", "TREND", "POS", "ANG", "R-Ang", "VAL", "P", "TIER", "P-21", "BAR", "NEXT", "N-1", "CGS", "ADX", "ATR%", "Vrsi", "VBoy", "V100", "V21", "V-Mom"]
        
        all_dates = df['date'].unique()
        for date in sorted(all_dates):
            day_df = df[df['date'] == date]
            ayas_df = day_df[day_df['source'] == 'AYAŞ']
            # aysenti_df logic removed
            
            ayas_rows = []
            idx = 1
            for _, r in ayas_df.sort_values(by=['prio', 'peak'], ascending=[True, False]).iterrows():
                if r['dna'] == "neutral" or not r['triggers']: continue
                if all(t['is_stuck'] for t in r['triggers']): continue
                

                
                rows_for_candidate = []
                for i, t in enumerate(r['triggers']):
                    row = format_row_data(r, t, i, idx)
                    rows_for_candidate.append(row)
                
                if rows_for_candidate:
                    ayas_rows.extend(rows_for_candidate)
                    idx += 1



            # Count unique symbols
            ayas_count = len([r for r in ayas_rows if r[0] != ""])
            
            d_str = f"{date.day:02d} {months[date.month]} {date.year}"
            f.write(f"\n## 📅 {d_str} (Ayaş: {ayas_count})\n")
            
            # AYAŞ TÜNELİ section
            if ayas_rows:
                f.write("\n### 🚇 AYAŞ TÜNELİ\n\n")
                write_aligned_table(f, ayas_rows, hdrs)

    print(f"Rapor: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_audit()
