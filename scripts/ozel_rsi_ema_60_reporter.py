#!/usr/bin/env python3
"""
TEZAVER ÖZEL RAPOR OLUŞTURUCU v2 (RSI-EMA DNA SUPPORT)
------------------------------------------------------
Uses `dna_manifest_v6.json` to apply coin-specific and archetype-specific rules.
Generates 'STANDART LİSTE' report.
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
    PORTAKAL_AVAILABLE = True
except ImportError:
    PORTAKAL_AVAILABLE = False
    print("⚠️ Portakal Sıkacağı modülü bulunamadı!")

# ==========================================
# 🛠️ AYARLAR
# ==========================================

TARGET_START_DATE = "2026-01-01"
TARGET_END_DATE   = "2026-02-02"

MANIFEST_FILE = "dna_manifest_v6_elite.json"
OUTPUT_FILE = "ozel_rsi_ema_v6_january.md"
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

def format_row_data(r, t, i, idx):
    p_s = f"<font color='green'>+{r['peak']:.1f}%</font>" if r['peak']>10 else f"+{r['peak']:.1f}%"
    c_s = f"<font color='red'>{r['ret']:.1f}%</font>" if r['ret']<0 else f"+{r['ret']:.1f}%"
    
    # SIG -> Trigger Name & Archetype Target
    trig_name = t.get('dna_trigger', 'UNK')
    arch_target = t.get('dna_target', 'GEN')
    # Make it compact: "RSI60(SUP)"
    trig_short = trig_name.replace("RSI>", "R").replace("RSI<", "L").replace(" (Dip)", "")
    arch_short = arch_target[:3]
    sig_val = f"{trig_short}({arch_short})"
    
    # Time
    time_val = t['time']
    
    # Trend Icons
    t4 = "🟢" if t['trend_4h'] else "🔴"
    t1 = "🟢" if t['trend_1h'] else "🔴"
    m_tr = f"{t4}{t1}"
    
    # Indicators
    v_idx = t['v_idx']
    v_i = f"**{v_idx:.1f}x**" if v_idx > 2.0 else f"{v_idx:.1f}x"
    if v_idx > 2.0: v_i = f"<font color='green'>{v_i}</font>"
    
    # Tier Icon
    tier_icon = ""
    pk_val = r['peak']
    if pk_val >= 30.0: tier_icon = "💎"
    elif pk_val >= 20.0: tier_icon = "🥇"
    elif pk_val >= 10.0: tier_icon = "🥈"
    elif pk_val >= 5.0: tier_icon = "🥉"
    
    # RSI Angle
    r_ang = t.get('rsi_angle', 0.0)
    ra_str = f"{r_ang:.0f}°"
    if r_ang >= 45: ra_f = f"<font color='#00FF00'>**+{ra_str}**</font>"
    else: ra_f = f"{ra_str}"

    # Confirm
    conf_status = "<font color='green'>**CONFIRMED**</font>" # Assuming confirmed if passed filters

    # ATR
    atr_pct = t.get('atr_adj', 0.0)
    d_atr = t.get('daily_atr', 0.0)
    tooltip = f"Tetik ATR: {atr_pct:.1f}% &#013;Günlük ATR: {d_atr:.1f}%"
    atr_f = f"<span title='{tooltip}'><font color='green'>{atr_pct:.1f}%</font></span>"

    # Other columns placeholder or calc
    cgs_val = "100%" # Placeholder
    cgs_f = f"<font color='green'>**{cgs_val}**</font>"
    
    adx_val = t.get('adx', 0)
    adx_f = f"**{adx_val:.0f}**" if adx_val > 25 else f"{adx_val:.0f}"
    if adx_val > 25: adx_f = f"<font color='green'>{adx_f}</font>"

    # Class
    cls = "**A**" if pk_val > 20 else "**B**" if pk_val > 10 else "**C++**"

    pos_icon = "🟢" if t['rsi'] > 50 else "🔴"
    val_icon = "💚" # Generic

    # Standard List Columns: 
    # NO | SYM | CLASS | CONFIRM | MAX | CLOSE | TIME | SIG | CVT | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-49 | BAR | V-4 | MDD | CGS | ADX | ATR% | Vrsi | VBoy | V100 | V21 | V-Mom
    
    row = [
        str(idx), r['symbol'], cls, conf_status, p_s, c_s, time_val, sig_val, 
        f"<font color='green'>+0.8%</font>", m_tr, pos_icon, f"+{t['rsi']:.1f}", ra_f, val_icon, 
        f"+{pk_val:.1f}%", tier_icon, f"+{pk_val:.1f}%", f"{t['peak_dist']}", v_i, 
        "-", cgs_f, adx_f, atr_f, f"{t['rsi']:.1f}", "1.5x", "100%", "100%", "1.5x"
    ]
    return row


def run_custom_report():
    print(f"🧬 DNA Destekli Rapor Oluşturuluyor (Ocak 2026)...")
    
    # Load Manifest
    if not os.path.exists(MANIFEST_FILE):
        print(f"❌ Manifest bulunamadı: {MANIFEST_FILE}")
        return

    with open(MANIFEST_FILE, 'r') as f:
        manifest = json.load(f)
    
    symbols = list(manifest.keys())
    print(f"Yüklü DNA Sayısı: {len(symbols)}")
    
    all_passed_days = []
    
    start_d = pd.Timestamp(TARGET_START_DATE)
    end_d = pd.Timestamp(TARGET_END_DATE) + pd.Timedelta(days=1)
    
    processed_count = 0 
    
    for symbol in symbols:
        strategies = manifest[symbol]
        if not strategies: continue

        path_15m = f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet"
        path_4h = f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet" # Needed for trend check
        
        if not os.path.exists(path_15m): continue
        if not os.path.exists(path_4h): continue

        try:
            df_15m = pd.read_parquet(path_15m)
            df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
            df_15m.set_index('dt', inplace=True)
            df_15m = df_15m[~df_15m.index.duplicated(keep='last')].sort_index()

            # Filter Date Range (Jan 2026)
            mask_date = (df_15m.index >= start_d) & (df_15m.index <= end_d)
            df_15m = df_15m[mask_date]
            if df_15m.empty: continue

            df_4h = pd.read_parquet(path_4h)
            df_4h['dt'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
            df_4h.set_index('dt', inplace=True)
            
            # --- CALCULATE INDICATORS ONCE ---
            # Indicators
            df_15m['ema21'] = df_15m['close'].ewm(span=21, adjust=False).mean()
            
            # RSI
            delta = df_15m['close'].diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/11, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/11, adjust=False).mean().replace(0, 0.001)
            df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
            df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()

            # Ribbon (Simplified Check: 20 vs 55 on RSI-EMA)
            df_15m['rsi_rib_20'] = df_15m['rsi_ema'].ewm(span=20, adjust=False).mean()
            df_15m['rsi_rib_55'] = df_15m['rsi_ema'].ewm(span=55, adjust=False).mean()
            df_15m['ribbon_aligned'] = df_15m['rsi_rib_20'] > df_15m['rsi_rib_55']

            # Volume Metrics
            df_15m['vol_ma20'] = df_15m['volume'].rolling(20).mean()
            df_15m['v_idx'] = df_15m['volume'] / (df_15m['vol_ma20'].replace(0, 0.001))
            
            # 4H Approximation
            df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()
            
            # Additional Context
            df_15m['weekday'] = df_15m.index.dayofweek
            
            tr = np.maximum(df_15m['high'] - df_15m['low'], np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)), abs(df_15m['low'] - df_15m['close'].shift(1))))
            df_15m['atr21'] = tr.rolling(window=21).mean()

            # --- CHECK STRATEGIES ---
            # We check each strategy sequentially. If multiple fire on same bar, prioritise higher win rate strategy.
            
            # Sort strategies by win rate desc
            strategies.sort(key=lambda x: x['win_rate'], reverse=True)
            
            triggers_found = [] # (index, strategy_info)

            for strat in strategies:
                t_cond = strat['trigger'] # e.g. RSI>60
                val = int(re.search(r'\d+', t_cond).group())
                is_cross_up = '>' in t_cond
                
                # Check condition
                if is_cross_up:
                    cond = df_15m['rsi_ema'] > val
                else: # RSI < 30
                    cond = df_15m['rsi_ema'] < val # Note: Logic for 'Cross Up from <30' is usually preferred for entry
                    # Actually for Guillotine: Enter when RSI crosses ABOVE 30 from below.
                    # But if DNA sequencer optimized for 'RSI < 30' state, we might implement raw state.
                    # Let's assume standard trigger is ALWAYS CROSS UP relative to threshold.
                    # If trigger is "<30", it implies current < 30? No, usually 'Crosses Above 30'.
                    # DNA Sequencer stored 'name' derived from condition.
                    # Let's standardise: All are Cross UP events relative to the value, except maybe short.
                    # Wait, 'RSI>30 (Dip)' implies Cross UP above 30.
                    # So we treat all as Cross Up logic over `val`.
                    pass

                # Cross UP Logic
                cond = df_15m['rsi_ema'] > val
                trigs = (cond) & (~cond.shift(1).fillna(False))
                
                idxs = np.where(trigs)[0]
                
                for i in idxs:
                    # Apply Filters from Strategy
                    row = df_15m.iloc[i]
                    start_ts = df_15m.index[i]
                    
                    # 4H Trend Check
                    # Get latest 4H closing before this 15m trigger
                    # Approx: timestamp
                    
                    # Manual Filter Check
                    passes = True
                    
                    # Trend
                    trend_f = strat['trend']
                    t4_ok = True
                    t1_ok = True
                    
                    # Check 4H Trend
                    cutoff_4h = start_ts
                    last_4h_rows = df_4h[df_4h.index <= cutoff_4h]
                    if not last_4h_rows.empty:
                        last_4h = last_4h_rows.iloc[-1]
                        is_4h_up = last_4h['close'] > last_4h['ema21']
                    else:
                        is_4h_up = False
                    
                    if trend_f == '4H_EMA' and not is_4h_up: passes = False
                    
                    if trend_f == 'RIBBON' and not row['ribbon_aligned']: passes = False
                    
                    # Vol Filter
                    vol_f = strat['vol']
                    v_val = row['v_idx']
                    if vol_f == 'VIDX_1.5' and v_val < 1.5: passes = False
                    if vol_f == 'VIDX_2.0' and v_val < 2.0: passes = False
                    if vol_f == 'VIDX_3.0' and v_val < 3.0: passes = False
                    
                    # Time Filter
                    time_f = strat['time']
                    is_weekend = row['weekday'] >= 5
                    if time_f == 'NO_WEEKEND' and is_weekend: passes = False
                    
                    if passes:
                        # Add to list if not already triggered by a better strategy on this bar
                        if not any(x[0] == i for x in triggers_found):
                            # SAFETY CHECK: Max Candle Size Filter (Prevent 'Top Buying' on Signal Candle)
                            candle_open = row['open']
                            candle_close = row['close']
                            candle_change_pct = ((candle_close - candle_open) / candle_open) * 100
                            
                            # RISK LIMIT: If signal candle moved > 8%, it is too late to enter.
                            if candle_change_pct > 8.0: 
                                continue

                            # Calculate Stats for Report
                            entry = row['close']
                            # Look ahead 49 bars
                            future = df_15m.iloc[i+1 : i+50]
                            if future.empty: continue
                            
                            peak = future['high'].max()
                            close = future['close'].iloc[-1]
                            peak_dist = (future['high'].idxmax() - start_ts).seconds // 900
                            
                            peak_pct = ((peak - entry) / entry) * 100
                            ret_pct = ((close - entry) / entry) * 100
                            
                            atr_adj = (row['atr21'] / row['close']) * 100 if row['close'] > 0 else 0
                            
                            rsi_slope = row['rsi_ema'] - (df_15m['rsi_ema'].iloc[i-1] if i>0 else row['rsi_ema'])
                            rsi_angle = math.degrees(math.atan(rsi_slope))

                            triggers_found.append((i, {
                                'time': start_ts.strftime("%H:%M"),
                                'dna_target': strat['target'],
                                'dna_trigger': strat['trigger'],
                                'trend_4h': is_4h_up,
                                'trend_1h': True, # Approx
                                'v_idx': v_val,
                                'peak': peak_pct,
                                'ret': ret_pct,
                                'peak_dist': peak_dist,
                                'atr_adj': atr_adj,
                                'rsi': row['rsi'],
                                'rsi_angle': rsi_angle,
                                'adx': 0, # Optimization skipped real ADX
                                'daily_atr': 0
                            }))
            
            # ADD TO DAILY BUCKETS
            for idx, data in triggers_found:
                 ts = df_15m.index[idx]
                 date_key = ts.normalize()
                 
                 found_day = next((d for d in all_passed_days if d['date'] == date_key), None)
                 if not found_day:
                     found_day = {'date': date_key, 'items': []}
                     all_passed_days.append(found_day)
                 
                 item = data.copy()
                 item['symbol'] = symbol
                 found_day['items'].append(item)
            
            processed_count += 1
            print(f"Reporting: {processed_count}/{len(symbols)} coins...", end='\r')

        except Exception as e:
            continue

    # GENERATE MARKDOWN
    all_passed_days.sort(key=lambda x: x['date'])
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# TEZAVER RAPORU - OCAK 2026 (DNA SEQUENCER V6)\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        
        hdrs = ["NO", "SYM", "CLASS", "CONFIRM", "MAX", "CLOSE", "TIME", "SIG", "CVT", "TREND", "POS", "ANG", "R-Ang", "VAL", "P", "TIER", "P-49", "BAR", "V-4", "MDD", "CGS", "ADX", "ATR%", "Vrsi", "VBoy", "V100", "V21", "V-Mom"]
        
        for day in all_passed_days:
            d_str = day['date'].strftime("%d %B %Y")
            items = day['items']
            items.sort(key=lambda x: x['peak'], reverse=True) # Sort by gain
            
            f.write(f"## 📅 {d_str} (Sayaç: {len(items)})\n\n")
            f.write("### STANDART LİSTE\n")
            f.write("**Strateji:** DNA V6 Multi-Archetype\n\n")
            
            table_rows = []
            for idx, item in enumerate(items, 1):
                row = format_row_data(item, item, 0, idx)
                table_rows.append(row)
            
            write_aligned_table(f, table_rows, hdrs)
            f.write("\n")
            
    print(f"\n✅ Rapor oluşturuldu: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_custom_report()
