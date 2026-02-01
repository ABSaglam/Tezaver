#!/usr/bin/env python3
"""
AYAŞ TÜNELİ-2 SCANNER (v2.3 - DNA MÜJDE ENTEGRASYONU - FIXED VALIDATION)
========================================================================
- List-2 (Olacaklar) için özel scanner.
- Blacklist entegrasyonu (52 Zehirli Koin).
- DNA Müjde Kuralları (Koin Bazlı Filtreleme).
- FIXED: DNA Logic matches Universal Key Generator (Turkish Strings).
"""

import pandas as pd
import numpy as np
import os
import json
import math
from datetime import datetime

# CONFIG
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
KEYS_DIR_NEW = "/Users/alisaglam/TezaverMac/data/golden_keys_list2"
KEYS_DIR_OLD = "/Users/alisaglam/TezaverMac/data/golden_keys_v2"
BLACKLIST_FILE = "/Users/alisaglam/TezaverMac/data/blacklist_list2.json"
DNA_RULES_FILE = "/Users/alisaglam/TezaverMac/data/dna_mujde_rules.json"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/SARI_LISTE_FINAL.md"

# Tarih
END_DATE = pd.Timestamp.now().normalize()
START_DATE = END_DATE - pd.Timedelta(days=100) 

def load_clean(path):
    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df = df[~df.index.duplicated(keep='last')]
    return df.sort_index()

def load_blacklist():
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, "r") as f:
                bl = json.load(f)
                print(f"✅ Blacklist yüklendi: {len(bl)} koin.")
                return set(bl)
        except: return set()
    return set()

def load_dna_rules():
    if os.path.exists(DNA_RULES_FILE):
        try:
            with open(DNA_RULES_FILE, "r") as f:
                rules = json.load(f)
                print(f"✅ DNA Müjde Kuralları yüklendi: {len(rules)} koin.")
                return rules
        except: return {}
    return {}

def get_angle(series, period=5):
    if len(series) < period: return 0.0
    y = series.tail(period).values
    x = np.arange(period)
    slope, _ = np.polyfit(x, y, 1)
    return math.degrees(math.atan(slope))

def get_dna_profile(day, df_w, df_h1, df_d, df_h4, symbol=None):
    """
    CORRECTED DNA LOGIC (Matches ayas2_faz1_historical_scan.py)
    """
    try:
        daily_integrity_cutoff = day.normalize()
        
        # --- IRON WALL FIX ---
        h1_cutoff = day - pd.Timedelta(hours=1)
        sub_h1_24 = df_h1[df_h1.index <= h1_cutoff].tail(24)
        
        h4_cutoff = day - pd.Timedelta(hours=4)
        sub_h4 = df_h4[df_h4.index <= h4_cutoff].tail(42)
        
        sub_d = df_d[df_d.index < daily_integrity_cutoff].tail(100)
        
        weekly_cutoff = day - pd.Timedelta(days=7)
        sub_w = df_w[df_w.index < weekly_cutoff].tail(52)
        
        if sub_w.empty or sub_d.empty or sub_h1_24.empty:
            return "neutral"
        
        # Haftalık RSI (Faz)
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
        
        # 1H EMA sıkışması (Accumulasyon)
        if len(sub_h1_24) >= 10:
            ema9 = sub_h1_24['close'].ewm(span=9, adjust=False).mean()
            ema21 = sub_h1_24['close'].ewm(span=21, adjust=False).mean()
            squeeze_pct = abs(ema9.iloc[-1] - ema21.iloc[-1]) / sub_h1_24['close'].iloc[-1] * 100
            if squeeze_pct <= 0.3: acc = "tight_squeeze"
            elif squeeze_pct <= 0.8: acc = "micro_squeeze"
            elif squeeze_pct <= 1.5: acc = "normal_gap"
            else: acc = "expanded_gap"
        else:
            acc = "no_data"
        
        # Harmoni (çoklu TF trend uyumu)
        if len(sub_h1_24) >= 21:
            ema21_h = sub_h1_24['close'].ewm(span=21, adjust=False).mean()
            h1_trend = sub_h1_24['close'].iloc[-1] > ema21_h.iloc[-1]
        else:
            h1_trend = True
        
        if len(sub_h4) >= 21:
            ema21_4h = sub_h4['close'].ewm(span=21, adjust=False).mean()
            h4_trend = sub_h4['close'].iloc[-1] > ema21_4h.iloc[-1]
        else:
            h4_trend = True
        
        if len(sub_d) >= 21:
            ema21_d = sub_d['close'].ewm(span=21, adjust=False).mean()
            d_trend = sub_d['close'].iloc[-1] > ema21_d.iloc[-1]
        else:
            d_trend = True
        
        trend_count = sum([h1_trend, h4_trend, d_trend])
        if trend_count == 3: harm = "harmony_L3"
        elif trend_count == 2: harm = "harmony_L2"
        elif trend_count == 1: harm = "harmony_L1"
        else: harm = "discord"
        
        # Ritim (hacim)
        if len(sub_d) >= 21:
            vol_ratio = sub_d['volume'].iloc[-1] / sub_d['volume'].rolling(21).mean().iloc[-1]
            if vol_ratio >= 2.5: ritim = "volume_explosion"
            elif vol_ratio >= 1.5: ritim = "volume_surge"
            elif vol_ratio >= 0.8: ritim = "volume_normal"
            else: ritim = "volume_dry"
        else:
            ritim = "no_data"
        
        # Bağlam (yıllık tepeye mesafe)
        if len(sub_d) >= 50:
            max_52w = sub_d['high'].tail(50).max()
            current_p = sub_d['close'].iloc[-1]
            dist = ((current_p / max_52w) - 1) * 100
            if dist >= -10: ctx = "near_ath"
            elif dist >= -30: ctx = "mid_range"
            elif dist >= -50: ctx = "discounted"
            else: ctx = "deep_discount"
        else:
            ctx = "no_data"
        
        # Enerji (hacim trendi)
        if len(sub_d) >= 10:
            vol_5 = sub_d['volume'].tail(5).mean()
            vol_10 = sub_d['volume'].tail(10).mean()
            if vol_5 > vol_10 * 1.2: enerji = "rising_energy"
            elif vol_5 < vol_10 * 0.8: enerji = "fading_energy"
            else: enerji = "stable_energy"
        else:
            enerji = "no_data"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except Exception as e:
        return "neutral"

def run_scanner():
    print("AYAŞ TÜNELİ-2: DNA MÜJDE SCANNER (FIXED)")
    
    # Files Load
    try:
        old_golden_coins = set()
        if os.path.exists(KEYS_DIR_OLD):
            for f in os.listdir(KEYS_DIR_OLD):
                if f.endswith("_key.json"):
                    old_golden_coins.add(f.replace("_key.json", ""))
    except: pass
                
    universal_map = {}
    if os.path.exists(KEYS_DIR_NEW):
        try:
            for f_name in os.listdir(KEYS_DIR_NEW):
                if f_name.endswith("_key.json"):
                    symbol = f_name.replace("_key.json", "")
                    if symbol not in old_golden_coins:
                        with open(os.path.join(KEYS_DIR_NEW, f_name), "r") as f:
                            data = json.load(f)
                            universal_map[symbol] = set(data['golden_dna_list'])
        except: pass
    
    blacklist_set = load_blacklist()
    dna_rules = load_dna_rules()
    
    print(f"DEBUG: Yeni Key: {len(universal_map)}")
    
    try:
        symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    except:
        print("HATA: Coin cells dizini okunamadı.")
        return
    
    report_rows = []
    processed = 0

    for idx_scan, symbol in enumerate(symbols):
        if symbol not in universal_map: continue
        
        if symbol in blacklist_set:
            if idx_scan % 100 == 0: print(f"🚫 {symbol} (Blacklist)")
            continue
            
        # Get DNA Rules
        rules = dna_rules.get(symbol, {})
        rule_trend = rules.get("trend_filter", False)
        rule_vol = rules.get("vol_filter", False)
        rule_adx = rules.get("adx_filter", False)
        
        try:
            df_15m = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet")
            
            # Indicators
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
                
            # Trigger
            rsi_ema_vals = df_15m['rsi_ema'].values
            all_above = np.ones(len(df_15m), dtype=bool)
            for col in rsi_ribbon_cols:
                all_above &= (rsi_ema_vals > df_15m[col].values)
            
            prev_not_above = ~np.roll(all_above, 1)
            prev_not_above[0] = True
            triggers = np.where(all_above & prev_not_above)[0]
            
            # Lazy Load Vars
            df_1h = None; df_4h = None; df_1d = None; df_1w = None
            
            for t_idx in triggers:
                trig_time = df_15m.index[t_idx]
                if trig_time < START_DATE or trig_time > END_DATE: continue
                
                # Check Next 21 Bars exists
                if t_idx + 21 >= len(df_15m): continue
                
                # Load TFs if needed
                if df_1h is None:
                    df_1h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
                    df_4h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
                    df_1d = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
                    df_1w = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")
                    
                    # ADX / ATR Pre-calc
                    d_tr = np.maximum(df_1d['high'] - df_1d['low'], np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), abs(df_1d['low'] - df_1d['close'].shift(1))))
                    df_1d['atr14'] = d_tr.rolling(14).mean()
                    
                    plus_dm = df_1d['high'].diff()
                    minus_dm = -df_1d['low'].diff()
                    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
                    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
                    tr14_sum = d_tr.rolling(14).sum()
                    plus_di = 100 * (plus_dm.rolling(14).sum() / tr14_sum)
                    minus_di = 100 * (minus_dm.rolling(14).sum() / tr14_sum)
                    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.001)
                    df_1d['adx14'] = dx.rolling(14).mean()
                
                # DNA Check
                dna = get_dna_profile(trig_time, df_1w, df_1h, df_1d, df_4h, symbol=symbol)
                if dna == "neutral": continue
                if dna not in universal_map[symbol]: continue
                
                # --- APPLY DNA MUJDE RULES ---
                if rule_trend or rule_vol or rule_adx:
                    # Calculate Metrics (IRON WALL FIX: Strictly Previous Closed Candles)
                    
                    # Trend H1 (Wait until candle closes)
                    # If triggers at 14:15, H1 candle 13:00-14:00 is relevant? 
                    # Actually standard logic: Use values KNOWN at trigger time.
                    # At 14:15, the 14:00 candle is OPEN. The 13:00 candle is CLOSED.
                    # Standard DNA uses 'h1_cutoff = day - 1h'.
                    
                    h1_cutoff = trig_time - pd.Timedelta(hours=1)
                    h1_row = df_1h[df_1h.index <= h1_cutoff].tail(1)
                    if len(h1_row) > 0:
                        e21_h = h1_row['close'].ewm(span=21, adjust=False).mean()
                        t1_val = "Bull" if h1_row['close'].iloc[-1] > e21_h.iloc[-1] else "Bear"
                    else: t1_val = "Bear"
                    
                    # Trend H4 (Wait until candle closes)
                    h4_cutoff = trig_time - pd.Timedelta(hours=4)
                    h4_row = df_4h[df_4h.index <= h4_cutoff].tail(1)
                    if len(h4_row) > 0:
                        e21_4h = h4_row['close'].ewm(span=21, adjust=False).mean()
                        t4_val = "Bull" if h4_row['close'].iloc[-1] > e21_4h.iloc[-1] else "Bear"
                    else: t4_val = "Bear"
                    
                    # Vol/ADX (Daily - Yesterday Close)
                    d_cutoff = trig_time.normalize() - pd.Timedelta(days=1)
                    d_row = df_1d[df_1d.index <= d_cutoff].tail(1)
                    
                    if len(d_row) > 0:
                        # For Vol MA, verify lookback window relative to d_cutoff
                        vol_vals = df_1d['volume'][df_1d.index < d_cutoff].tail(20) # 20 days prior to yesterday
                        if len(vol_vals) > 0:
                            vol_ma = vol_vals.mean()
                            v_mom_val = d_row['volume'].iloc[-1] / vol_ma if vol_ma > 0 else 0
                        else: v_mom_val = 0
                        adx_val = d_row['adx14'].iloc[-1]
                    else: v_mom_val=0; adx_val=0
                    
                    # Check Rules
                    if rule_trend and (t1_val == "Bear" and t4_val == "Bear"): continue
                    if rule_vol and v_mom_val <= 1.0: continue
                    if rule_adx and adx_val <= 20: continue
                
                # --- REPORT GEN ---
                future_slice = df_15m['high'].iloc[t_idx+1 : t_idx+22]
                curr_close = df_15m['close'].iloc[t_idx]
                max_gain = ((future_slice.max() - curr_close) / curr_close) * 100
                
                if max_gain >= 30: tier = "💎"
                elif max_gain >= 20: tier = "🥇"
                elif max_gain >= 10: tier = "🥈"
                elif max_gain >= 5: tier = "🥉"
                else: tier = "-"
                
                max_str = f"**{max_gain:.1f}%**"
                if max_gain > 5: max_str = f"<font color='green'>{max_str}</font>"
                else: max_str = f"<font color='red'>{max_str}</font>"
                
                trig_str = f"{trig_time.strftime('%Y-%m-%d %H:%M')}"
                
                # Extra Stats for Columns
                # Need: TREND (Emoji), ADX, V-Mom
                # Recalculate if not skipped
                # We need Trend Emoji
                if 't1_val' not in locals():
                     h1_row = df_1h[df_1h.index <= trig_time].tail(1)
                     t1_val = "Bull"
                     # ... simplified for display ...
                
                trend_display = "🟢🟢" # Default visual
                
                # ADX/V-Mom for display
                if 'adx_val' not in locals(): adx_val = 0
                if 'v_mom_val' not in locals(): v_mom_val = 0
                
                adx_str = f"**{int(adx_val)}**"
                if adx_val > 25: adx_str = f"<font color='green'>{adx_str}</font>"
                
                row = f"| {len(report_rows)+1} | {symbol} | {max_str} | 0% | {trig_str} | RSI-EMA | - | {trend_display} | 🟡 | 0 | 0° | - | - | {tier} | - | - | - | - | - | {adx_str} | 0 | 0 | 0 | 0 | 0 | {v_mom_val:.1f}x |"
                report_rows.append(row)
                
        except Exception as e:
            continue
            
        processed += 1
        if processed % 50 == 0: print(f"  Processed: {processed}/{len(symbols)}")

    # Write Report
    with open(OUTPUT_FILE, "w") as f:
        f.write("# SARI LİSTE (List-2 Optimized w/ DNA Mujde)\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write("| NO | SYM | MAX | CLOSE | TIME | SIG | CVT | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-21 | BAR | NEXT | N-1 | CGS | ADX | ATR% | Vrsi | VBoy | V100 | V21 | V-Mom |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in report_rows:
            f.write(r + "\n")
            
    print(f"✅ Rapor OLUŞTURULDU: {OUTPUT_FILE}")
    print(f"Toplam Sinyal: {len(report_rows)}")

if __name__ == "__main__":
    run_scanner()
