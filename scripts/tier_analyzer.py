#!/usr/bin/env python3
"""
TIER ANALYZER - Dahi Modu
Hangi gösterge kombinasyonları en yüksek Tier oranı veriyor?
"""

import pandas as pd
import numpy as np
import os
import json
import math
from datetime import datetime
from itertools import combinations

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

# Analiz periyodu
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

def analyze_triggers():
    print("=" * 60)
    print("🧠 DAHİ MODU - TIER ANALİZİ")
    print("=" * 60)
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    all_triggers = []
    
    start_d = pd.Timestamp(START_DATE)
    end_d = pd.Timestamp(END_DATE) + pd.Timedelta(days=1)
    
    print(f"Tarih Aralığı: {START_DATE} -> {END_DATE}")
    print(f"Coin Sayısı: {len(symbols)}")
    print("Analiz başlıyor...")
    
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
            
            ribbon_periods = [20, 25, 30, 35, 40, 45, 50, 55]
            for p in ribbon_periods:
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
                    
                    # Process all triggers, but mark if Ayaş
                    current_utc = current.normalize()
                    day_mask = (df_15m.index.normalize() == current_utc)
                    target_day_data = df_15m[day_mask]
                    if target_day_data.empty:
                        current += pd.Timedelta(days=1); continue

                    # Get Daily ATR and ADX
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
                        
                        is_trigger = i in all_trigger_indices
                        if is_trigger:
                            trig_time = df_15m.index[i]
                            
                            # Trend
                            cutoff_4h = trig_time - pd.Timedelta(hours=4)
                            last_4h = df_4h[df_4h.index <= cutoff_4h]
                            t4 = 1 if not last_4h.empty and last_4h.iloc[-1]['close'] > last_4h.iloc[-1]['ema21'] else 0
                            
                            cutoff_1h = trig_time - pd.Timedelta(hours=1)
                            last_1h = df_1h[df_1h.index <= cutoff_1h]
                            t1 = 1 if not last_1h.empty and last_1h.iloc[-1]['close'] > last_1h.iloc[-1]['ema21'] else 0
                            
                            trend_score = t4 + t1  # 0, 1, 2

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
                            
                            # Ribbon Angle
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
                            
                            # Peak calculation
                            next_triggers = all_trigger_indices[all_trigger_indices > i]
                            next_t_idx = next_triggers[0] if len(next_triggers) > 0 else len(df_15m)
                            search_limit = min(i + 22, next_t_idx)
                            
                            if i + 1 < len(df_15m):
                                val_slice = df_15m['high'].values[i + 1 : search_limit + 1]
                                if len(val_slice) > 0:
                                    peak_p = val_slice.max()
                                else:
                                    peak_p = df_15m['close'].values[i]
                            else:
                                peak_p = df_15m['close'].values[i]
                            
                            peak_pct = ((peak_p / df_15m['close'].values[i]) - 1) * 100
                            
                            # Tier classification
                            if peak_pct >= 30: tier = "diamond"
                            elif peak_pct >= 20: tier = "gold"
                            elif peak_pct >= 10: tier = "silver"
                            elif peak_pct >= 5: tier = "bronze"
                            else: tier = "none"
                            
                            is_tier = tier != "none"
                            
                            all_triggers.append({
                                'symbol': symbol,
                                'date': current,
                                'is_ayas': is_ayas,
                                'trend_score': trend_score,
                                'pos': pos,
                                'ang_score': ang_score,
                                'rsi_angle': rsi_angle,
                                'v_idx': v_idx,
                                'v_dyn': v_dyn,
                                'v_mom': v_mom,
                                'v_eff': v_eff,
                                'v_hyb': v_hyb,
                                'atr_adj': atr_adj,
                                'd_atr': d_atr,
                                'd_adx': d_adx,
                                'ribbon_pos': ribbon_pos,
                                'peak_pct': peak_pct,
                                'tier': tier,
                                'is_tier': is_tier
                            })
                            
                except Exception as e:
                    pass
                current += pd.Timedelta(days=1)
        except: continue
    
    # Analysis
    df = pd.DataFrame(all_triggers)
    
    if df.empty:
        print("Veri bulunamadı!")
        return
    
    print(f"\nToplam Tetik: {len(df)}")
    print(f"Tier Olanlar: {df['is_tier'].sum()} ({df['is_tier'].mean()*100:.1f}%)")
    
    # Create binary features for combination analysis
    df['trend_2'] = df['trend_score'] == 2
    df['trend_1plus'] = df['trend_score'] >= 1
    df['pos_green'] = df['pos'] == 'green'
    df['pos_yellow_plus'] = df['pos'].isin(['yellow', 'green', 'orange'])
    df['ang_high'] = df['ang_score'] >= 3.0
    df['ang_pos'] = df['ang_score'] > 0
    df['rsi_ang_high'] = df['rsi_angle'] >= 45
    df['rsi_ang_pos'] = df['rsi_angle'] > 10
    
    # Vrsi (v_hyb) thresholds
    df['vrsi_10plus'] = df['v_hyb'] >= 10.0
    df['vrsi_9plus'] = df['v_hyb'] >= 9.0
    df['vrsi_7plus'] = df['v_hyb'] >= 7.0
    
    # VBoy (v_eff) thresholds
    df['vboy_8plus'] = df['v_eff'] >= 8.0
    df['vboy_7plus'] = df['v_eff'] >= 7.0
    df['vboy_5plus'] = df['v_eff'] >= 5.0
    
    # V100 (v_idx) thresholds
    df['v100_9plus'] = df['v_idx'] >= 9.0
    df['v100_7plus'] = df['v_idx'] >= 7.0
    df['v100_5plus'] = df['v_idx'] >= 5.0
    
    # V21 (v_dyn) thresholds
    df['v21_9plus'] = df['v_dyn'] >= 9.0
    df['v21_7plus'] = df['v_dyn'] >= 7.0
    df['v21_5plus'] = df['v_dyn'] >= 5.0
    
    # V-Mom thresholds
    df['vmom_2plus'] = df['v_mom'] >= 2.0
    df['vmom_1_5plus'] = df['v_mom'] >= 1.5
    df['vmom_1_2plus'] = df['v_mom'] >= 1.2
    
    # ATR thresholds
    df['atr_3plus'] = df['atr_adj'] >= 3.0
    df['atr_2plus'] = df['atr_adj'] >= 2.0
    df['atr_1_5plus'] = df['atr_adj'] >= 1.5
    
    # ADX thresholds
    df['adx_50plus'] = df['d_adx'] >= 50
    df['adx_40plus'] = df['d_adx'] >= 40
    df['adx_25plus'] = df['d_adx'] >= 25
    
    df['ribbon_above'] = df['ribbon_pos'] == 'above'
    
    features = [
        'is_ayas', 'trend_2', 'trend_1plus', 'pos_green', 'pos_yellow_plus',
        'ang_high', 'ang_pos', 'rsi_ang_high', 'rsi_ang_pos',
        # Vrsi
        'vrsi_10plus', 'vrsi_9plus', 'vrsi_7plus',
        # VBoy
        'vboy_8plus', 'vboy_7plus', 'vboy_5plus',
        # V100
        'v100_9plus', 'v100_7plus', 'v100_5plus',
        # V21
        'v21_9plus', 'v21_7plus', 'v21_5plus',
        # V-Mom
        'vmom_2plus', 'vmom_1_5plus', 'vmom_1_2plus',
        # ATR
        'atr_3plus', 'atr_2plus', 'atr_1_5plus',
        # ADX
        'adx_50plus', 'adx_40plus', 'adx_25plus',
        'ribbon_above'
    ]
    
    print("\n" + "=" * 60)
    print("📊 TEK FAKTÖR ANALİZİ")
    print("=" * 60)
    
    single_results = []
    for feat in features:
        mask = df[feat] == True
        n = mask.sum()
        if n > 0:
            tier_rate = df.loc[mask, 'is_tier'].mean() * 100
            avg_peak = df.loc[mask, 'peak_pct'].mean()
            single_results.append({
                'feature': feat,
                'count': n,
                'tier_rate': tier_rate,
                'avg_peak': avg_peak
            })
    
    single_df = pd.DataFrame(single_results).sort_values('tier_rate', ascending=False)
    print(single_df.to_string(index=False))
    
    print("\n" + "=" * 60)
    print("🔬 İKİLİ KOMBİNASYON ANALİZİ (En İyi 20)")
    print("=" * 60)
    
    combo_results = []
    for combo in combinations(features, 2):
        mask = (df[combo[0]] == True) & (df[combo[1]] == True)
        n = mask.sum()
        if n >= 10:  # Minimum sample size
            tier_rate = df.loc[mask, 'is_tier'].mean() * 100
            avg_peak = df.loc[mask, 'peak_pct'].mean()
            combo_results.append({
                'combo': f"{combo[0]} + {combo[1]}",
                'count': n,
                'tier_rate': tier_rate,
                'avg_peak': avg_peak
            })
    
    combo_df = pd.DataFrame(combo_results).sort_values('tier_rate', ascending=False).head(20)
    print(combo_df.to_string(index=False))
    
    print("\n" + "=" * 60)
    print("💎 ÜÇLÜ KOMBİNASYON ANALİZİ (En İyi 20)")
    print("=" * 60)
    
    triple_results = []
    for combo in combinations(features, 3):
        mask = (df[combo[0]] == True) & (df[combo[1]] == True) & (df[combo[2]] == True)
        n = mask.sum()
        if n >= 5:  # Minimum sample size for 3-way
            tier_rate = df.loc[mask, 'is_tier'].mean() * 100
            avg_peak = df.loc[mask, 'peak_pct'].mean()
            triple_results.append({
                'combo': f"{combo[0]} + {combo[1]} + {combo[2]}",
                'count': n,
                'tier_rate': tier_rate,
                'avg_peak': avg_peak
            })
    
    triple_df = pd.DataFrame(triple_results).sort_values('tier_rate', ascending=False).head(20)
    print(triple_df.to_string(index=False))
    
    print("\n" + "=" * 60)
    print("🏆 DÖRTLÜ KOMBİNASYON ANALİZİ (En İyi 20)")
    print("=" * 60)
    
    quad_results = []
    for combo in combinations(features, 4):
        mask = (df[combo[0]] == True) & (df[combo[1]] == True) & (df[combo[2]] == True) & (df[combo[3]] == True)
        n = mask.sum()
        if n >= 3:  # Minimum sample size for 4-way
            tier_rate = df.loc[mask, 'is_tier'].mean() * 100
            avg_peak = df.loc[mask, 'peak_pct'].mean()
            quad_results.append({
                'combo': f"{combo[0]} + {combo[1]} + {combo[2]} + {combo[3]}",
                'count': n,
                'tier_rate': tier_rate,
                'avg_peak': avg_peak
            })
    
    quad_df = pd.DataFrame(quad_results).sort_values('tier_rate', ascending=False).head(20)
    print(quad_df.to_string(index=False))
    
    # Find the best combination with 100% tier rate
    print("\n" + "=" * 60)
    print("✨ %100 TIER ORANI OLAN KOMBİNASYONLAR")
    print("=" * 60)
    
    all_combos = pd.concat([
        single_df.rename(columns={'feature': 'combo'}),
        combo_df,
        triple_df,
        quad_df
    ], ignore_index=True)
    
    perfect = all_combos[all_combos['tier_rate'] == 100.0].sort_values('count', ascending=False)
    if not perfect.empty:
        print(perfect.to_string(index=False))
    else:
        print("❌ %100 Tier oranı sağlayan kombinasyon bulunamadı.")
        print("\nEn yüksek Tier oranları:")
        best = all_combos.sort_values('tier_rate', ascending=False).head(10)
        print(best.to_string(index=False))
    
    # Save results
    all_combos.sort_values('tier_rate', ascending=False).to_csv('/Users/alisaglam/TezaverMac/tier_analysis_results.csv', index=False)
    print("\n📁 Sonuçlar tier_analysis_results.csv dosyasına kaydedildi.")

if __name__ == "__main__":
    analyze_triggers()
