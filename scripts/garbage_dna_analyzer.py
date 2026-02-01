#!/usr/bin/env python3
"""
ÇÖP DNA ANALİZİ - Dahi Modu v3
Hedef: Tier ve küçük kazançlara SIFIR zarar vererek çöpü temizle
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
    print("🧠 ÇÖP DNA ANALİZİ - Dahi Modu v3")
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

            # Indicators
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
                        
                        # Trend (4H, 1H)
                        cutoff_4h = trig_time - pd.Timedelta(hours=4)
                        last_4h = df_4h[df_4h.index <= cutoff_4h]
                        t4 = 1 if not last_4h.empty and last_4h.iloc[-1]['close'] > last_4h.iloc[-1]['ema21'] else 0
                        
                        cutoff_1h = trig_time - pd.Timedelta(hours=1)
                        last_1h = df_1h[df_1h.index <= cutoff_1h]
                        t1 = 1 if not last_1h.empty and last_1h.iloc[-1]['close'] > last_1h.iloc[-1]['ema21'] else 0
                        
                        trend_score = t4 + t1  # 0, 1, 2
                        trend_str = f"{t4}{t1}"  # "00", "01", "10", "11"

                        # Volume metrics
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
                        
                        # Ribbon
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
                        
                        # Position
                        if curr_v < 30: pos = "black"
                        elif curr_v < 50: pos = "red"
                        elif curr_v < 60: pos = "yellow"
                        elif curr_v < 70: pos = "green"
                        else: pos = "orange"
                        
                        # ATR
                        atr21_val = df_15m['atr21'].values[i]
                        close_val = df_15m['close'].values[i]
                        atr_adj = (atr21_val / close_val) * 100 if close_val > 0 else 0
                        
                        # RSI-EMA Angle
                        rsi_ema_now = df_15m['rsi_ema'].values[i]
                        rsi_ema_prev = df_15m['rsi_ema'].values[i-1] if i > 0 else rsi_ema_now
                        rsi_slope = rsi_ema_now - rsi_ema_prev
                        rsi_angle = math.degrees(math.atan(rsi_slope))
                        
                        # RSI value
                        rsi_val = df_15m['rsi'].values[i]
                        
                        # Peak calculation
                        next_triggers = all_trigger_indices[all_trigger_indices > i]
                        next_t_idx = next_triggers[0] if len(next_triggers) > 0 else len(df_15m)
                        search_limit = min(i + 22, next_t_idx)
                        
                        if i + 1 < len(df_15m):
                            val_slice = df_15m['high'].values[i + 1 : search_limit + 1]
                            peak_p = val_slice.max() if len(val_slice) > 0 else df_15m['close'].values[i]
                        else:
                            peak_p = df_15m['close'].values[i]
                        
                        peak_pct = ((peak_p / df_15m['close'].values[i]) - 1) * 100
                        
                        # Category
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

def analyze_garbage_dna(df):
    print(f"\n📊 GENEL DAĞILIM")
    print("=" * 50)
    print(df['cat'].value_counts())
    
    total = len(df)
    tier_count = (df['cat'] == 'tier').sum()
    small_gain_count = (df['cat'] == 'small_gain').sum()
    flat_count = (df['cat'] == 'flat').sum()
    garbage_count = (df['cat'] == 'garbage').sum()
    
    print(f"\nTier (≥5%): {tier_count} ({tier_count/total*100:.1f}%)")
    print(f"Small Gain (2-5%): {small_gain_count} ({small_gain_count/total*100:.1f}%)")
    print(f"Flat (0-2%): {flat_count} ({flat_count/total*100:.1f}%)")
    print(f"Garbage (<0%): {garbage_count} ({garbage_count/total*100:.1f}%)")
    
    # Define categories
    df['is_tier'] = df['cat'] == 'tier'  # MUTLAK KORU
    df['is_small'] = df['cat'] == 'small_gain'  # Az kayıp kabul edilebilir
    df['is_noise'] = df['cat'].isin(['flat', 'garbage'])  # ELE
    
    print("\n" + "=" * 70)
    print("🔬 ELEME ANALİZİ: Noise (Flat+Garbage) vs Tier")
    print("=" * 70)
    
    tier_df = df[df['is_tier']]
    small_df = df[df['is_small']]
    noise_df = df[df['is_noise']]
    
    print(f"\nTier (KORU): {len(tier_df)}")
    print(f"Small Gain (az kayıp OK): {len(small_df)}")
    print(f"Noise (ELE): {len(noise_df)}")
    
    # Analyze each feature
    features_to_analyze = [
        ('trend_str', 'categorical'),
        ('trend_score', 'numeric'),
        ('pos', 'categorical'),
        ('ribbon_above', 'boolean'),
        ('ang_score', 'numeric'),
        ('rsi_angle', 'numeric'),
        ('rsi', 'numeric'),
        ('v_idx', 'numeric'),
        ('v_dyn', 'numeric'),
        ('v_mom', 'numeric'),
        ('v_eff', 'numeric'),
        ('v_hyb', 'numeric'),
        ('atr_adj', 'numeric'),
        ('d_atr', 'numeric'),
        ('d_adx', 'numeric'),
        ('is_ayas', 'boolean')
    ]
    
    print("\n" + "-" * 70)
    print("NÜMERİK ÖZELLİKLER: Tier vs Noise Ortalamaları")
    print("-" * 70)
    
    for feat, ftype in features_to_analyze:
        if ftype == 'numeric':
            tier_mean = tier_df[feat].mean()
            noise_mean = noise_df[feat].mean()
            diff_pct = ((noise_mean - tier_mean) / (tier_mean + 0.001)) * 100
            flag = "⚠️" if abs(diff_pct) > 20 else ""
            print(f"{feat:15s}: Tier={tier_mean:7.2f} | Noise={noise_mean:7.2f} | Fark={diff_pct:+.1f}% {flag}")
    
    # FIND SAFE ELIMINATION RULES
    print("\n" + "=" * 70)
    print("🎯 ELEME KURALLARI ARAMA")
    print("=" * 70)
    print("Hedef: Tier kaybı = 0, Small Gain kaybı minimumda tutarak maksimum Noise ele\n")
    
    # Test various elimination rules
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
        ("atr_adj < 0.3", df['atr_adj'] < 0.3),
        ("atr_adj < 0.5", df['atr_adj'] < 0.5),
        ("atr_adj < 0.8", df['atr_adj'] < 0.8),
        ("atr_adj < 1.0", df['atr_adj'] < 1.0),
        ("d_atr < 3", df['d_atr'] < 3),
        ("d_atr < 4", df['d_atr'] < 4),
        ("d_atr < 5", df['d_atr'] < 5),
        ("d_adx < 20", df['d_adx'] < 20),
        ("d_adx < 25", df['d_adx'] < 25),
        ("d_adx < 30", df['d_adx'] < 30),
        ("is_ayas == False", df['is_ayas'] == False),
    ]
    
    results = []
    
    print(f"{'Kural':<25} {'Noise Elenen':<15} {'Tier Kaybı':<15} {'Small Kaybı':<15} {'NET KAZANÇ':<10}")
    print("-" * 85)
    
    for rule_name, rule_mask in rules_to_test:
        noise_eliminated = (rule_mask & df['is_noise']).sum()
        noise_pct = noise_eliminated / len(noise_df) * 100 if len(noise_df) > 0 else 0
        
        tier_lost = (rule_mask & df['is_tier']).sum()
        tier_pct = tier_lost / len(tier_df) * 100 if len(tier_df) > 0 else 0
        
        small_lost = (rule_mask & df['is_small']).sum()
        small_pct = small_lost / len(small_df) * 100 if len(small_df) > 0 else 0
        
        # Net gain = Noise eliminated - (Tier lost * 100 + Small lost * 10)
        # Heavy penalty for Tier loss, light penalty for Small loss
        net_gain = noise_eliminated - (tier_lost * 100) - (small_lost * 2)
        
        tier_safe = "✅" if tier_lost == 0 else f"❌{tier_lost}"
        
        if noise_pct > 1:  # Only show rules that eliminate some noise
            print(f"{rule_name:<25} {noise_eliminated:>5} ({noise_pct:>5.1f}%)    {tier_safe:<10}    {small_lost:>5} ({small_pct:>5.1f}%)    {net_gain:>6.0f}")
        
        results.append({
            'rule': rule_name,
            'noise_eliminated': noise_eliminated,
            'noise_pct': noise_pct,
            'tier_lost': tier_lost,
            'tier_pct': tier_pct,
            'small_lost': small_lost,
            'small_pct': small_pct,
            'net_gain': net_gain
        })
    
    # Sort by net gain and find best rules with 0 tier loss
    results_df = pd.DataFrame(results)
    
    print("\n" + "=" * 70)
    print("✅ TIER KAYBI SIFIR OLAN EN İYİ KURALLAR")
    print("=" * 70)
    
    zero_tier_loss = results_df[results_df['tier_lost'] == 0].sort_values('noise_eliminated', ascending=False)
    print(zero_tier_loss.head(15).to_string(index=False))
    
    print("\n" + "=" * 70)
    print("🎯 ÇOK DÜŞÜK TIER KAYBI (≤5) OLAN EN İYİ KURALLAR")
    print("=" * 70)
    
    low_tier_loss = results_df[results_df['tier_lost'] <= 5].sort_values('net_gain', ascending=False)
    print(low_tier_loss.head(15).to_string(index=False))
    
    # Coin-specific analysis
    print("\n" + "=" * 70)
    print("📌 COİN BAZLI ANALİZ: En çok çöp üreten coinler")
    print("=" * 70)
    
    coin_stats = df.groupby('symbol').agg({
        'cat': lambda x: (x == 'garbage').sum(),
        'is_good': 'sum',
        'peak_pct': 'mean'
    }).rename(columns={'cat': 'garbage_count', 'is_good': 'good_count'})
    
    coin_stats['total'] = coin_stats['garbage_count'] + coin_stats['good_count']
    coin_stats['garbage_rate'] = coin_stats['garbage_count'] / (coin_stats['total'] + 1) * 100
    
    worst_coins = coin_stats[coin_stats['total'] >= 10].sort_values('garbage_rate', ascending=False).head(20)
    print("\nEn kötü coinler (>%80 garbage rate):")
    print(worst_coins[worst_coins['garbage_rate'] > 80].to_string())
    
    # Save results
    df.to_csv('/Users/alisaglam/TezaverMac/garbage_dna_analysis.csv', index=False)
    print("\n📁 Ham veri garbage_dna_analysis.csv'ye kaydedildi.")

if __name__ == "__main__":
    df = collect_all_triggers()
    if not df.empty:
        analyze_garbage_dna(df)
    else:
        print("Veri bulunamadı!")
