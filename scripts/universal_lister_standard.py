#!/usr/bin/env python3
"""
TEZAVER UNIVERSAL LISTER (STANDARD FORMAT)
Generates reports in the project's official Standard Format.
Usage:
  python3 universal_lister_standard.py --days 3
  python3 universal_lister_standard.py --start 2026-01-01 --end 2026-01-31
"""

import pandas as pd
import numpy as np
import os
import json
import re
import math
import sys
import argparse
from datetime import datetime, timedelta

# Portakal Sıkacağı Integration
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from portakal_sikacagi import apply_portakal_sikacagi
    PORTAKAL_AVAILABLE = True
except ImportError:
    PORTAKAL_AVAILABLE = False

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
GOLDEN_KEYS_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys"
GLOBAL_AUDIT_PATH = "/Users/alisaglam/TezaverMac/data/global_performance_audit.json"

GLOBAL_ELITE_DNAS = set()
try:
    if os.path.exists(GLOBAL_AUDIT_PATH):
        with open(GLOBAL_AUDIT_PATH, "r") as f:
            audit_data = json.load(f)
            # Power Score > 5000 is elite (Top ~10 DNAs)
            # Or just take top 100 entries. Let's take top 100.
            for entry in audit_data[:100]:
                GLOBAL_ELITE_DNAS.add(entry.get('dna'))
except: pass

# --- IGNITOR ENGINE INTEGRATION ---
IGNITION_SOUL_PATH = "/Users/alisaglam/TezaverMac/ignition_soul_manifest.json"
class IgnitorEngine:
    def __init__(self, soul_path=IGNITION_SOUL_PATH):
        self.soul = {}
        if os.path.exists(soul_path):
            with open(soul_path, "r") as f:
                self.soul = json.load(f)
    def get_threshold(self, symbol):
        return self.soul.get(symbol, 5.0) # Default to 5.0x
    def analyze_sequence(self, df_15m, t0_idx, symbol, pure_mode=False, df_1h=None, btc_df_15m=None, d_atr=0.0):
        if t0_idx + 2 >= len(df_15m): return False, "", 0
        t0, t1, t2 = df_15m.iloc[t0_idx], df_15m.iloc[t0_idx + 1], df_15m.iloc[t0_idx + 2]
        t_time = df_15m.index[t0_idx]
        
        vol_ma = t0['vol_ma50'] if t0['vol_ma50'] > 0 else 0.001
        vol_ratio_t0 = t0['volume'] / vol_ma
        threshold = self.get_threshold(symbol)
        is_sovereign = vol_ratio_t0 >= (threshold * 2.4)
        
        # (Bypass logic removed as per Ali Beyim's 'step-by-step' directive)

        # --- PHASE 5: KUTSAL KASE (Absolute Verdict) ---
        if btc_df_15m is not None:
             # Find BTC data for the exact same point
             try:
                 btc_t0 = btc_df_15m.loc[t_time]
                 btc15m_ret = (btc_t0['close'] / btc_t0['open']) - 1
                 
                 # 1. BTC Anchor: If BTC 15m is dumping (>0.5% drop), abort all
                 if btc15m_ret < -0.005: 
                      return False, "Aborted: BTC Dumping", 0
                 
                 # 2. RS-Index (Relative Strength): 
                 coin_ret = (t0['close'] / t0['open']) - 1
                 # Holy Grail Rule: Alpha Multiplier (1.2x market performance)
                 alpha_mult = 1.2
                 if pure_mode:
                      if btc15m_ret > 0 and coin_ret < (btc15m_ret * alpha_mult):
                           return False, f"Rejected: Low Alpha ({coin_ret/btc15m_ret:.2f}x)", 0
                      elif btc15m_ret <= 0 and coin_ret < 0.01: # Min 1% solo move if market is flat/down
                           return False, "Rejected: Weak Solo Move", 0
             except: pass

        # --- AHENK (1H Trend Harmony) ---
        if df_1h is not None and pure_mode:
             h_idx = df_1h.index.asof(t_time)
             if h_idx in df_1h.index:
                  h_data = df_1h.loc[h_idx]
                  if h_data['close'] < h_data['ema21'] or h_data['ema9'] < h_data['ema21']:
                       return False, "Ahenksiz: 1H Negative", 0
        
        # --- RUH (Volatility Compression / Squeeze) ---
        if pure_mode:
             pre_atr_avg = df_15m['tr'].iloc[max(0, t0_idx-50):t0_idx].mean()
             long_atr_avg = df_15m['atr100'].iloc[t0_idx]
             if pre_atr_avg > (long_atr_avg * 1.2):
                  return False, "Ruhsuz: Volatile Prelude", 0

        # --- PREDICATIVE SIETERS (The Oracle's Blade) ---
        body_t0 = abs(t0['close'] - t0['open'])
        range_t0 = (t0['high'] - t0['low']) or 0.001
        v_eff_t0 = (body_t0 / range_t0) * 10
        
        # 3. Squat Bar Filter (Phase 5): Giant Volume but no price expansion = Distribution Trap
        if pure_mode and vol_ratio_t0 > 8.0 and v_eff_t0 < 5.0:
             return False, "Rejected: Squat Bar (Distribution)", 0

        # Oracle Rule 1: Body Integrity (Tightened for %100)
        min_eff = 8.5 if pure_mode else 6.5
        if v_eff_t0 < min_eff: return False, "Rejected: Weak Body", 0
        
        # Oracle Rule 4: Immediate Trend Alignment (15m)
        ema9_15 = t0['ema9'] if 'ema9' in df_15m.columns else t0['close']
        if pure_mode and t0['close'] < ema9_15:
             return False, "Rejected: Below 15m EMA9", 0

        # --- PHASE 6: GIYOTIN KORUMASI (Anti-Climax & Wick of Death) ---
        if pure_mode:
             # Standard protections for Non-Sovereign
             # 1. Climax Rejector: If T0 return > 2.0x Daily ATR, it's exhaustion.
             t0_ret = (t0['close'] / t0['open']) - 1
             if d_atr > 0 and (t0_ret * 100) > (d_atr * 2.0):
                  return False, f"Rejected: Extreme Climax ({t0_ret*100:.1f}%)", 0
             
             # 2. Wick of Death: Upper shadow > 40% of total bar range.
             upper_wick = t0['high'] - max(t0['open'], t0['close'])
             if range_t0 > 0 and (upper_wick / range_t0) > 0.40:
                  return False, "Rejected: Wick of Death", 0

             # 3. RSI Overheat: Momentum is already over-extended. (Always Active)
             if t0['rsi'] > 85.0:
                  return False, "Rejected: RSI Overheat (>85)", 0
             
             # --- PHASE 7: V-MOM GUARD (Speed Filter) ---
             t0_ret = (t0['close'] / t0['open']) - 1
             if vol_ratio_t0 > 10.0 and t0_ret < 0.015:
                  return False, "Rejected: V-Mom Trap", 0

        # Entry Decision
             
        if vol_ratio_t0 < threshold: return False, "", 0
        
        # Oracle Rule 2: Volume Decay
        vol_ratio_t1 = t1['volume'] / vol_ma
        vol_ratio_t2 = t2['volume'] / vol_ma
        if pure_mode:
            if vol_ratio_t1 < (vol_ratio_t0 * 0.40): return False, "Rejected: Vol Decay", 0
            if vol_ratio_t2 < (vol_ratio_t0 * 0.30): return False, "Rejected: Vol Decay", 0
            
        # Oracle Rule 3: RSI Acceleration
        rsi_acc = (t2['rsi'] - t1['rsi']) - (t1['rsi'] - t0['rsi'])
        if pure_mode and rsi_acc < -3.0: return False, "Rejected: RSI Slowing", 0
        
        if vol_ratio_t1 < 1.5: return False, "", 0
        if t1['close'] < t0['open']: return False, "", 0
        
        # Oracle Rule 5: Momentum Apex (Balanced Floor)
        if pure_mode:
             if t0['rsi'] < 50.0 or t2['rsi'] < 50.0:
                  return False, "Rejected: Below RSI Apex Floor", 0
             
             # Structural Breakout: T2 must close above T0 high
             if t2['close'] < t0['high']:
                  return False, "Rejected: Failed Structural Breakout", 0

        if t2['rsi'] < t0['rsi'] or t2['rsi_ema'] <= t1['rsi_ema']: return False, "", 0
        
        return True, "🔥 KASE-V", 2

IGNITOR = IgnitorEngine()

def strip_tags(s):
    return re.sub(r'<[^>]+>', '', str(s))

def format_cell(val, width):
    s = str(val)
    content_len = len(strip_tags(s))
    padding = max(0, width - content_len)
    return " " + s + " " * padding + " "

def write_aligned_table_stdout(rows, headers):
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
    
    print(header_line)
    print(sep_line)
    
    for r in rows:
        row_line = "|"
        for i, val in enumerate(r):
            if i < len(col_widths):
                row_line += format_cell(val, col_widths[i]) + "|"
        print(row_line)

def get_profile_simple(day, df_w, df_h1, df_d, df_h4):
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
        
        # Simple daily check
        daily_integrity = day.normalize()
        sub_d = df_d[df_d.index < daily_integrity]
        sub_h4 = df_h4[df_h4.index < day]
        sub_h1 = df_h1[df_h1.index < day]
        sub_h1_24 = df_h1[df_h1.index < day].tail(24)

        if sub_h1_24.empty or 'ema9' not in sub_h1_24: return "neutral"
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        
        if sub_d.empty or sub_h4.empty or sub_h1.empty: return "neutral"
        
        s = int(sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21']) + \
            int(sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21']) + \
            int(sub_h1.iloc[-1]['close']>sub_h1.iloc[-1]['ema21'])
        harm = f"harmony_L{s}"
        
        sub_d_tail = sub_d.tail(10)
        vol_p = sub_d.iloc[-1]['volume'] / (sub_d_tail['volume'].mean()+1)
        ritim = "ignited" if vol_p > 2.0 else "active" if vol_p > 1.0 else "sleeping"
        
        yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
        retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
        ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|depleting_energy" # Simplified
    except: return "neutral"

def format_row_data(r, t, i, idx):
    pk_val = t['peak']
    e_ret = t.get('exit_ret', 0.0) * 100
    
    p_s = f"<font color='green'>+{pk_val:.1f}%</font>" if pk_val > 10 else f"+{pk_val:.1f}%"
    e_s = f"<font color='red'>{e_ret:.1f}%</font>" if e_ret < 0 else f"+{e_ret:.1f}%"
    
    if e_ret >= 3.0: e_s = f"<font color='green'>**{e_s}**</font>"
    elif e_ret >= 0.5: e_s = f"<font color='green'>{e_s}</font>"
    
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
    else: pk = "0.0%"

    tier_icon = ""
    if pk_val >= 30.0: tier_icon = "💎"
    elif pk_val >= 20.0: tier_icon = "🥇"
    elif pk_val >= 10.0: tier_icon = "🥈"
    elif pk_val >= 5.0: tier_icon = "🥉"
    
    bar_val = str(t['peak_dist'])
    if t['peak_dist'] == 0: bar_val = f"<font color='red'>**0 ⚡ FLASH**</font>"
    elif t['is_limited']: bar_val = f"<font color='blue'>{bar_val}</font>"
    
    sig_val = f"{t['strat']}" 
    
    vd_s = f"{t['v_dyn']:.1f}"
    vd_f = f"<font color='green'>**{vd_s}**</font>" if t['v_dyn'] >= 8.0 else vd_s
    
    vm_s = f"{t['v_mom']:.1f}x"
    vm_f = f"<font color='green'>**{vm_s}**</font>" if t['v_mom'] > 1.5 else vm_s
    
    ve_s = f"{t['v_eff']:.1f}"
    if t['v_eff'] >= 7.0: ve_f = f"<font color='green'>**{ve_s}**</font>"
    elif t['v_eff'] < 3.0: ve_f = f"<font color='red'>{ve_s}</font>"
    else: ve_f = ve_s
    
    vh_s = f"{t['v_hyb']:.1f}"
    if t['v_hyb'] >= 9.0: vh_f = f"<font color='#00FF00'>**{vh_s}**</font>"
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
    
    nn_val = "-"
    if t.get('next_next_pct') is not None:
        nnv = t['next_next_pct']
        if nnv > 0: nn_str = f"+{nnv:.1f}%"
        elif nnv < 0: nn_str = f"{nnv:.1f}%"
        else: nn_str = "0.0%"
        if nnv > 0: nn_val = f"<font color='green'>{nn_str}</font>"
        elif nnv < 0: nn_val = f"<font color='red'>{nn_str}</font>"
        else: nn_val = nn_str
    
    trig_val = f"+{t['trig_pct']:.1f}%" if t['trig_pct'] > 0 else f"{t['trig_pct']:.1f}%"

    sym_str = r['symbol']

    atr_pct = t.get('atr_adj', 0.0)
    d_atr = t.get('daily_atr', 0.0)
    tooltip = f"Tetik ATR: {atr_pct:.1f}% &#013;Günlük ATR: {d_atr:.1f}%"
    
    if atr_pct >= 4.0: atr_f = f"<font color='#00FF00'>**{atr_pct:.1f}%**</font>"
    elif atr_pct >= 2.0: atr_f = f"<font color='DarkGreen'>**{atr_pct:.1f}%**</font>"
    elif atr_pct >= 1.0: atr_f = f"<font color='green'>{atr_pct:.1f}%</font>"
    else: atr_f = f"{atr_pct:.1f}%"
    atr_f = f"<span title='{tooltip}'>{atr_f}</span>"
    
    # R-Ang (RSI Angle)
    r_ang = t.get('rsi_angle', 0.0)
    ra_str = f"{r_ang:.0f}°"
    if r_ang >= 45: ra_f = f"<font color='#00FF00'>**+{ra_str}**</font>" 
    elif r_ang >= 10: ra_f = f"<font color='green'>+{ra_str}</font>" 
    elif r_ang <= -45: ra_f = f"<font color='red'>**{ra_str}**</font>" 
    elif r_ang <= -10: ra_f = f"<font color='red'>{ra_str}</font>" 
    else: ra_f = f"<font color='gray'>{ra_str}</font>" 

    cgs_val = r.get('cgs', 0.0)
    if cgs_val >= 50: cgs_f = f"<font color='green'>**{cgs_val:.0f}%**</font>"
    elif cgs_val >= 25: cgs_f = f"<font color='green'>{cgs_val:.0f}%</font>"
    elif cgs_val > 0: cgs_f = f"<font color='gray'>{cgs_val:.0f}%</font>"
    else: cgs_f = "<font color='red'>0%</font>"

    adx_val = t.get('d_adx', 0.0)
    if adx_val >= 25: adx_f = f"<font color='green'>**{adx_val:.1f}**</font>"
    elif adx_val >= 20: adx_f = f"<font color='green'>{adx_val:.1f}</font>"
    else: adx_f = f"<font color='gray'>{adx_val:.1f}</font>"

    pos_icon = t['pos_icon']
    ang_emoji = t['ang_emoji']
    val_icon = t['val_icon']

    if i == 0:
        return [str(idx), sym_str, p_s, e_s, t['time'], sig_val, t['m_tr'], pos_icon, ang_emoji, ra_f, val_icon, trig_val, tier_icon, pk, bar_val, next_val, nn_val, cgs_f, adx_f, atr_f, vh_f, ve_f, v_i, vd_f, vm_f]
    else:
        return ["", "", "", "", t['time'], sig_val, t['m_tr'], pos_icon, ang_emoji, ra_f, val_icon, trig_val, tier_icon, pk, bar_val, next_val, nn_val, cgs_f, adx_f, atr_f, vh_f, ve_f, v_i, vd_f, vm_f]

def main():
    parser = argparse.ArgumentParser(description="Tezaver Standard Universal Lister")
    parser.add_argument('--days', type=int, help='Number of days to look back')
    parser.add_argument('--start', type=str, help='Start date YYYY-MM-DD')
    parser.add_argument('--end', type=str, help='End date YYYY-MM-DD')
    parser.add_argument('--mode', type=str, help='Project suffix (optional)')
    parser.add_argument('--disable-ayas', action='store_true', help='Disable Ayas Tunnel strict filtering')
    parser.add_argument('--sealed', action='store_true', help='Enable strict Ayas Tunnel (Daily Golden Key permission)')
    parser.add_argument('--ignitor', action='store_true', help='Enable Volume Ignition (3-Bar Sequence) mode')
    parser.add_argument('--tier-only', action='store_true', help='Only show signals that achieved a Tier (Bronze+) result')
    
    args = parser.parse_args()

    # Disable Ayas Check by default for "Universal" listing unless specified otherwise? 
    # The custom specific reporter had DISABLE_AYAS_CHECK = True. Let's keep it True for broad listing.
    DISABLE_AYAS_CHECK = True 

    if args.days:
        end_d = datetime.now()
        start_d = end_d - timedelta(days=args.days)
    elif args.start:
        start_d = datetime.strptime(args.start, "%Y-%m-%d")
        if args.end:
            end_d = datetime.strptime(args.end, "%Y-%m-%d")
        else:
            end_d = datetime.now()
    else:
        # Default 3 days
        end_d = datetime.now()
        start_d = end_d - timedelta(days=3)

    print(f"\n📊 TEZAVER LISTING ({start_d.strftime('%Y-%m-%d')} -> {end_d.strftime('%Y-%m-%d')})")
    print("-" * 60)

    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    all_passed_days = []
    processed_pairs = set()

    pd_start = pd.Timestamp(start_d)
    pd_end = pd.Timestamp(end_d) + pd.Timedelta(days=1)

    # --- PHASE 5: BTC CONTEXT LOADING ---
    btc_df_15m = None
    try:
        btc_p15m = f"{COIN_CELLS_DIR}/BTCUSDT/data/history_15m.parquet"
        if os.path.exists(btc_p15m):
            btc_df_15m = pd.read_parquet(btc_p15m)
            btc_df_15m['dt'] = pd.to_datetime(btc_df_15m['timestamp'], unit='ms')
            btc_df_15m.set_index('dt', inplace=True)
            btc_df_15m = btc_df_15m[~btc_df_15m.index.duplicated(keep='last')].sort_index()
    except: pass

    for symbol in symbols:
        try:
            # We don't necessarily need the golden key if we are doing universal scan with disable_ayas_check=True
            # But let's check basic data existence
            
            p_1d = f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet"
            p_15m = f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet"
            
            if not os.path.exists(p_1d) or not os.path.exists(p_15m): continue

            def load_clean(path):
                df = pd.read_parquet(path)
                df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('dt', inplace=True)
                df = df[~df.index.duplicated(keep='last')]
                return df.sort_index()

            df_1d = load_clean(p_1d)
            df_4h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
            df_1h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
            df_1w = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")
            df_15m = load_clean(p_15m)

            # Calculation similar to custom reporter
            df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()
            d_tr = np.maximum(df_1d['high'] - df_1d['low'], np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), abs(df_1d['low'] - df_1d['close'].shift(1))))
            df_1d['atr14'] = d_tr.rolling(window=14).mean()
            df_1d['atr_pct'] = (df_1d['atr14'] / df_1d['close']) * 100
            
            # ADX
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

            delta = df_15m['close'].diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/11, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/11, adjust=False).mean().replace(0, 0.001)
            df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
            df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
            
            for p in [20, 55]:
                df_15m[f'rsi_rib_{p}'] = df_15m['rsi_ema'].ewm(span=p, adjust=False).mean()
            
            ema12 = df_15m['close'].ewm(span=12, adjust=False).mean()
            ema26 = df_15m['close'].ewm(span=26, adjust=False).mean()
            df_15m['macd_hist'] = (ema12 - ema26) - (ema12 - ema26).ewm(span=9, adjust=False).mean()
            
            tr = np.maximum(df_15m['high'] - df_15m['low'], np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)), abs(df_15m['low'] - df_15m['close'].shift(1))))
            df_15m['atr100'] = tr.rolling(window=100).mean()
            df_15m['atr21'] = tr.rolling(window=21).mean()
            df_15m['vol_ma50'] = df_15m['volume'].rolling(window=50).mean()
            df_15m['tr'] = tr

            current = pd_start
            while current <= pd_end:
                try:
                    pair_key = (symbol, current.strftime('%Y-%m-%d'))
                    if pair_key in processed_pairs:
                        current += pd.Timedelta(days=1); continue

                    current_utc = current.normalize()
                    day_mask = (df_15m.index.normalize() == current_utc)
                    target_day_data = df_15m[day_mask]
                    if target_day_data.empty:
                        current += pd.Timedelta(days=1); continue

                    open_p = target_day_data.iloc[0]['open']
                    max_h = target_day_data['high'].max()
                    close_p = target_day_data.iloc[-1]['close']
                    
                    try:
                        daily_atr_val = df_1d.loc[df_1d.index.normalize() == current_utc, 'atr_pct']
                        d_atr = daily_atr_val.values[0] if not daily_atr_val.empty else df_1d['atr_pct'].iloc[-1]
                        daily_adx_val = df_1d.loc[df_1d.index.normalize() == current_utc, 'adx14']
                        d_adx = daily_adx_val.values[0] if not daily_adx_val.empty else df_1d['adx14'].iloc[-1]
                    except:
                        d_atr = 0.0
                        d_adx = 0.0

                    rsi_vals = df_15m['rsi'].values
                    # Trigger logic: RSI crosses 70 up
                    # We need to map day indices to full array indices
                    # But simpler: calculate crossing on full array, then filter for today
                    
                    # Optimization: only check indices for this day
                    day_indices = np.where(day_mask)[0]
                    
                    trig_list = []
                    
                    # 1. ALWAYS Identify Sniper candidates (Triple Tap)
                    # Rules: 13-16 UTC, Vol 2-5x, RSI < 45, Count >= 3
                    sniper_indices = []
                    for i in day_indices:
                        if i < 50: continue
                        h = df_15m.index[i].hour
                        if not (13 <= h <= 16): continue
                        if df_15m['rsi'].values[i] >= 45: continue
                        vol = df_15m['volume'].values[i]
                        avg = df_15m['vol_ma50'].values[i] or 1
                        ratio = vol / avg
                        if 2.0 <= ratio <= 5.0:
                            sniper_indices.append(i)
                    
                    is_sniper_day = (len(sniper_indices) >= 3)
                    
                    # --- AYAŞ TÜNELİ (VİZE) KONTROLÜ ---
                    # Eğer mode 'sniper' ise veya --sealed (yoksa bile ben buraya mühürlü mod ekliyorum) 
                    # Ayaş tüneli felsefesi: Koine özel Altın Anahtar (Golden Key) var mı? 
                    # Ve o günkü profili (Daily DNA) vize alıyor mu?
                    ayas_vize = True
                    is_ayas_mode = getattr(args, 'sealed', False) or args.mode == 'sniper'
                    
                    if is_ayas_mode:
                        try:
                            key_path = f"{GOLDEN_KEYS_DIR}/{symbol}_key.json"
                            if not os.path.exists(key_path):
                                ayas_vize = False
                            else:
                                with open(key_path, "r") as fk:
                                    g_keys = set(json.load(fk).get('golden_dna_list', []))
                                
                                # Daily Profile (DNA) calculation at Start of Day
                                d_profile = get_profile_simple(current_utc, df_1w, df_1h, df_1d, df_4h)
                                if d_profile not in g_keys:
                                    ayas_vize = False
                                
                                # Tagging
                                current_day_tags = []
                                if d_profile in g_keys:
                                    current_day_tags.append("[🛡️ İMZA]")
                                if d_profile in GLOBAL_ELITE_DNAS:
                                    current_day_tags.append("[🌍 KÜRESEL]")
                                
                                ayas_tag_str = " ".join(current_day_tags)
                        except:
                            ayas_vize = False
                    
                    if is_ayas_mode and not ayas_vize:
                        current += pd.Timedelta(days=1); continue # Tünelden geçemedi
                    
                    # 2. Get F100 Sinyalleri
                    f100_indices = []
                    for i in day_indices:
                        if i < 21: continue
                        if df_15m['rsi'].values[i-1] <= 70 and df_15m['rsi'].values[i] > 70:
                            f100_indices.append(i)
                    
                    # 2b. Get Ignitor Sinyalleri (Volume Ignition)
                    ignitor_indices = []
                    ignitor_shifts = {} # Map t0_idx to entry_offset (0 or 2)
                    is_ignitor_mode = getattr(args, 'ignitor', False) or args.mode == 'ignitor'
                    if is_ignitor_mode:
                        is_pure = getattr(args, 'tier_only', False)
                        for i in day_indices:
                            if i < 50: continue
                            passed, msg, shift = IGNITOR.analyze_sequence(df_15m, i, symbol, pure_mode=is_pure, df_1h=df_1h, btc_df_15m=btc_df_15m, d_atr=d_atr)
                            if passed:
                                ignitor_indices.append(i)
                                ignitor_shifts[i] = shift

                    # 3. Combine/Select Based on Mode
                    target_indices = []
                    strat_name_map = {}
                    
                    if is_ignitor_mode:
                        target_indices = ignitor_indices
                        for idx in ignitor_indices:
                            strat_name_map[idx] = "🔥 IGNITOR"
                    elif args.mode == 'sniper':
                        if is_sniper_day:
                            target_indices = sniper_indices
                            for idx in sniper_indices:
                                strat_name_map[idx] = "SNIPER 🎯"
                        else:
                            target_indices = []
                    else:
                        # Standard Mode
                        target_indices = f100_indices
                        for idx in f100_indices:
                            prefix = ayas_tag_str + " " if is_ayas_mode and ayas_tag_str else ""
                            if is_sniper_day and idx in sniper_indices:
                                strat_name_map[idx] = f"{prefix}F100 🎯"
                            else:
                                strat_name_map[idx] = f"{prefix}F100"
                    
                    trigger_events = []
                    for i in target_indices:
                        # 4. ENTRY SHIFT for Ignitor
                        entry_idx = i + ignitor_shifts.get(i, 0)
                        if entry_idx >= len(df_15m): continue
                        
                        # 5. Calculate Peak and HOLY GRAIL EXIT (HGE)
                        search_limit = min(entry_idx + 50, len(df_15m))
                        entry_p = df_15m['close'].values[entry_idx]
                        peak_p = entry_p
                        
                        # Trailing Exit Simulation for "Holy Grail"
                        exit_p = df_15m['close'].values[search_limit-1] 
                        stop_p = df_15m['low'].values[i] # Initial Stop at T0 Low

                        peak_p = max(entry_p, df_15m['high'].values[entry_idx])
                        peak_dist = 0
                        for k in range(entry_idx + 1, search_limit):
                            curr_h = df_15m['high'].values[k]
                            curr_c = df_15m['close'].values[k]
                            if curr_h > peak_p: 
                                peak_p = curr_h
                                peak_dist = k - entry_idx
                            if curr_c < (peak_p * 0.975) or curr_c < stop_p:
                                exit_p = curr_c
                                break
                        
                        max_ret = (peak_p / entry_p) - 1
                        hge_ret = (exit_p / entry_p) - 1
                        is_limited = (search_limit - i < 49)
                        
                        # Indicators logic
                        trig_time = df_15m.index[i]
                        
                        cutoff_4h = trig_time - pd.Timedelta(hours=4)
                        last_4h = df_4h[df_4h.index <= cutoff_4h]
                        t4 = "🟢" if not last_4h.empty and last_4h.iloc[-1]['close'] > last_4h.iloc[-1]['ema21'] else "🔴"
                        
                        cutoff_1h = trig_time - pd.Timedelta(hours=1)
                        last_1h = df_1h[df_1h.index <= cutoff_1h]
                        t1 = "🟢" if not last_1h.empty and last_1h.iloc[-1]['close'] > last_1h.iloc[-1]['ema21'] else "🔴"
                        m_tr = f"{t4}{t1}"
                        
                        h_t, h_p = df_15m['macd_hist'].values[i], df_15m['macd_hist'].values[i-1]
                        mac_c = "🟢" if h_t > 0 and h_t > h_p else "🟣" if h_t > 0 else "🔴" if h_t < h_p else "🟡"
                        
                        v_idx = min(10.0, (df_15m['tr'].values[i] / (df_15m['atr100'].values[i] or 0.001)) * 3.33)
                        v_dyn = min(10.0, (df_15m['tr'].values[i] / (df_15m['atr21'].values[i] or 0.001)) * 3.33)
                        
                        past_vidx = []
                        for k in range(1, 4):
                            p_tr = df_15m['tr'].values[i-k]
                            p_atr = df_15m['atr100'].values[i-k] or 0.001
                            past_vidx.append((p_tr/p_atr)*3.33)
                        avg_past = np.mean(past_vidx) if past_vidx else 0.001
                        v_mom = (v_idx / avg_past) if avg_past > 0 else 0
                        
                        body = abs(df_15m['close'].values[i] - df_15m['open'].values[i])
                        rng = df_15m['tr'].values[i] or 0.001
                        v_eff = (body / rng) * 10.0
                        
                        v_hyb = min(15.0, v_idx * (df_15m['rsi'].values[i]/50.0))
                        
                        is_trigger = True 
                        if is_trigger:
                            strat_signal = strat_name_map.get(i, "F100")
                            
                            next_pct = None
                            if i + peak_dist + 1 < len(df_15m):
                                nc = df_15m['close'].values[i + peak_dist + 1]
                                next_pct = ((nc - peak_p)/peak_p)*100
                            
                            nn_pct = None
                            if i + peak_dist + 2 < len(df_15m):
                                nnc = df_15m['close'].values[i + peak_dist + 2]
                                nn_pct = ((nnc - df_15m['close'].values[i + peak_dist + 1])/df_15m['close'].values[i + peak_dist + 1])*100
                                
                            candle_open = df_15m['open'].values[i]
                            trig_pct = ((df_15m['close'].values[i] - candle_open)/candle_open)*100
                            
                            val_20 = df_15m['rsi_rib_20'].values[i]
                            val_55 = df_15m['rsi_rib_55'].values[i]
                            ribbon_above = val_20 > val_55
                            
                            if val_20 > val_55:
                                src_icon = "🟢"
                                src_heart = "💚"
                                curr_v = val_20
                                prev_v = df_15m['rsi_rib_20'].values[i-1]
                            else:
                                src_icon = "🔴"
                                src_heart = "❤️"
                                curr_v = val_55
                                prev_v = df_15m['rsi_rib_55'].values[i-1]
                                
                            slope = (curr_v - prev_v) / 2.0
                            angle_deg = math.degrees(math.atan(slope))
                            ang_score = angle_deg / 4.5
                            if abs(ang_score) > 5.0: ang_e = f"<font color='{'green' if ang_score>=0 else 'red'}'>**{ang_score:+.1f}**</font>"
                            else: ang_e = f"<font color='{'green' if ang_score>=0 else 'red'}'>{ang_score:+.1f}</font>"

                            if curr_v < 30: pos_icon = "⚫"
                            elif curr_v < 50: pos_icon = "🔴"
                            elif curr_v < 60: pos_icon = "🟡"
                            elif curr_v < 70: pos_icon = "🟢"
                            else: pos_icon = "🟠"
                            
                            rsi_ema_now = df_15m['rsi_ema'].values[i]
                            rsi_ema_prev = df_15m['rsi_ema'].values[i-1]
                            rsi_angle = math.degrees(math.atan(rsi_ema_now - rsi_ema_prev))
                            
                            p_49_price = df_15m['close'].values[min(len(df_15m)-1, entry_idx + 49)]
                            p_49_gain = ((p_49_price / entry_p) - 1) * 100

                            # Phase 8: DIAMOND INCINERATOR (Noise Cancellation) - DISABLED for Transparency
                            # Ali Beyim wants the TRUTH. No skipping low-yield or losing signals.
                            # is_pure = getattr(args, 'tier_only', False)
                            # if is_ignitor_mode and is_pure:
                            #     if max_ret < 0.10:
                            #          continue

                            trigger_events.append({
                                'time': df_15m.index[entry_idx].strftime("%H:%M"),
                                'strat': strat_signal, 'mac_color': mac_c,
                                'peak': max_ret * 100,
                                'exit_ret': hge_ret,
                                'peak_dist': peak_dist, 'is_limited': is_limited,
                                'm_tr': m_tr, 'next_pct': next_pct, 'next_next_pct': nn_pct,
                                'trig_pct': trig_pct, 'daily_atr': d_atr,
                                'pos_icon': pos_icon, 'ang_emoji': ang_e, 'val_icon': src_heart,
                                'v_index': v_idx, 'v_dyn': v_dyn, 'v_mom': v_mom, 
                                'v_eff': v_eff, 'v_hyb': v_hyb, 'atr_adj': (df_15m['tr'].values[i]/df_15m['close'].values[i])*100,
                                'rsi_angle': rsi_angle,
                                # Portakal Fields
                                'd_atr': d_atr, 'd_adx': d_adx, 'trend_score': (1 if t4=="🟢" else 0) + (1 if t1=="🟢" else 0),
                                'ribbon_above': ribbon_above, 'ang_score': ang_score, 'rsi': df_15m['rsi'].values[i],
                                'p_49': p_49_gain, 'trig_p': trig_pct
                            })
                    
                    if trigger_events:
                        all_passed_days.append({
                            'date': current, 'symbol': symbol,
                            'peak': ((max_h/open_p)-1)*100, 'ret': ((close_p/open_p)-1)*100,
                            'triggers': trigger_events,
                            'prio': min([{"🟢":1,"🟣":2,"🟡":3,"🔴":4}.get(t['mac_color'],5) for t in trigger_events])
                        })
                        processed_pairs.add(pair_key)
                        
                except Exception as e:
                    pass
                current += pd.Timedelta(days=1)
        except: continue

    # --- PHASE 2: SYMBIOTIC INTELLIGENCE (Cross-Coin Correlation) ---
    # Collect all ignitor signals by timestamp
    ignitor_map = {} # time -> count
    for d in all_passed_days:
        for t in d['triggers']:
            if "IGNITOR" in t['strat']:
                full_time = f"{d['date'].strftime('%Y-%m-%d')} {t['time']}"
                ignitor_map[full_time] = ignitor_map.get(full_time, 0) + 1
    
    # Tag symbiotic events (If >= 3 coins trigger same 15m bar)
    for d in all_passed_days:
        for t in d['triggers']:
            full_time = f"{d['date'].strftime('%Y-%m-%d')} {t['time']}"
            if ignitor_map.get(full_time, 0) >= 3:
                t['strat'] = "[🤝 SEMBİYOTİK] " + t['strat']

    # FILTERING (Portakal)
    if PORTAKAL_AVAILABLE:
        flat_triggers = []
        for d_idx, d_data in enumerate(all_passed_days):
            for t_idx, trig in enumerate(d_data['triggers']):
                t_cpy = trig.copy()
                t_cpy['__day_idx'] = d_idx
                t_cpy['__trig_idx'] = t_idx
                flat_triggers.append(t_cpy)
        
        if flat_triggers:
            df_triggers = pd.DataFrame(flat_triggers)
            df_filt = apply_portakal_sikacagi(df_triggers, verbose=False)
            survivors = set(zip(df_filt['__day_idx'], df_filt['__trig_idx']))
            
            new_days = []
            for d_idx, d_data in enumerate(all_passed_days):
                new_trigs = [t for i, t in enumerate(d_data['triggers']) if (d_idx, i) in survivors]
                if new_trigs:
                    d_data['triggers'] = new_trigs
                    new_days.append(d_data)
            all_passed_days = new_days

    # OUTPUT
    df = pd.DataFrame(all_passed_days)
    if df.empty:
        print("No matches found.")
        return

    df.sort_values(by=['date', 'prio', 'peak'], ascending=[True, True, False], inplace=True)
    
    hdrs = ["NO", "SYM", "MAX", "EXIT", "TIME", "SIG", "TREND", "POS", "ANG", "R-Ang", "VAL", "P", "TIER", "P-49", "BAR", "NEXT", "N-1", "CGS", "ADX", "ATR%", "Vrsi", "VBoy", "V100", "V21", "V-Mom"]
    
    for date in sorted(df['date'].unique()):
        day_df = df[df['date'] == date]
        rows = []
        idx_counter = 1
        for _, r in day_df.iterrows():
            c_rows = []
            for i, t in enumerate(r['triggers']):
                row = format_row_data(r, t, i, idx_counter)
                c_rows.append(row)
            if c_rows:
                rows.extend(c_rows)
                idx_counter += 1
        
        print(f"\n## 📅 {pd.Timestamp(date).strftime('%d %B %Y')} (Count: {len(rows)})")
        write_aligned_table_stdout(rows, hdrs)

if __name__ == "__main__":
    main()
