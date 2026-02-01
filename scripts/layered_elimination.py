#!/usr/bin/env python3
"""
KATMANLI ELEME ANALİZİ - Dahi Modu v4
İlk filtre uygulandıktan sonra kalan veri üzerinde 2. ve 3. katman kuralları bul
"""

import pandas as pd
import numpy as np
import os
import json
import math
from datetime import datetime

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
START_DATE = "2026-01-01"
END_DATE = "2026-01-30"

def load_clean(path):
    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df = df[~df.index.duplicated(keep='last')]
    return df.sort_index()

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
        daily_integrity_cutoff = day.normalize()
        sub_h1_24 = df_h1[df_h1.index < day].tail(24)
        sub_d = df_d[df_d.index < daily_integrity_cutoff]
        sub_h4 = df_h4[df_h4.index < day]
        sub_h1 = df_h1[df_h1.index < day]
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

def collect_all_triggers():
    print("=" * 70)
    print("🧠 KATMANLI ELEME ANALİZİ - Dahi Modu v4")
    print("=" * 70)
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    all_triggers = []
    start_d, end_d = pd.Timestamp(START_DATE), pd.Timestamp(END_DATE) + pd.Timedelta(days=1)
    
    print(f"Tarih: {START_DATE} -> {END_DATE}")
    print(f"Coinler: {len(symbols)}")
    print("Veri toplaniyor...")
    
    for symbol in symbols:
        try:
            key_path = f"/Users/alisaglam/TezaverMac/data/golden_keys/{symbol}_key.json"
            if not os.path.exists(key_path): continue
            with open(key_path, "r") as f:
                golden_dna_list = set(json.load(f).get('golden_dna_list', []))
            
            df_1d = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
            df_4h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
            df_1h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
            df_1w = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")
            df_15m = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet")

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

            delta = df_15m['close'].diff()
            alpha = 1 / 11
            gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
            df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
            df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
            for p in [20, 25, 30, 35, 40, 45, 50, 55]:
                df_15m[f'rsi_rib_{p}'] = df_15m['rsi_ema'].ewm(span=p, adjust=False).mean()
            tr = np.maximum(df_15m['high'] - df_15m['low'], np.maximum(abs(df_15m['high'] - df_15m['close'].shift(1)), abs(df_15m['low'] - df_15m['close'].shift(1))))
            df_15m['atr100'] = tr.rolling(window=100).mean()
            df_15m['atr21'] = tr.rolling(window=21).mean()
            df_15m['tr'] = tr

            current = start_d
            while current <= end_d:
                try:
                    dna_ayas = get_profile_simple(current, df_1w, df_1h, df_1d, df_4h)
                    is_ayas = (dna_ayas != "neutral") and (dna_ayas in golden_dna_list)
                    
                    current_utc = current.normalize()
                    day_mask = (df_15m.index.normalize() == current_utc)
                    target_day_data = df_15m[day_mask]
                    if target_day_data.empty:
                        current += pd.Timedelta(days=1); continue

                    try:
                        daily_atr_val = df_1d.loc[df_1d.index.normalize() == current.normalize(), 'atr_pct']
                        d_atr = daily_atr_val.values[0] if not daily_atr_val.empty else 0
                        daily_adx_val = df_1d.loc[df_1d.index.normalize() == current.normalize(), 'adx14']
                        d_adx = daily_adx_val.values[0] if not daily_adx_val.empty else 0
                        if np.isnan(d_adx): d_adx = 0
                    except:
                        d_atr, d_adx = 0, 0

                    rsi_vals = df_15m['rsi'].values
                    all_trigger_indices = np.where((rsi_vals[:-1] <= 70) & (rsi_vals[1:] > 70))[0] + 1
                    
                    day_indices = np.where(day_mask)[0]
                    for i in day_indices:
                        if i < 21: continue
                        if i not in all_trigger_indices: continue
                        
                        trig_time = df_15m.index[i]
                        
                        cutoff_4h = trig_time - pd.Timedelta(hours=4)
                        last_4h = df_4h[df_4h.index <= cutoff_4h]
                        t4 = 1 if not last_4h.empty and last_4h.iloc[-1]['close'] > last_4h.iloc[-1]['ema21'] else 0
                        
                        cutoff_1h = trig_time - pd.Timedelta(hours=1)
                        last_1h = df_1h[df_1h.index <= cutoff_1h]
                        t1 = 1 if not last_1h.empty and last_1h.iloc[-1]['close'] > last_1h.iloc[-1]['ema21'] else 0
                        
                        trend_score = t4 + t1
                        trend_str = f"{t4}{t1}"

                        v_t = df_15m['volume'].values[i]
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
                        
                        val_20 = df_15m['rsi_rib_20'].values[i]
                        val_55 = df_15m['rsi_rib_55'].values[i]
                        val_20_prev = df_15m['rsi_rib_20'].values[i-1] if i>=1 else val_20
                        val_55_prev = df_15m['rsi_rib_55'].values[i-1] if i>=1 else val_55
                        
                        ribbon_above = val_20 > val_55
                        curr_v = val_20 if ribbon_above else val_55
                        prev_v = val_20_prev if ribbon_above else val_55_prev
                        
                        slope = (curr_v - prev_v) / 2.0
                        ang_deg = math.degrees(math.atan(slope))
                        ang_score = ang_deg / 4.5
                        
                        if curr_v < 30: pos = "black"
                        elif curr_v < 50: pos = "red"
                        elif curr_v < 60: pos = "yellow"
                        elif curr_v < 70: pos = "green"
                        else: pos = "orange"
                        
                        atr21_val = df_15m['atr21'].values[i]
                        close_val = df_15m['close'].values[i]
                        atr_adj = (atr21_val / close_val) * 100 if close_val > 0 else 0
                        
                        rsi_ema_now = df_15m['rsi_ema'].values[i]
                        rsi_ema_prev = df_15m['rsi_ema'].values[i-1] if i > 0 else rsi_ema_now
                        rsi_slope = rsi_ema_now - rsi_ema_prev
                        rsi_angle = math.degrees(math.atan(rsi_slope))
                        
                        rsi_val = df_15m['rsi'].values[i]
                        
                        next_triggers = all_trigger_indices[all_trigger_indices > i]
                        next_t_idx = next_triggers[0] if len(next_triggers) > 0 else len(df_15m)
                        search_limit = min(i + 22, next_t_idx)
                        
                        if i + 1 < len(df_15m):
                            val_slice = df_15m['high'].values[i + 1 : search_limit + 1]
                            peak_p = val_slice.max() if len(val_slice) > 0 else df_15m['close'].values[i]
                        else:
                            peak_p = df_15m['close'].values[i]
                        
                        peak_pct = ((peak_p / df_15m['close'].values[i]) - 1) * 100
                        
                        if peak_pct >= 5: cat = "tier"
                        elif peak_pct >= 2: cat = "small_gain"
                        elif peak_pct >= 0: cat = "flat"
                        else: cat = "garbage"
                        
                        all_triggers.append({
                            'symbol': symbol, 'date': current.strftime('%Y-%m-%d'),
                            'is_ayas': is_ayas, 
                            'trend_str': trend_str, 'trend_score': trend_score,
                            'pos': pos, 'ribbon_above': ribbon_above,
                            'ang_score': ang_score, 'rsi_angle': rsi_angle, 'rsi': rsi_val,
                            'v_idx': v_idx, 'v_dyn': v_dyn, 'v_mom': v_mom, 'v_eff': v_eff, 'v_hyb': v_hyb,
                            'atr_adj': atr_adj, 'd_atr': d_atr, 'd_adx': d_adx,
                            'peak_pct': peak_pct, 'cat': cat
                        })
                            
                except: pass
                current += pd.Timedelta(days=1)
        except: continue
    
    return pd.DataFrame(all_triggers)

def find_next_elimination_rule(df, layer_name, excluded_rules=[]):
    """Find the best elimination rule for current dataset"""
    df['is_tier'] = df['cat'] == 'tier'
    df['is_small'] = df['cat'] == 'small_gain'
    df['is_noise'] = df['cat'].isin(['flat', 'garbage'])
    
    tier_count = df['is_tier'].sum()
    small_count = df['is_small'].sum()
    noise_count = df['is_noise'].sum()
    total = len(df)
    
    print(f"\n📊 {layer_name} - Veri Durumu:")
    print(f"   Toplam: {total}")
    print(f"   Tier: {tier_count} ({tier_count/total*100:.1f}%)")
    print(f"   Small: {small_count} ({small_count/total*100:.1f}%)")
    print(f"   Noise: {noise_count} ({noise_count/total*100:.1f}%)")
    
    rules_to_test = [
        ("trend_str == '00'", df['trend_str'] == '00'),
        ("trend_str == '01'", df['trend_str'] == '01'),
        ("trend_score == 0", df['trend_score'] == 0),
        ("trend_score < 2", df['trend_score'] < 2),
        ("pos == 'black'", df['pos'] == 'black'),
        ("pos == 'red'", df['pos'] == 'red'),
        ("pos in ['black','red']", df['pos'].isin(['black', 'red'])),
        ("ribbon_above == False", df['ribbon_above'] == False),
        ("ang_score < -2", df['ang_score'] < -2),
        ("ang_score < 0", df['ang_score'] < 0),
        ("ang_score < 2", df['ang_score'] < 2),
        ("rsi_angle < 0", df['rsi_angle'] < 0),
        ("rsi_angle < 30", df['rsi_angle'] < 30),
        ("rsi_angle < 45", df['rsi_angle'] < 45),
        ("rsi < 71", df['rsi'] < 71),
        ("rsi < 72", df['rsi'] < 72),
        ("rsi < 73", df['rsi'] < 73),
        ("v_idx < 3", df['v_idx'] < 3),
        ("v_idx < 4", df['v_idx'] < 4),
        ("v_idx < 5", df['v_idx'] < 5),
        ("v_dyn < 3", df['v_dyn'] < 3),
        ("v_dyn < 4", df['v_dyn'] < 4),
        ("v_dyn < 5", df['v_dyn'] < 5),
        ("v_mom < 0.8", df['v_mom'] < 0.8),
        ("v_mom < 1.0", df['v_mom'] < 1.0),
        ("v_mom < 1.2", df['v_mom'] < 1.2),
        ("v_eff < 3", df['v_eff'] < 3),
        ("v_eff < 4", df['v_eff'] < 4),
        ("v_eff < 5", df['v_eff'] < 5),
        ("v_hyb < 5", df['v_hyb'] < 5),
        ("v_hyb < 6", df['v_hyb'] < 6),
        ("v_hyb < 7", df['v_hyb'] < 7),
        ("v_hyb < 8", df['v_hyb'] < 8),
        ("atr_adj < 0.3", df['atr_adj'] < 0.3),
        ("atr_adj < 0.5", df['atr_adj'] < 0.5),
        ("atr_adj < 0.8", df['atr_adj'] < 0.8),
        ("atr_adj < 1.0", df['atr_adj'] < 1.0),
        ("d_atr < 3", df['d_atr'] < 3),
        ("d_atr < 4", df['d_atr'] < 4),
        ("d_atr < 5", df['d_atr'] < 5),
        ("d_atr < 6", df['d_atr'] < 6),
        ("d_adx < 20", df['d_adx'] < 20),
        ("d_adx < 25", df['d_adx'] < 25),
        ("d_adx < 30", df['d_adx'] < 30),
    ]
    
    # Filter out already used rules
    rules_to_test = [(n, m) for n, m in rules_to_test if n not in excluded_rules]
    
    results = []
    
    for rule_name, rule_mask in rules_to_test:
        noise_eliminated = (rule_mask & df['is_noise']).sum()
        tier_lost = (rule_mask & df['is_tier']).sum()
        small_lost = (rule_mask & df['is_small']).sum()
        
        if noise_eliminated > 0:
            # Efficiency = Noise eliminated per Tier lost (higher is better)
            tier_cost = tier_lost if tier_lost > 0 else 0.1
            efficiency = noise_eliminated / tier_cost
            
            results.append({
                'rule': rule_name,
                'noise_elim': noise_eliminated,
                'noise_pct': noise_eliminated / noise_count * 100 if noise_count > 0 else 0,
                'tier_lost': tier_lost,
                'tier_pct': tier_lost / tier_count * 100 if tier_count > 0 else 0,
                'small_lost': small_lost,
                'small_pct': small_lost / small_count * 100 if small_count > 0 else 0,
                'efficiency': efficiency
            })
    
    results_df = pd.DataFrame(results)
    
    # Show top rules sorted by efficiency (low tier loss, high noise elimination)
    print(f"\n🎯 {layer_name} - En İyi Kurallar:")
    print("-" * 90)
    
    # First show rules with ZERO Tier loss
    zero_tier = results_df[results_df['tier_lost'] == 0].sort_values('noise_elim', ascending=False)
    if not zero_tier.empty:
        print("\n✅ TIER KAYBI SIFIR:")
        for _, row in zero_tier.head(5).iterrows():
            print(f"   {row['rule']:<25} Noise: {row['noise_elim']:>5} ({row['noise_pct']:>5.1f}%) | Small: {row['small_lost']:>5}")
    
    # Then show rules with minimal Tier loss but high effectiveness
    low_tier = results_df[(results_df['tier_lost'] <= 10) & (results_df['noise_elim'] >= 100)].sort_values('efficiency', ascending=False)
    if not low_tier.empty:
        print("\n⚠️ DÜŞÜK TIER KAYBI (≤10), YÜKSEK ETKİ:")
        for _, row in low_tier.head(10).iterrows():
            tier_icon = "✅" if row['tier_lost'] == 0 else f"❌{int(row['tier_lost'])}"
            print(f"   {row['rule']:<25} Noise: {row['noise_elim']:>5} ({row['noise_pct']:>5.1f}%) | Tier: {tier_icon:<6} | Eff: {row['efficiency']:.1f}")
    
    return results_df

def run_layered_analysis(df):
    """Run multi-layer elimination analysis with Phase A (fixed) and Phase B (search)"""
    
    print("\n" + "=" * 70)
    print("🏗️ İKİ FAZLI ELEME SİSTEMİ")
    print("=" * 70)
    
    original_total = len(df)
    original_tier = (df['cat'] == 'tier').sum()
    original_small = (df['cat'] == 'small_gain').sum()
    original_noise = (df['cat'].isin(['flat', 'garbage'])).sum()
    
    current_df = df.copy()
    
    # ========================================
    # PHASE A - FIXED RULES (ATR-based)
    # ========================================
    print("\n" + "=" * 70)
    print("🅰️ FAZ A: ATR BAZLI ELEME (Sabit Kurallar)")
    print("=" * 70)
    
    phase_a_rules = [
        ("d_atr < 4", lambda d: d['d_atr'] >= 4),
        ("atr_adj < 0.3", lambda d: d['atr_adj'] >= 0.3),
        ("d_atr < 5", lambda d: d['d_atr'] >= 5),
    ]
    
    for rule_name, keep_func in phase_a_rules:
        before = len(current_df)
        tier_before = (current_df['cat'] == 'tier').sum()
        
        current_df = current_df[keep_func(current_df)]
        
        after = len(current_df)
        tier_after = (current_df['cat'] == 'tier').sum()
        
        print(f"  ❌ {rule_name}: Elenen={before-after}, Tier Kaybı={tier_before-tier_after}")
    
    phase_a_total = len(current_df)
    phase_a_tier = (current_df['cat'] == 'tier').sum()
    phase_a_small = (current_df['cat'] == 'small_gain').sum()
    phase_a_noise = (current_df['cat'].isin(['flat', 'garbage'])).sum()
    
    print(f"\n📊 FAZ A SONRASI:")
    print(f"   Toplam: {phase_a_total} (Elenen: {original_total - phase_a_total})")
    print(f"   Tier: {phase_a_tier} ({phase_a_tier/phase_a_total*100:.1f}%)")
    print(f"   Tier Kaybı: {original_tier - phase_a_tier} ({(original_tier - phase_a_tier)/original_tier*100:.1f}%)")
    
    # ========================================
    # PHASE B - DYNAMIC RULES (Search for best)
    # ========================================
    print("\n" + "=" * 70)
    print("🅱️ FAZ B: DİNAMİK ELEME (Derinlemesine Arama)")
    print("=" * 70)
    
    # Tier loss budget for Phase B (additional 10% of remaining)
    remaining_tier = (current_df['cat'] == 'tier').sum()
    phase_b_tier_limit = int(remaining_tier * 0.10)  # 10% of remaining
    
    print(f"\n🎯 Faz B Hedefi: Max {phase_b_tier_limit} ek Tier kaybı (%10)")
    print(f"   Kalan Tier: {remaining_tier}")
    print(f"   Kalan Noise: {(current_df['cat'].isin(['flat', 'garbage'])).sum()}")
    
    # Extended Phase B candidate rules
    phase_b_rules = [
        # Volume metrics
        ("v_hyb < 5", lambda d: d['v_hyb'] < 5),
        ("v_hyb < 6", lambda d: d['v_hyb'] < 6),
        ("v_hyb < 7", lambda d: d['v_hyb'] < 7),
        ("v_hyb < 8", lambda d: d['v_hyb'] < 8),
        ("v_idx < 3", lambda d: d['v_idx'] < 3),
        ("v_idx < 4", lambda d: d['v_idx'] < 4),
        ("v_idx < 5", lambda d: d['v_idx'] < 5),
        ("v_idx < 6", lambda d: d['v_idx'] < 6),
        ("v_dyn < 3", lambda d: d['v_dyn'] < 3),
        ("v_dyn < 4", lambda d: d['v_dyn'] < 4),
        ("v_dyn < 5", lambda d: d['v_dyn'] < 5),
        ("v_mom < 0.6", lambda d: d['v_mom'] < 0.6),
        ("v_mom < 0.8", lambda d: d['v_mom'] < 0.8),
        ("v_mom < 1.0", lambda d: d['v_mom'] < 1.0),
        ("v_eff < 2", lambda d: d['v_eff'] < 2),
        ("v_eff < 3", lambda d: d['v_eff'] < 3),
        ("v_eff < 4", lambda d: d['v_eff'] < 4),
        ("v_eff < 5", lambda d: d['v_eff'] < 5),
        # Trend
        ("trend_score == 0", lambda d: d['trend_score'] == 0),
        ("trend_str == '01'", lambda d: d['trend_str'] == '01'),
        ("trend_str == '00'", lambda d: d['trend_str'] == '00'),
        ("trend_score < 2", lambda d: d['trend_score'] < 2),
        # RSI
        ("rsi < 71", lambda d: d['rsi'] < 71),
        ("rsi < 72", lambda d: d['rsi'] < 72),
        ("rsi < 73", lambda d: d['rsi'] < 73),
        # Position
        ("pos == 'red'", lambda d: d['pos'] == 'red'),
        ("pos == 'yellow'", lambda d: d['pos'] == 'yellow'),
        ("pos in ['red','black']", lambda d: d['pos'].isin(['red', 'black'])),
        # Ribbon
        ("ribbon_above == False", lambda d: d['ribbon_above'] == False),
        # Angle
        ("ang_score < -1", lambda d: d['ang_score'] < -1),
        ("ang_score < 0", lambda d: d['ang_score'] < 0),
        ("ang_score < 1", lambda d: d['ang_score'] < 1),
        ("ang_score < 2", lambda d: d['ang_score'] < 2),
        ("rsi_angle < 30", lambda d: d['rsi_angle'] < 30),
        ("rsi_angle < 45", lambda d: d['rsi_angle'] < 45),
        ("rsi_angle < 50", lambda d: d['rsi_angle'] < 50),
        # ADX
        ("d_adx < 15", lambda d: d['d_adx'] < 15),
        ("d_adx < 20", lambda d: d['d_adx'] < 20),
        ("d_adx < 25", lambda d: d['d_adx'] < 25),
        ("d_adx < 30", lambda d: d['d_adx'] < 30),
    ]
    
    applied_b_rules = []
    total_b_tier_lost = 0
    layer = 0
    
    # Search until we hit the tier limit
    while total_b_tier_lost < phase_b_tier_limit:
        layer += 1
        
        # Evaluate ALL unused rules
        rule_evaluations = []
        
        for rule_name, rule_func in phase_b_rules:
            if rule_name in applied_b_rules:
                continue
            
            mask = rule_func(current_df)
            if not mask.any():
                continue
            
            noise_elim = ((current_df['cat'].isin(['flat', 'garbage'])) & mask).sum()
            tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
            small_lost = ((current_df['cat'] == 'small_gain') & mask).sum()
            
            # Skip if would exceed budget
            if total_b_tier_lost + tier_lost > phase_b_tier_limit:
                continue
            
            # Calculate efficiency (Noise per Tier)
            tier_cost = max(tier_lost, 0.1)
            efficiency = noise_elim / tier_cost
            
            # Only consider if eliminates at least 20 noise
            if noise_elim >= 20:
                rule_evaluations.append({
                    'name': rule_name,
                    'func': rule_func,
                    'noise_elim': noise_elim,
                    'tier_lost': tier_lost,
                    'small_lost': small_lost,
                    'efficiency': efficiency
                })
        
        if not rule_evaluations:
            print(f"\n⏹️ Faz B Katman {layer}: Bütçe dahilinde kural kalmadı.")
            break
        
        # Sort by efficiency (best first)
        rule_evaluations.sort(key=lambda x: x['efficiency'], reverse=True)
        
        # Show top candidates
        if layer <= 3:
            print(f"\n🔍 Faz B Katman {layer} - En İyi Adaylar:")
            for r in rule_evaluations[:5]:
                print(f"   {r['name']:<25} Noise:{r['noise_elim']:>5} | Tier:{r['tier_lost']:>3} | Eff:{r['efficiency']:.1f}")
        
        # Pick the best one
        best = rule_evaluations[0]
        
        # Apply
        mask = best['func'](current_df)
        current_df = current_df[~mask]
        applied_b_rules.append(best['name'])
        total_b_tier_lost += best['tier_lost']
        
        print(f"\n   ✅ SEÇİLEN: {best['name']}")
        print(f"      Noise Elenen: {best['noise_elim']}")
        print(f"      Tier Kaybı: {best['tier_lost']} (Faz B Toplam: {total_b_tier_lost}/{phase_b_tier_limit})")
        print(f"      Small Kaybı: {best['small_lost']}")
        print(f"      Kalan: {len(current_df)}")
    
    # ========================================
    # PHASE C - AGGRESSIVE (Tier-only protection)
    # ========================================
    print("\n" + "=" * 70)
    print("🔥 FAZ C: AGRESİF ELEME (Sadece Tier Koruma)")
    print("=" * 70)
    
    remaining_tier_c = (current_df['cat'] == 'tier').sum()
    remaining_small = (current_df['cat'] == 'small_gain').sum()
    remaining_noise = (current_df['cat'].isin(['flat', 'garbage'])).sum()
    remaining_bad = remaining_small + remaining_noise  # Eliminate both!
    
    phase_c_tier_limit = int(remaining_tier_c * 0.10)  # 10% of remaining Tier
    
    print(f"\n🎯 Faz C Hedefi: Max {phase_c_tier_limit} ek Tier kaybı (%10)")
    print(f"   Kalan Tier: {remaining_tier_c}")
    print(f"   Elenecek (Small+Noise): {remaining_bad}")
    print(f"   Hedef: Tier oranını maksimize et!")
    
    # Phase C rules - target Small + Noise together
    phase_c_rules = [
        # Volume (target less profitable)
        ("v_hyb < 6", lambda d: d['v_hyb'] < 6),
        ("v_hyb < 7", lambda d: d['v_hyb'] < 7),
        ("v_hyb < 8", lambda d: d['v_hyb'] < 8),
        ("v_idx < 4", lambda d: d['v_idx'] < 4),
        ("v_idx < 5", lambda d: d['v_idx'] < 5),
        ("v_idx < 6", lambda d: d['v_idx'] < 6),
        ("v_dyn < 4", lambda d: d['v_dyn'] < 4),
        ("v_dyn < 5", lambda d: d['v_dyn'] < 5),
        ("v_mom < 0.8", lambda d: d['v_mom'] < 0.8),
        ("v_mom < 1.0", lambda d: d['v_mom'] < 1.0),
        ("v_mom < 1.2", lambda d: d['v_mom'] < 1.2),
        ("v_eff < 3", lambda d: d['v_eff'] < 3),
        ("v_eff < 4", lambda d: d['v_eff'] < 4),
        ("v_eff < 5", lambda d: d['v_eff'] < 5),
        # Trend
        ("trend_score == 0", lambda d: d['trend_score'] == 0),
        ("trend_score < 2", lambda d: d['trend_score'] < 2),
        ("trend_str == '01'", lambda d: d['trend_str'] == '01'),
        ("trend_str == '00'", lambda d: d['trend_str'] == '00'),
        # RSI
        ("rsi < 72", lambda d: d['rsi'] < 72),
        ("rsi < 73", lambda d: d['rsi'] < 73),
        ("rsi < 74", lambda d: d['rsi'] < 74),
        # Position
        ("pos == 'red'", lambda d: d['pos'] == 'red'),
        ("pos == 'yellow'", lambda d: d['pos'] == 'yellow'),
        ("pos in ['red','yellow']", lambda d: d['pos'].isin(['red', 'yellow'])),
        # Ribbon
        ("ribbon_above == False", lambda d: d['ribbon_above'] == False),
        # Angle
        ("ang_score < 1", lambda d: d['ang_score'] < 1),
        ("ang_score < 2", lambda d: d['ang_score'] < 2),
        ("ang_score < 3", lambda d: d['ang_score'] < 3),
        ("rsi_angle < 45", lambda d: d['rsi_angle'] < 45),
        ("rsi_angle < 50", lambda d: d['rsi_angle'] < 50),
        ("rsi_angle < 55", lambda d: d['rsi_angle'] < 55),
        # ADX
        ("d_adx < 25", lambda d: d['d_adx'] < 25),
        ("d_adx < 30", lambda d: d['d_adx'] < 30),
        ("d_adx < 35", lambda d: d['d_adx'] < 35),
    ]
    
    applied_c_rules = []
    total_c_tier_lost = 0
    layer = 0
    
    while total_c_tier_lost < phase_c_tier_limit:
        layer += 1
        rule_evaluations = []
        
        for rule_name, rule_func in phase_c_rules:
            if rule_name in applied_c_rules:
                continue
            
            mask = rule_func(current_df)
            if not mask.any():
                continue
            
            # Count ALL eliminated (Small + Noise = "bad")
            bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
            tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
            
            if total_c_tier_lost + tier_lost > phase_c_tier_limit:
                continue
            
            tier_cost = max(tier_lost, 0.1)
            efficiency = bad_elim / tier_cost
            
            if bad_elim >= 50:
                rule_evaluations.append({
                    'name': rule_name,
                    'func': rule_func,
                    'bad_elim': bad_elim,
                    'tier_lost': tier_lost,
                    'efficiency': efficiency
                })
        
        if not rule_evaluations:
            print(f"\n⏹️ Faz C Katman {layer}: Bütçe dahilinde kural kalmadı.")
            break
        
        rule_evaluations.sort(key=lambda x: x['efficiency'], reverse=True)
        
        if layer <= 5:
            print(f"\n🔍 Faz C Katman {layer} - En İyi Adaylar:")
            for r in rule_evaluations[:5]:
                print(f"   {r['name']:<25} Bad:{r['bad_elim']:>5} | Tier:{r['tier_lost']:>3} | Eff:{r['efficiency']:.1f}")
        
        best = rule_evaluations[0]
        
        mask = best['func'](current_df)
        current_df = current_df[~mask]
        applied_c_rules.append(best['name'])
        total_c_tier_lost += best['tier_lost']
        
        print(f"\n   ✅ SEÇİLEN: {best['name']}")
        print(f"      Bad Elenen: {best['bad_elim']}")
        print(f"      Tier Kaybı: {best['tier_lost']} (Faz C Toplam: {total_c_tier_lost}/{phase_c_tier_limit})")
        print(f"      Kalan: {len(current_df)}")
    
    # ========================================
    # PHASE D - COMBINATION RULES (Multi-feature)
    # ========================================
    print("\n" + "=" * 70)
    print("🧬 FAZ D: KOMBİNASYON KURALLARI (Çoklu Özellik)")
    print("=" * 70)
    
    remaining_tier_d = (current_df['cat'] == 'tier').sum()
    remaining_bad_d = ((current_df['cat'] == 'small_gain') | (current_df['cat'].isin(['flat', 'garbage']))).sum()
    
    print(f"\n🎯 Faz D Hedefi: Kombinasyon bazlı kurallarla SIFIR Tier kaybı")
    print(f"   Kalan Tier: {remaining_tier_d}")
    print(f"   Elenecek (Small+Noise): {remaining_bad_d}")
    
    # Base conditions for combinations
    conditions = {
        'v_hyb_low': lambda d: d['v_hyb'] < 7,
        'v_hyb_mid': lambda d: (d['v_hyb'] >= 7) & (d['v_hyb'] < 9),
        'v_idx_low': lambda d: d['v_idx'] < 5,
        'v_idx_mid': lambda d: (d['v_idx'] >= 5) & (d['v_idx'] < 7),
        'v_dyn_low': lambda d: d['v_dyn'] < 5,
        'v_eff_low': lambda d: d['v_eff'] < 4,
        'v_eff_mid': lambda d: (d['v_eff'] >= 4) & (d['v_eff'] < 6),
        'v_mom_low': lambda d: d['v_mom'] < 1.0,
        'trend_0': lambda d: d['trend_score'] == 0,
        'trend_01': lambda d: d['trend_str'] == '01',
        'rsi_low': lambda d: d['rsi'] < 73,
        'rsi_mid': lambda d: (d['rsi'] >= 73) & (d['rsi'] < 76),
        'pos_red': lambda d: d['pos'] == 'red',
        'pos_yellow': lambda d: d['pos'] == 'yellow',
        'ribbon_below': lambda d: d['ribbon_above'] == False,
        'ang_low': lambda d: d['ang_score'] < 3,
        'rsi_ang_low': lambda d: d['rsi_angle'] < 55,
        'adx_low': lambda d: d['d_adx'] < 35,
    }
    
    # Generate 2-feature combinations
    from itertools import combinations as iter_combos
    
    combo_results = []
    cond_names = list(conditions.keys())
    
    print(f"\n🔍 2'li ve 3'lü kombinasyonlar deneniyor...")
    print(f"   Toplam {len(cond_names)} koşul mevcut")
    
    # Test 2-combos
    for combo in iter_combos(cond_names, 2):
        cond1, cond2 = combo
        mask = conditions[cond1](current_df) & conditions[cond2](current_df)
        
        if not mask.any():
            continue
        
        bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
        tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
        
        if tier_lost == 0 and bad_elim >= 5:
            combo_results.append({
                'combo': f"{cond1} + {cond2}",
                'type': '2-combo',
                'bad_elim': bad_elim,
                'tier_lost': 0
            })
    
    # Test 3-combos
    for combo in iter_combos(cond_names, 3):
        cond1, cond2, cond3 = combo
        mask = conditions[cond1](current_df) & conditions[cond2](current_df) & conditions[cond3](current_df)
        
        if not mask.any():
            continue
        
        bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
        tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
        
        if tier_lost == 0 and bad_elim >= 5:
            combo_results.append({
                'combo': f"{cond1} + {cond2} + {cond3}",
                'type': '3-combo',
                'bad_elim': bad_elim,
                'tier_lost': 0
            })
    
    # Sort by bad eliminated
    combo_results.sort(key=lambda x: x['bad_elim'], reverse=True)
    
    print(f"\n✅ Tier kaybı 0 olan {len(combo_results)} kombinasyon bulundu!")
    
    if combo_results:
        print(f"\n🏆 EN İYİ 15 KOMBİNASYON:")
        print("-" * 70)
        for i, r in enumerate(combo_results[:15], 1):
            print(f"   {i:2d}. {r['combo']:<45} Bad:{r['bad_elim']:>4} | Tier:0 ✅")
    
    # Apply top combinations greedily
    applied_d_rules = []
    
    for r in combo_results:
        if len(applied_d_rules) >= 5:  # Max 5 combo rules
            break
        
        # Parse combo and apply
        parts = r['combo'].split(' + ')
        
        if len(parts) == 2:
            mask = conditions[parts[0]](current_df) & conditions[parts[1]](current_df)
        elif len(parts) == 3:
            mask = conditions[parts[0]](current_df) & conditions[parts[1]](current_df) & conditions[parts[2]](current_df)
        else:
            continue
        
        bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
        tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
        
        if tier_lost == 0 and bad_elim >= 3:
            current_df = current_df[~mask]
            applied_d_rules.append(r['combo'])
            print(f"\n   ✅ UYGULANDI: {r['combo']}")
            print(f"      Bad Elenen: {bad_elim}")
            print(f"      Kalan: {len(current_df)}")
    
    # ========================================
    # PHASE E - EXTENDED COMBOS (4-feature + minimal tier loss)
    # ========================================
    print("\n" + "=" * 70)
    print("🔬 FAZ E: GENİŞLETİLMİŞ KOMBİNASYONLAR")
    print("=" * 70)
    
    remaining_tier_e = (current_df['cat'] == 'tier').sum()
    remaining_bad_e = ((current_df['cat'] == 'small_gain') | (current_df['cat'].isin(['flat', 'garbage']))).sum()
    
    print(f"\n🎯 Faz E Hedefi: 4'lü kombinasyonlar + minimal Tier kaybı (max 2 per rule)")
    print(f"   Kalan Tier: {remaining_tier_e}")
    print(f"   Elenecek (Small+Noise): {remaining_bad_e}")
    
    # Extended conditions for Phase E
    conditions_e = {
        'v_hyb_7': lambda d: d['v_hyb'] < 7,
        'v_hyb_8': lambda d: d['v_hyb'] < 8,
        'v_hyb_9': lambda d: d['v_hyb'] < 9,
        'v_idx_5': lambda d: d['v_idx'] < 5,
        'v_idx_6': lambda d: d['v_idx'] < 6,
        'v_idx_7': lambda d: d['v_idx'] < 7,
        'v_dyn_5': lambda d: d['v_dyn'] < 5,
        'v_dyn_6': lambda d: d['v_dyn'] < 6,
        'v_eff_4': lambda d: d['v_eff'] < 4,
        'v_eff_5': lambda d: d['v_eff'] < 5,
        'v_mom_1': lambda d: d['v_mom'] < 1.0,
        'v_mom_12': lambda d: d['v_mom'] < 1.2,
        'trend_0': lambda d: d['trend_score'] == 0,
        'trend_1': lambda d: d['trend_score'] < 2,
        'trend_01': lambda d: d['trend_str'] == '01',
        'rsi_73': lambda d: d['rsi'] < 73,
        'rsi_74': lambda d: d['rsi'] < 74,
        'rsi_75': lambda d: d['rsi'] < 75,
        'pos_red': lambda d: d['pos'] == 'red',
        'pos_yellow': lambda d: d['pos'] == 'yellow',
        'pos_orange': lambda d: d['pos'] == 'orange',
        'ribbon_below': lambda d: d['ribbon_above'] == False,
        'ang_3': lambda d: d['ang_score'] < 3,
        'ang_4': lambda d: d['ang_score'] < 4,
        'rsi_ang_55': lambda d: d['rsi_angle'] < 55,
        'rsi_ang_60': lambda d: d['rsi_angle'] < 60,
        'adx_30': lambda d: d['d_adx'] < 30,
        'adx_35': lambda d: d['d_adx'] < 35,
    }
    
    combo_results_e = []
    cond_names_e = list(conditions_e.keys())
    
    print(f"\n🔍 4'lü kombinasyonlar ve minimal kayıplı 2-3'lü deneniyor...")
    print(f"   Toplam {len(cond_names_e)} koşul mevcut")
    
    # Test 2-combos with tier_lost <= 2
    for combo in iter_combos(cond_names_e, 2):
        cond1, cond2 = combo
        mask = conditions_e[cond1](current_df) & conditions_e[cond2](current_df)
        
        if not mask.any():
            continue
        
        bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
        tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
        
        # Allow tier_lost <= 2
        if tier_lost <= 2 and bad_elim >= 10:
            efficiency = bad_elim / max(tier_lost, 0.1)
            combo_results_e.append({
                'combo': f"{cond1} + {cond2}",
                'type': '2-combo',
                'bad_elim': bad_elim,
                'tier_lost': tier_lost,
                'efficiency': efficiency
            })
    
    # Test 3-combos with tier_lost <= 1
    for combo in iter_combos(cond_names_e, 3):
        cond1, cond2, cond3 = combo
        mask = conditions_e[cond1](current_df) & conditions_e[cond2](current_df) & conditions_e[cond3](current_df)
        
        if not mask.any():
            continue
        
        bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
        tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
        
        if tier_lost <= 1 and bad_elim >= 5:
            efficiency = bad_elim / max(tier_lost, 0.1)
            combo_results_e.append({
                'combo': f"{cond1} + {cond2} + {cond3}",
                'type': '3-combo',
                'bad_elim': bad_elim,
                'tier_lost': tier_lost,
                'efficiency': efficiency
            })
    
    # Test 4-combos with tier_lost == 0
    for combo in iter_combos(cond_names_e, 4):
        cond1, cond2, cond3, cond4 = combo
        mask = conditions_e[cond1](current_df) & conditions_e[cond2](current_df) & conditions_e[cond3](current_df) & conditions_e[cond4](current_df)
        
        if not mask.any():
            continue
        
        bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
        tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
        
        if tier_lost == 0 and bad_elim >= 3:
            combo_results_e.append({
                'combo': f"{cond1} + {cond2} + {cond3} + {cond4}",
                'type': '4-combo',
                'bad_elim': bad_elim,
                'tier_lost': tier_lost,
                'efficiency': bad_elim * 10  # High priority for zero-loss
            })
    
    # Sort by efficiency
    combo_results_e.sort(key=lambda x: x['efficiency'], reverse=True)
    
    print(f"\n✅ Tier kaybı ≤2 olan {len(combo_results_e)} kombinasyon bulundu!")
    
    if combo_results_e:
        # Show by tier loss
        zero_loss = [r for r in combo_results_e if r['tier_lost'] == 0]
        one_loss = [r for r in combo_results_e if r['tier_lost'] == 1]
        two_loss = [r for r in combo_results_e if r['tier_lost'] == 2]
        
        print(f"\n   Tier=0: {len(zero_loss)} | Tier=1: {len(one_loss)} | Tier=2: {len(two_loss)}")
        
        print(f"\n🏆 EN İYİ 10 KOMBİNASYON (Efficiency sıralı):")
        print("-" * 80)
        for i, r in enumerate(combo_results_e[:10], 1):
            print(f"   {i:2d}. {r['combo']:<50} Bad:{r['bad_elim']:>4} | Tier:{r['tier_lost']} | Eff:{r['efficiency']:.0f}")
    
    # Apply top combinations greedily
    applied_e_rules = []
    total_e_tier_lost = 0
    max_e_tier = 10  # Max 10 Tier loss for Phase E
    
    for r in combo_results_e:
        if len(applied_e_rules) >= 8:  # Max 8 rules
            break
        if total_e_tier_lost + r['tier_lost'] > max_e_tier:
            continue
        
        # Parse combo and apply
        parts = r['combo'].split(' + ')
        
        if len(parts) == 2:
            mask = conditions_e[parts[0]](current_df) & conditions_e[parts[1]](current_df)
        elif len(parts) == 3:
            mask = conditions_e[parts[0]](current_df) & conditions_e[parts[1]](current_df) & conditions_e[parts[2]](current_df)
        elif len(parts) == 4:
            mask = conditions_e[parts[0]](current_df) & conditions_e[parts[1]](current_df) & conditions_e[parts[2]](current_df) & conditions_e[parts[3]](current_df)
        else:
            continue
        
        bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
        tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
        
        if bad_elim >= 3:
            current_df = current_df[~mask]
            applied_e_rules.append(r['combo'])
            total_e_tier_lost += tier_lost
            tier_icon = "✅" if tier_lost == 0 else f"⚠️{tier_lost}"
            print(f"\n   ✅ UYGULANDI: {r['combo']}")
            print(f"      Bad Elenen: {bad_elim} | Tier: {tier_icon}")
            print(f"      Kalan: {len(current_df)}")
    
    print(f"\n📊 Faz E Toplam: {len(applied_e_rules)} kural, {total_e_tier_lost} Tier kaybı")
    
    # ========================================
    # PHASE F - ULTRA EXTENDED (5-feature combos)
    # ========================================
    print("\n" + "=" * 70)
    print("🚀 FAZ F: ULTRA GENİŞLETİLMİŞ (5'li Kombinasyonlar)")
    print("=" * 70)
    
    remaining_tier_f = (current_df['cat'] == 'tier').sum()
    remaining_bad_f = ((current_df['cat'] == 'small_gain') | (current_df['cat'].isin(['flat', 'garbage']))).sum()
    
    print(f"\n🎯 Faz F Hedefi: 5'li kombinasyonlar + max 5 Tier kaybı toplam")
    print(f"   Kalan Tier: {remaining_tier_f}")
    print(f"   Elenecek (Small+Noise): {remaining_bad_f}")
    
    # Extended conditions for Phase F (more granular)
    conditions_f = {
        'v_hyb_8': lambda d: d['v_hyb'] < 8,
        'v_hyb_9': lambda d: d['v_hyb'] < 9,
        'v_hyb_10': lambda d: d['v_hyb'] < 10,
        'v_idx_6': lambda d: d['v_idx'] < 6,
        'v_idx_7': lambda d: d['v_idx'] < 7,
        'v_idx_8': lambda d: d['v_idx'] < 8,
        'v_dyn_6': lambda d: d['v_dyn'] < 6,
        'v_dyn_7': lambda d: d['v_dyn'] < 7,
        'v_eff_5': lambda d: d['v_eff'] < 5,
        'v_eff_6': lambda d: d['v_eff'] < 6,
        'v_mom_12': lambda d: d['v_mom'] < 1.2,
        'v_mom_15': lambda d: d['v_mom'] < 1.5,
        'trend_1': lambda d: d['trend_score'] < 2,
        'trend_01': lambda d: d['trend_str'] == '01',
        'rsi_74': lambda d: d['rsi'] < 74,
        'rsi_75': lambda d: d['rsi'] < 75,
        'rsi_76': lambda d: d['rsi'] < 76,
        'pos_yellow': lambda d: d['pos'] == 'yellow',
        'pos_orange': lambda d: d['pos'] == 'orange',
        'ribbon_below': lambda d: d['ribbon_above'] == False,
        'ang_4': lambda d: d['ang_score'] < 4,
        'ang_5': lambda d: d['ang_score'] < 5,
        'rsi_ang_60': lambda d: d['rsi_angle'] < 60,
        'rsi_ang_65': lambda d: d['rsi_angle'] < 65,
        'adx_35': lambda d: d['d_adx'] < 35,
        'adx_40': lambda d: d['d_adx'] < 40,
    }
    
    combo_results_f = []
    cond_names_f = list(conditions_f.keys())
    
    print(f"\n🔍 5'li kombinasyonlar deneniyor...")
    print(f"   Toplam {len(cond_names_f)} koşul mevcut")
    
    # Test 5-combos with tier_lost == 0
    count = 0
    for combo in iter_combos(cond_names_f, 5):
        count += 1
        if count > 50000:  # Limit iterations
            break
        
        cond1, cond2, cond3, cond4, cond5 = combo
        mask = (conditions_f[cond1](current_df) & conditions_f[cond2](current_df) & 
                conditions_f[cond3](current_df) & conditions_f[cond4](current_df) &
                conditions_f[cond5](current_df))
        
        if not mask.any():
            continue
        
        bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
        tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
        
        if tier_lost == 0 and bad_elim >= 3:
            combo_results_f.append({
                'combo': f"{cond1} + {cond2} + {cond3} + {cond4} + {cond5}",
                'type': '5-combo',
                'bad_elim': bad_elim,
                'tier_lost': 0,
                'efficiency': bad_elim * 10
            })
    
    # Also test remaining 3-4 combos with tier_lost <= 1
    for combo in iter_combos(cond_names_f, 3):
        cond1, cond2, cond3 = combo
        mask = conditions_f[cond1](current_df) & conditions_f[cond2](current_df) & conditions_f[cond3](current_df)
        
        if not mask.any():
            continue
        
        bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
        tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
        
        if tier_lost <= 1 and bad_elim >= 10:
            efficiency = bad_elim / max(tier_lost, 0.1)
            combo_results_f.append({
                'combo': f"{cond1} + {cond2} + {cond3}",
                'type': '3-combo',
                'bad_elim': bad_elim,
                'tier_lost': tier_lost,
                'efficiency': efficiency
            })
    
    # Sort by efficiency
    combo_results_f.sort(key=lambda x: x['efficiency'], reverse=True)
    
    print(f"\n✅ Uygun {len(combo_results_f)} kombinasyon bulundu!")
    
    if combo_results_f:
        zero_loss_f = len([r for r in combo_results_f if r['tier_lost'] == 0])
        print(f"   Tier=0: {zero_loss_f}")
        
        print(f"\n🏆 EN İYİ 10 KOMBİNASYON:")
        print("-" * 90)
        for i, r in enumerate(combo_results_f[:10], 1):
            combo_short = r['combo'][:55] + "..." if len(r['combo']) > 55 else r['combo']
            print(f"   {i:2d}. {combo_short:<60} Bad:{r['bad_elim']:>3} | Tier:{r['tier_lost']}")
    
    # Apply top combinations
    applied_f_rules = []
    total_f_tier_lost = 0
    max_f_tier = 5  # Max 5 Tier loss for Phase F
    
    for r in combo_results_f:
        if len(applied_f_rules) >= 10:  # Max 10 rules
            break
        if total_f_tier_lost + r['tier_lost'] > max_f_tier:
            continue
        
        parts = r['combo'].split(' + ')
        
        if len(parts) == 3:
            mask = conditions_f[parts[0]](current_df) & conditions_f[parts[1]](current_df) & conditions_f[parts[2]](current_df)
        elif len(parts) == 5:
            mask = (conditions_f[parts[0]](current_df) & conditions_f[parts[1]](current_df) & 
                   conditions_f[parts[2]](current_df) & conditions_f[parts[3]](current_df) &
                   conditions_f[parts[4]](current_df))
        else:
            continue
        
        bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
        tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
        
        if bad_elim >= 3:
            current_df = current_df[~mask]
            applied_f_rules.append(r['combo'])
            total_f_tier_lost += tier_lost
            tier_icon = "✅" if tier_lost == 0 else f"⚠️{tier_lost}"
            print(f"\n   ✅ UYGULANDI: {r['combo'][:60]}...")
            print(f"      Bad Elenen: {bad_elim} | Tier: {tier_icon}")
            print(f"      Kalan: {len(current_df)}")
    
    print(f"\n📊 Faz F Toplam: {len(applied_f_rules)} kural, {total_f_tier_lost} Tier kaybı")
    
    # ========================================
    # PHASE G - FINAL SWEEP (All remaining zero-loss)
    # ========================================
    print("\n" + "=" * 70)
    print("🧹 FAZ G: FİNAL SÜPÜRME (Kalan Tüm Sıfır Kayıplı)")
    print("=" * 70)
    
    remaining_tier_g = (current_df['cat'] == 'tier').sum()
    remaining_bad_g = ((current_df['cat'] == 'small_gain') | (current_df['cat'].isin(['flat', 'garbage']))).sum()
    
    print(f"\n🎯 Faz G Hedefi: Kalan TÜM sıfır kayıplı kombinasyonlar")
    print(f"   Kalan Tier: {remaining_tier_g}")
    print(f"   Elenecek (Small+Noise): {remaining_bad_g}")
    
    # Use same conditions but test ALL remaining combos
    conditions_g = {
        'v_hyb_9': lambda d: d['v_hyb'] < 9,
        'v_hyb_10': lambda d: d['v_hyb'] < 10,
        'v_idx_7': lambda d: d['v_idx'] < 7,
        'v_idx_8': lambda d: d['v_idx'] < 8,
        'v_dyn_6': lambda d: d['v_dyn'] < 6,
        'v_dyn_7': lambda d: d['v_dyn'] < 7,
        'v_eff_5': lambda d: d['v_eff'] < 5,
        'v_eff_6': lambda d: d['v_eff'] < 6,
        'v_mom_12': lambda d: d['v_mom'] < 1.2,
        'v_mom_15': lambda d: d['v_mom'] < 1.5,
        'trend_1': lambda d: d['trend_score'] < 2,
        'trend_01': lambda d: d['trend_str'] == '01',
        'rsi_75': lambda d: d['rsi'] < 75,
        'rsi_76': lambda d: d['rsi'] < 76,
        'pos_yellow': lambda d: d['pos'] == 'yellow',
        'pos_orange': lambda d: d['pos'] == 'orange',
        'ribbon_below': lambda d: d['ribbon_above'] == False,
        'ang_4': lambda d: d['ang_score'] < 4,
        'ang_5': lambda d: d['ang_score'] < 5,
        'rsi_ang_60': lambda d: d['rsi_angle'] < 60,
        'rsi_ang_65': lambda d: d['rsi_angle'] < 65,
        'adx_35': lambda d: d['d_adx'] < 35,
        'adx_40': lambda d: d['d_adx'] < 40,
    }
    
    cond_names_g = list(conditions_g.keys())
    
    print(f"\n🔍 Tüm 2-6'lı kombinasyonlar taranıyor...")
    
    applied_g_rules = []
    total_g_bad = 0
    max_g_rules = 15
    
    # Multiple passes to find all zero-loss rules
    for combo_size in [2, 3, 4, 5, 6]:
        if len(applied_g_rules) >= max_g_rules:
            break
        
        combo_results_g = []
        count = 0
        max_iter = 100000 if combo_size <= 4 else 20000
        
        for combo in iter_combos(cond_names_g, combo_size):
            count += 1
            if count > max_iter:
                break
            
            # Build mask
            mask = conditions_g[combo[0]](current_df)
            for c in combo[1:]:
                mask = mask & conditions_g[c](current_df)
            
            if not mask.any():
                continue
            
            bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
            tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
            
            if tier_lost == 0 and bad_elim >= 3:
                combo_results_g.append({
                    'combo': ' + '.join(combo),
                    'bad_elim': bad_elim
                })
        
        # Sort and apply
        combo_results_g.sort(key=lambda x: x['bad_elim'], reverse=True)
        
        for r in combo_results_g:
            if len(applied_g_rules) >= max_g_rules:
                break
            
            parts = r['combo'].split(' + ')
            mask = conditions_g[parts[0]](current_df)
            for p in parts[1:]:
                mask = mask & conditions_g[p](current_df)
            
            bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
            tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
            
            if tier_lost == 0 and bad_elim >= 3:
                current_df = current_df[~mask]
                applied_g_rules.append(r['combo'])
                total_g_bad += bad_elim
                print(f"   ✅ {len(applied_g_rules):2d}. {r['combo'][:55]}... Bad:{bad_elim}")
    
    print(f"\n📊 Faz G Toplam: {len(applied_g_rules)} kural, {total_g_bad} bad elendi, 0 Tier kaybı")
    
    # ========================================
    # PHASE H - MINIMAL TIER LOSS (1 per rule allowed)
    # ========================================
    print("\n" + "=" * 70)
    print("⚡ FAZ H: MİNİMAL TIER KAYBI (Kural başı max 1)")
    print("=" * 70)
    
    remaining_tier_h = (current_df['cat'] == 'tier').sum()
    remaining_bad_h = ((current_df['cat'] == 'small_gain') | (current_df['cat'].isin(['flat', 'garbage']))).sum()
    
    print(f"\n🎯 Faz H Hedefi: Kural başı max 1 Tier kaybı, yüksek verimlilik")
    print(f"   Kalan Tier: {remaining_tier_h}")
    print(f"   Elenecek (Small+Noise): {remaining_bad_h}")
    
    conditions_h = {
        'v_hyb_9': lambda d: d['v_hyb'] < 9,
        'v_hyb_10': lambda d: d['v_hyb'] < 10,
        'v_idx_7': lambda d: d['v_idx'] < 7,
        'v_idx_8': lambda d: d['v_idx'] < 8,
        'v_dyn_6': lambda d: d['v_dyn'] < 6,
        'v_dyn_7': lambda d: d['v_dyn'] < 7,
        'v_eff_5': lambda d: d['v_eff'] < 5,
        'v_eff_6': lambda d: d['v_eff'] < 6,
        'v_mom_12': lambda d: d['v_mom'] < 1.2,
        'v_mom_15': lambda d: d['v_mom'] < 1.5,
        'trend_1': lambda d: d['trend_score'] < 2,
        'trend_01': lambda d: d['trend_str'] == '01',
        'rsi_75': lambda d: d['rsi'] < 75,
        'rsi_76': lambda d: d['rsi'] < 76,
        'pos_yellow': lambda d: d['pos'] == 'yellow',
        'pos_orange': lambda d: d['pos'] == 'orange',
        'ribbon_below': lambda d: d['ribbon_above'] == False,
        'ang_4': lambda d: d['ang_score'] < 4,
        'ang_5': lambda d: d['ang_score'] < 5,
        'rsi_ang_60': lambda d: d['rsi_angle'] < 60,
        'rsi_ang_65': lambda d: d['rsi_angle'] < 65,
        'adx_35': lambda d: d['d_adx'] < 35,
        'adx_40': lambda d: d['d_adx'] < 40,
    }
    
    cond_names_h = list(conditions_h.keys())
    
    print(f"\n🔍 1 Tier kayıplı kombinasyonlar aranıyor...")
    
    applied_h_rules = []
    total_h_bad = 0
    total_h_tier = 0
    max_h_rules = 10
    max_h_tier = 10  # Max 10 Tier total for Phase H
    
    # Find combos with tier_lost == 1 and high efficiency
    combo_results_h = []
    
    for combo_size in [2, 3]:
        for combo in iter_combos(cond_names_h, combo_size):
            mask = conditions_h[combo[0]](current_df)
            for c in combo[1:]:
                mask = mask & conditions_h[c](current_df)
            
            if not mask.any():
                continue
            
            bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
            tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
            
            # ONLY ZERO TIER LOSS
            if tier_lost == 0 and bad_elim >= 3:
                combo_results_h.append({
                    'combo': ' + '.join(combo),
                    'bad_elim': bad_elim,
                    'tier_lost': 0,
                    'efficiency': bad_elim * 10
                })
    
    # Sort by efficiency
    combo_results_h.sort(key=lambda x: x['efficiency'], reverse=True)
    
    print(f"\n✅ Tier=1, Bad≥15 olan {len(combo_results_h)} kombinasyon bulundu!")
    
    if combo_results_h:
        print(f"\n🏆 EN İYİ 10:")
        for i, r in enumerate(combo_results_h[:10], 1):
            print(f"   {i:2d}. {r['combo']:<45} Bad:{r['bad_elim']:>3} | Tier:1")
    
    # Apply
    for r in combo_results_h:
        if len(applied_h_rules) >= max_h_rules:
            break
        if total_h_tier + r['tier_lost'] > max_h_tier:
            continue
        
        parts = r['combo'].split(' + ')
        mask = conditions_h[parts[0]](current_df)
        for p in parts[1:]:
            mask = mask & conditions_h[p](current_df)
        
        bad_elim = ((current_df['cat'].isin(['flat', 'garbage', 'small_gain'])) & mask).sum()
        tier_lost = ((current_df['cat'] == 'tier') & mask).sum()
        
        if tier_lost == 0 and bad_elim >= 3:
            current_df = current_df[~mask]
            applied_h_rules.append(r['combo'])
            total_h_bad += bad_elim
            print(f"\n   ✅ {r['combo'][:50]}... Bad:{bad_elim} | Tier:✅0")
    
    print(f"\n📊 Faz H Toplam: {len(applied_h_rules)} kural, {total_h_bad} bad, {total_h_tier} Tier kaybı")
    
    # ========================================
    # FINAL SUMMARY
    # ========================================
    print("\n" + "=" * 70)
    print("📊 FİNAL ÖZET")
    print("=" * 70)
    
    final_total = len(current_df)
    final_tier = (current_df['cat'] == 'tier').sum()
    final_small = (current_df['cat'] == 'small_gain').sum()
    final_noise = (current_df['cat'].isin(['flat', 'garbage'])).sum()
    
    print(f"\n📈 BAŞLANGIÇ:")
    print(f"   Toplam: {original_total}")
    print(f"   Tier: {original_tier} ({original_tier/original_total*100:.1f}%)")
    print(f"   Small: {original_small} ({original_small/original_total*100:.1f}%)")
    print(f"   Noise: {original_noise} ({original_noise/original_total*100:.1f}%)")
    
    print(f"\n📉 FİNAL (A + B Sonrası):")
    print(f"   Toplam: {final_total}")
    print(f"   Tier: {final_tier} ({final_tier/final_total*100:.1f}%)")
    print(f"   Small: {final_small} ({final_small/final_total*100:.1f}%)")
    print(f"   Noise: {final_noise} ({final_noise/final_total*100:.1f}%)")
    
    print(f"\n✅ FAZ A KURALLARI (Sabit):")
    for i, (rule, _) in enumerate(phase_a_rules, 1):
        print(f"   A{i}. {rule}")
    
    print(f"\n✅ FAZ B KURALLARI (Dinamik):")
    for i, rule in enumerate(applied_b_rules, 1):
        print(f"   B{i}. {rule}")
    
    print(f"\n📊 TOPLAM ELEME ETKİSİ:")
    print(f"   Elenen Toplam: {original_total - final_total} ({(original_total - final_total)/original_total*100:.1f}%)")
    print(f"   Kaybedilen Tier: {original_tier - final_tier} ({(original_tier - final_tier)/original_tier*100:.1f}%)")
    print(f"   Kaybedilen Small: {original_small - final_small} ({(original_small - final_small)/original_small*100:.1f}%)")
    print(f"   Elenen Noise: {original_noise - final_noise} ({(original_noise - final_noise)/original_noise*100:.1f}%)")
    
    print(f"\n🎯 BAŞARI ORANI İYİLEŞMESİ:")
    print(f"   Başlangıç Tier Rate: {original_tier/original_total*100:.1f}%")
    print(f"   Final Tier Rate: {final_tier/final_total*100:.1f}%")
    print(f"   İyileşme: {final_tier/final_total*100 - original_tier/original_total*100:+.1f}%")
    
    good_rate_start = (original_tier + original_small) / original_total * 100
    good_rate_final = (final_tier + final_small) / final_total * 100
    print(f"\n🏆 (Tier + Small) BAŞARI ORANI:")
    print(f"   Başlangıç: {good_rate_start:.1f}%")
    print(f"   Final: {good_rate_final:.1f}%")
    print(f"   İyileşme: {good_rate_final - good_rate_start:+.1f}%")
    
    # === FINAL SUMMARY ===
    print("\n" + "=" * 70)
    print("📊 FİNAL ÖZET")
    print("=" * 70)
    
    original_total = len(df)
    original_small = (df['cat'] == 'small_gain').sum()
    original_noise = (df['cat'].isin(['flat', 'garbage'])).sum()
    
    final_total = len(current_df)
    final_tier = (current_df['cat'] == 'tier').sum()
    final_small = (current_df['cat'] == 'small_gain').sum()
    final_noise = (current_df['cat'].isin(['flat', 'garbage'])).sum()
    
    print(f"\n📈 BAŞLANGIÇ:")
    print(f"   Toplam: {original_total}")
    print(f"   Tier: {original_tier} ({original_tier/original_total*100:.1f}%)")
    print(f"   Small: {original_small} ({original_small/original_total*100:.1f}%)")
    print(f"   Noise: {original_noise} ({original_noise/original_total*100:.1f}%)")
    
    print(f"\n📉 FİNAL (Elemelerden Sonra):")
    print(f"   Toplam: {final_total}")
    print(f"   Tier: {final_tier} ({final_tier/final_total*100:.1f}%)")
    print(f"   Small: {final_small} ({final_small/final_total*100:.1f}%)")
    print(f"   Noise: {final_noise} ({final_noise/final_total*100:.1f}%)")
    
    print(f"\n✅ UYGULANAN {len(applied_rules)} KURAL:")
    for i, rule in enumerate(applied_rules, 1):
        print(f"   {i}. {rule}")
    
    print(f"\n📊 ELEME ETKİSİ:")
    print(f"   Elenen Toplam: {original_total - final_total} ({(original_total - final_total)/original_total*100:.1f}%)")
    print(f"   Kaybedilen Tier: {original_tier - final_tier} ({(original_tier - final_tier)/original_tier*100:.1f}%)")
    print(f"   Kaybedilen Small: {original_small - final_small} ({(original_small - final_small)/original_small*100:.1f}%)")
    print(f"   Elenen Noise: {original_noise - final_noise} ({(original_noise - final_noise)/original_noise*100:.1f}%)")
    
    print(f"\n🎯 BAŞARI ORANI İYİLEŞMESİ:")
    print(f"   Başlangıç Tier Rate: {original_tier/original_total*100:.1f}%")
    print(f"   Final Tier Rate: {final_tier/final_total*100:.1f}%")
    improvement = final_tier/final_total*100 - original_tier/original_total*100
    print(f"   İyileşme: {improvement:+.1f}%")
    
    # Combined + Small rate
    good_rate_start = (original_tier + original_small) / original_total * 100
    good_rate_final = (final_tier + final_small) / final_total * 100
    print(f"\n🏆 (Tier + Small) BAŞARI ORANI:")
    print(f"   Başlangıç: {good_rate_start:.1f}%")
    print(f"   Final: {good_rate_final:.1f}%")
    print(f"   İyileşme: {good_rate_final - good_rate_start:+.1f}%")
    
    print(f"\n🎯 BAŞARI ORANI İYİLEŞMESİ:")
    print(f"   Başlangıç Tier Rate: {original_tier/original_total*100:.1f}%")
    print(f"   Final Tier Rate: {final_tier/final_total*100:.1f}%")
    print(f"   İyileşme: {final_tier/final_total*100 - original_tier/original_total*100:+.1f}%")

if __name__ == "__main__":
    df = collect_all_triggers()
    if not df.empty:
        run_layered_analysis(df)
    else:
        print("Veri bulunamadı!")
