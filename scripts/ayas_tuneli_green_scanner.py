#!/usr/bin/env python3
"""
YESİL LİSTE SCANNER (v3 FINAL OPTIMIZED)
========================================
- Hedef: Yeşil Liste V3 (Final)
- Mod: Optimized (With DNA Rules).
- Güvenlik: IRON WALL (Look-Ahead Bias Fix) her zaman aktif.
"""

import pandas as pd
import numpy as np
import os
import json
import math
from datetime import datetime

# CONFIG - GREEN MODE V3 (FINAL OPTIMIZED)
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
KEYS_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys_green_v3"
BLACKLIST_FILE = "" 
DNA_RULES_FILE = "/Users/alisaglam/TezaverMac/data/dna_mujde_rules_green_v3.json"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/YESIL_LISTE_V3_FINAL.md"

def load_clean(path):
    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df = df[~df.index.duplicated(keep='last')]
    return df.sort_index()

def load_blacklist(): return set()

def load_dna_rules():
    if os.path.exists(DNA_RULES_FILE):
        try:
            with open(DNA_RULES_FILE, "r") as f:
                rules = json.load(f)
                print(f"✅ DNA Müjde Kuralları yüklendi: {len(rules)} koin.")
                return rules
        except: return {}
    return {}

def get_dna_profile(day, df_w, df_h1, df_d, df_h4, symbol=None):
    """ CORRECTED DNA LOGIC (Matches Universal/Scan Runtime) """
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
        
        if sub_w.empty or sub_d.empty or sub_h1_24.empty: return "neutral"
        
        # Haftalık RSI
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
        
        # 1H EMA
        if len(sub_h1_24) >= 10:
            ema9 = sub_h1_24['close'].ewm(span=9, adjust=False).mean()
            ema21 = sub_h1_24['close'].ewm(span=21, adjust=False).mean()
            squeeze_pct = abs(ema9.iloc[-1] - ema21.iloc[-1]) / sub_h1_24['close'].iloc[-1] * 100
            if squeeze_pct <= 0.3: acc = "tight_squeeze"
            elif squeeze_pct <= 0.8: acc = "micro_squeeze"
            elif squeeze_pct <= 1.5: acc = "normal_gap"
            else: acc = "expanded_gap"
        else: acc = "no_data"
        
        # Harmoni
        if len(sub_h1_24) >= 21:
            ema21_h = sub_h1_24['close'].ewm(span=21, adjust=False).mean()
            h1_trend = sub_h1_24['close'].iloc[-1] > ema21_h.iloc[-1]
        else: h1_trend = True
        
        if len(sub_h4) >= 21:
            ema21_4h = sub_h4['close'].ewm(span=21, adjust=False).mean()
            h4_trend = sub_h4['close'].iloc[-1] > ema21_4h.iloc[-1]
        else: h4_trend = True
        
        if len(sub_d) >= 21:
            ema21_d = sub_d['close'].ewm(span=21, adjust=False).mean()
            d_trend = sub_d['close'].iloc[-1] > ema21_d.iloc[-1]
        else: d_trend = True
        
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
        
        # Context
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
    except Exception as e:
        return "neutral"

def run_scanner():
    print("YESİL LİSTE V3 (FINAL) TARAMASI BAŞLIYOR")
    
    # Tarih
    END_DATE = pd.Timestamp.now().normalize()
    START_DATE = END_DATE - pd.Timedelta(days=100) 
    
    green_map = {}
    if os.path.exists(KEYS_DIR):
        try:
            for f_name in os.listdir(KEYS_DIR):
                if f_name.endswith("_key.json"):
                    symbol = f_name.replace("_key.json", "")
                    with open(os.path.join(KEYS_DIR, f_name), "r") as f:
                        data = json.load(f)
                        if 'golden_dna_list' in data:
                            green_map[symbol] = set(data['golden_dna_list'])
        except: pass

    dna_rules = load_dna_rules()
    print(f"DEBUG: V3 Anahtar Sayısı: {len(green_map)}")
    
    if len(green_map) == 0:
        print("HATA: V3 anahtarları yüklenemedi!")
        return

    try:
        symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
        print(f"DEBUG: Bulunan Klasör Sayısı: {len(symbols)}")
    except Exception as e:
        print(f"HATA: Klasör okunamadı! {e}")
        return
    
    report_rows = []
    processed = 0

    for idx_scan, symbol in enumerate(symbols):
        if symbol not in green_map: continue
        
        rules = dna_rules.get(symbol, {})
        # Baseline report didn't have Trend data, so rule generator disabled trend filters.
        # But here we CAN calculate trend. However, to match simulation, we should respect the disabled flag.
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
            
            df_1h = None; df_4h = None; df_1d = None; df_1w = None
            
            for t_idx in triggers:
                trig_time = df_15m.index[t_idx]
                if trig_time < START_DATE or trig_time > END_DATE: continue
                if t_idx + 21 >= len(df_15m): continue
                
                # Check DNA
                if df_1h is None:
                    df_1h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
                    df_4h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
                    df_1d = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
                    df_1w = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")
                    # ADX calc
                    d_tr = np.maximum(df_1d['high'] - df_1d['low'], np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), abs(df_1d['low'] - df_1d['close'].shift(1))))
                    df_1d['atr14'] = d_tr.rolling(14).mean()
                    plus_dm = df_1d['high'].diff(); minus_dm = -df_1d['low'].diff()
                    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
                    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
                    tr14_sum = d_tr.rolling(14).sum()
                    dx = 100 * abs((100*(plus_dm.rolling(14).sum()/tr14_sum)) - (100*(minus_dm.rolling(14).sum()/tr14_sum))) / ((100*(plus_dm.rolling(14).sum()/tr14_sum)) + (100*(minus_dm.rolling(14).sum()/tr14_sum)) + 0.001)
                    df_1d['adx14'] = dx.rolling(14).mean()

                dna = get_dna_profile(trig_time, df_1w, df_1h, df_1d, df_4h, symbol=symbol)
                if dna == "neutral": continue
                if dna not in green_map[symbol]: continue
                
                # Filter Logic Debug
                if idx_scan < 5: 
                    print(f"DEBUG: {symbol} DNA Match. Check Filter...")
                    
                # --- DNA MUJDE RULES (IRON WALL) ---
                if rule_vol or rule_adx: # rule_trend is False in V3 simulation
                    d_cutoff = trig_time.normalize() - pd.Timedelta(days=1)
                    d_row = df_1d[df_1d.index <= d_cutoff].tail(1)
                    if len(d_row) > 0:
                        vol_vals = df_1d['volume'][df_1d.index < d_cutoff].tail(20)
                        if len(vol_vals) > 0:
                            v_mom_val = d_row['volume'].iloc[-1] / vol_vals.mean()
                        else: v_mom_val = 0
                        adx_val = d_row['adx14'].iloc[-1]
                    else: v_mom_val=0; adx_val=0
                    
                    if idx_scan < 5: 
                         print(f"  --> Filter Check: Vol={rule_vol}({v_mom_val:.2f}), ADX={rule_adx}({adx_val:.1f})")

                    if rule_vol and v_mom_val <= 1.0: continue
                    if rule_adx and adx_val <= 20: continue

                # Report Calc
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
                
                # Display values
                if 'adx_val' not in locals(): 
                     d_row_prev = df_1d[df_1d.index <= (trig_time.normalize() - pd.Timedelta(days=1))].tail(1)
                     adx_val = d_row_prev['adx14'].iloc[-1] if len(d_row_prev)>0 else 0
                if 'v_mom_val' not in locals():
                     d_cutoff = trig_time.normalize() - pd.Timedelta(days=1)
                     d_row_prev = df_1d[df_1d.index <= d_cutoff].tail(1)
                     v_mom_val = 0
                     if len(d_row_prev) > 0:
                         vol_vals = df_1d['volume'][df_1d.index < d_cutoff].tail(20)
                         if len(vol_vals) > 0: v_mom_val = d_row_prev['volume'].iloc[-1] / vol_vals.mean()


                trend_emoji = "🟡" 
                
                row = f"| {len(report_rows)+1} | {symbol} | {max_str} | 0% | {trig_str} | RSI-EMA | - | {trend_emoji} | 🟡 | 0 | 0° | - | - | {tier} | - | - | - | - | - | {int(adx_val)} | 0 | 0 | 0 | 0 | 0 | {v_mom_val:.1f}x |"
                report_rows.append(row)
                
                
        except Exception as e: 
            if idx_scan < 10: print(f"HATA ({symbol}): {e}")
            continue
            
        processed += 1
        if processed % 20 == 0: print(f"  Processed: {processed}/{len(green_map)}")
        
    with open(OUTPUT_FILE, "w") as f:
        f.write("# YESİL LİSTE V3 (FINAL OPTIMIZED)\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write("| NO | SYM | MAX | CLOSE | TIME | SIG | CVT | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-21 | BAR | NEXT | N-1 | CGS | ADX | ATR% | Vrsi | VBoy | V100 | V21 | V-Mom |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in report_rows:
            f.write(r + "\n")
            
    print(f"✅ Yeşil Liste V3 Raporu: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scanner()
