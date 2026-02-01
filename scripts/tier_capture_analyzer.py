#!/usr/bin/env python3
"""
TIER CAPTURE ANALYZER - Dahi Modu v2
Günlük bazda Tier yakalama oranı analizi
Daha yüksek kombinasyonlar (5-6-7li)
"""

import pandas as pd
import numpy as np
import os
import json
import math
from datetime import datetime
from itertools import combinations

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

def collect_triggers():
    print("=" * 70)
    print("🧠 DAHİ MODU v2 - GÜNLÜK TIER YAKALAMA ANALİZİ")
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
                        
                        if val_20 > val_55:
                            curr_v, prev_v = val_20, val_20_prev
                            ribbon_pos = "above"
                        else:
                            curr_v, prev_v = val_55, val_55_prev
                            ribbon_pos = "below"
                            
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
                        
                        next_triggers = all_trigger_indices[all_trigger_indices > i]
                        next_t_idx = next_triggers[0] if len(next_triggers) > 0 else len(df_15m)
                        search_limit = min(i + 22, next_t_idx)
                        
                        if i + 1 < len(df_15m):
                            val_slice = df_15m['high'].values[i + 1 : search_limit + 1]
                            peak_p = val_slice.max() if len(val_slice) > 0 else df_15m['close'].values[i]
                        else:
                            peak_p = df_15m['close'].values[i]
                        
                        peak_pct = ((peak_p / df_15m['close'].values[i]) - 1) * 100
                        
                        if peak_pct >= 30: tier = "diamond"
                        elif peak_pct >= 20: tier = "gold"
                        elif peak_pct >= 10: tier = "silver"
                        elif peak_pct >= 5: tier = "bronze"
                        else: tier = "none"
                        
                        is_tier = tier != "none"
                        
                        all_triggers.append({
                            'symbol': symbol, 'date': current.strftime('%Y-%m-%d'),
                            'is_ayas': is_ayas, 'trend_score': trend_score, 'pos': pos,
                            'ang_score': ang_score, 'rsi_angle': rsi_angle,
                            'v_idx': v_idx, 'v_dyn': v_dyn, 'v_mom': v_mom, 'v_eff': v_eff, 'v_hyb': v_hyb,
                            'atr_adj': atr_adj, 'd_atr': d_atr, 'd_adx': d_adx,
                            'ribbon_pos': ribbon_pos, 'peak_pct': peak_pct, 'tier': tier, 'is_tier': is_tier
                        })
                            
                except: pass
                current += pd.Timedelta(days=1)
        except: continue
    
    return pd.DataFrame(all_triggers)

def analyze_daily_capture(df):
    print(f"\nToplam Tetik: {len(df)}")
    print(f"Tier Olanlar: {df['is_tier'].sum()} ({df['is_tier'].mean()*100:.1f}%)")
    
    # Binary features
    df['f_ayas'] = df['is_ayas']
    df['f_trend2'] = df['trend_score'] == 2
    df['f_trend1'] = df['trend_score'] >= 1
    df['f_pos_green'] = df['pos'] == 'green'
    df['f_pos_yg'] = df['pos'].isin(['yellow', 'green'])
    df['f_ang3'] = df['ang_score'] >= 3.0
    df['f_ang0'] = df['ang_score'] > 0
    df['f_rang45'] = df['rsi_angle'] >= 45
    df['f_rang10'] = df['rsi_angle'] >= 10
    df['f_vrsi10'] = df['v_hyb'] >= 10
    df['f_vrsi9'] = df['v_hyb'] >= 9
    df['f_vrsi7'] = df['v_hyb'] >= 7
    df['f_vboy8'] = df['v_eff'] >= 8
    df['f_vboy7'] = df['v_eff'] >= 7
    df['f_vboy5'] = df['v_eff'] >= 5
    df['f_v100_9'] = df['v_idx'] >= 9
    df['f_v100_7'] = df['v_idx'] >= 7
    df['f_v100_5'] = df['v_idx'] >= 5
    df['f_v21_9'] = df['v_dyn'] >= 9
    df['f_v21_7'] = df['v_dyn'] >= 7
    df['f_v21_5'] = df['v_dyn'] >= 5
    df['f_vmom2'] = df['v_mom'] >= 2.0
    df['f_vmom15'] = df['v_mom'] >= 1.5
    df['f_vmom12'] = df['v_mom'] >= 1.2
    df['f_atr3'] = df['atr_adj'] >= 3.0
    df['f_atr2'] = df['atr_adj'] >= 2.0
    df['f_atr15'] = df['atr_adj'] >= 1.5
    df['f_adx50'] = df['d_adx'] >= 50
    df['f_adx40'] = df['d_adx'] >= 40
    df['f_adx25'] = df['d_adx'] >= 25
    df['f_ribbon'] = df['ribbon_pos'] == 'above'
    
    features = [c for c in df.columns if c.startswith('f_')]
    
    # DAILY BREAKDOWN
    print("\n" + "=" * 70)
    print("📅 GÜNLÜK TIER DAĞILIMI")
    print("=" * 70)
    
    daily_stats = df.groupby('date').agg({
        'is_tier': ['count', 'sum']
    }).reset_index()
    daily_stats.columns = ['date', 'total_triggers', 'tier_count']
    daily_stats['tier_rate'] = (daily_stats['tier_count'] / daily_stats['total_triggers'] * 100).round(1)
    print(daily_stats.to_string(index=False))
    
    total_days = len(daily_stats)
    total_tiers = daily_stats['tier_count'].sum()
    
    print(f"\n📊 ÖZET: {total_days} gün, toplam {total_tiers} Tier tetik")
    
    # FIND BEST FILTER FOR MAXIMUM CAPTURE
    print("\n" + "=" * 70)
    print("🎯 MAKSİMUM YAKALAMA ANALİZİ")
    print("=" * 70)
    print("Her kombinasyon için: (Tier yakalama sayısı, Precision, Günlük dağılım)")
    
    def evaluate_filter(mask):
        """Returns: n_caught, precision, unique_days, daily_coverage"""
        caught = df[mask & df['is_tier']]
        n_caught = len(caught)
        n_triggered = mask.sum()
        precision = (n_caught / n_triggered * 100) if n_triggered > 0 else 0
        unique_days = caught['date'].nunique() if n_caught > 0 else 0
        return n_caught, precision, unique_days, n_triggered
    
    # Test progressively larger combinations
    # To avoid explosion, use greedy approach: start with best singles, build up
    
    print("\n--- TEK FAKTÖRLER (Yakalama Gücüne Göre) ---")
    single_results = []
    for f in features:
        mask = df[f] == True
        n_caught, prec, days, n_trig = evaluate_filter(mask)
        if n_caught > 0:
            single_results.append({
                'filter': f, 'caught': n_caught, 'precision': prec, 
                'days': days, 'triggered': n_trig
            })
    
    single_df = pd.DataFrame(single_results).sort_values('caught', ascending=False)
    print(single_df.head(15).to_string(index=False))
    
    # GREEDY COMBINATION BUILDING
    print("\n" + "=" * 70)
    print("🔬 OPTİMAL KOMBİNASYON ARAMA (2-7'li)")
    print("=" * 70)
    
    # Use all filters that have at least some tier catches
    active_filters = [r['filter'] for r in single_results if r['caught'] >= 10]
    
    best_combos = []
    
    # Test 2-7 combinations
    for combo_size in range(2, 8):
        if combo_size > len(active_filters):
            break
        
        # Limit to most promising filters for higher combos
        if combo_size <= 4:
            test_filters = active_filters[:20]  # Top 20
        else:
            test_filters = active_filters[:15]  # Top 15 for larger combos
        
        combo_results = []
        max_combos = 5000  # Limit to avoid explosion
        combo_count = 0
        
        for combo in combinations(test_filters, combo_size):
            combo_count += 1
            if combo_count > max_combos:
                break
                
            mask = pd.Series([True] * len(df))
            for f in combo:
                mask = mask & (df[f] == True)
            
            n_caught, prec, days, n_trig = evaluate_filter(mask)
            
            if n_caught >= 2:  # Lower threshold
                combo_results.append({
                    'combo': ' + '.join([f.replace('f_','') for f in combo]),
                    'size': combo_size,
                    'caught': n_caught,
                    'precision': round(prec, 1),
                    'days': days,
                    'triggered': n_trig
                })
        
        if combo_results:
            combo_df = pd.DataFrame(combo_results)
            
            # Sort by precision first, then by caught
            combo_df = combo_df.sort_values(['precision', 'caught'], ascending=[False, False])
            
            print(f"\n--- {combo_size}'Lİ KOMBİNASYONLAR (En iyi 10) ---")
            print(combo_df.head(10).to_string(index=False))
            
            # Keep top 5 from each size
            best_combos.extend(combo_df.head(5).to_dict('records'))
    
    # FINAL RANKING
    print("\n" + "=" * 70)
    print("🏆 EN İYİ FİLTRELER (Tüm Boyutlar)")
    print("=" * 70)
    
    if best_combos:
        final_df = pd.DataFrame(best_combos)
        
        # Score = precision * log(caught) to balance both
        final_df['score'] = final_df['precision'] * np.log1p(final_df['caught'])
        final_df = final_df.sort_values('score', ascending=False)
        
        print("\n--- PRECISION ODAKLI (%100'e yakın) ---")
        prec_focus = final_df[final_df['precision'] >= 90].sort_values('caught', ascending=False).head(10)
        if not prec_focus.empty:
            print(prec_focus.to_string(index=False))
        else:
            print("90%+ precision bulunamadı, 80%+ gösteriliyor:")
            print(final_df[final_df['precision'] >= 80].sort_values('caught', ascending=False).head(10).to_string(index=False))
        
        print("\n--- YAKALAMA ODAKLI (En çok Tier) ---")
        catch_focus = final_df[final_df['precision'] >= 60].sort_values('caught', ascending=False).head(10)
        print(catch_focus.to_string(index=False))
        
        print("\n--- BALANCE (En iyi skor) ---")
        print(final_df.head(10).to_string(index=False))
        
        # Save
        final_df.to_csv('/Users/alisaglam/TezaverMac/tier_capture_analysis.csv', index=False)
        print("\n📁 Sonuçlar tier_capture_analysis.csv'ye kaydedildi.")
    
    # Show daily capture for best filter
    if best_combos:
        best = final_df.iloc[0]
        print("\n" + "=" * 70)
        print(f"📅 EN İYİ FİLTRE GÜNLÜK PERFORMANSI: {best['combo']}")
        print("=" * 70)
        
        # Recreate mask for best filter
        best_filters = ['f_' + f.strip() for f in best['combo'].split(' + ')]
        mask = pd.Series([True] * len(df))
        for f in best_filters:
            mask = mask & (df[f] == True)
        
        caught_df = df[mask & df['is_tier']]
        daily_caught = caught_df.groupby('date').size().reset_index(name='caught')
        
        # Merge with total tiers
        daily_full = daily_stats.merge(daily_caught, on='date', how='left').fillna(0)
        daily_full['caught'] = daily_full['caught'].astype(int)
        daily_full['capture_rate'] = (daily_full['caught'] / daily_full['tier_count'] * 100).round(1)
        daily_full['capture_rate'] = daily_full['capture_rate'].fillna(0)
        
        print(daily_full.to_string(index=False))

if __name__ == "__main__":
    df = collect_triggers()
    if not df.empty:
        analyze_daily_capture(df)
    else:
        print("Veri bulunamadı!")
