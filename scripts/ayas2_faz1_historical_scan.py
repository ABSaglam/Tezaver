#!/usr/bin/env python3
"""
AYAŞ TÜNELİ-2: FAZ 1 - TARİHSEL TARAMA
=======================================
Yeni tetik (RSI-EMA > Tüm Ribbon) ile tüm coinleri tara.
Her tetik için:
  - 21 bar MAX hesapla
  - Tier ata (Diamond/Gold/Silver/Bronze/NoTier)
  - DNA profilini kaydet
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
OUTPUT_FILE = "/Users/alisaglam/TezaverMac/data/ayas2_historical_scan.parquet"

# Son 100 gün
END_DATE = pd.Timestamp.now().normalize()
START_DATE = END_DATE - pd.Timedelta(days=100)

def load_clean(path):
    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df = df[~df.index.duplicated(keep='last')]
    return df.sort_index()

def get_dna_profile(day, df_w, df_h1, df_d, df_h4):
    """Basitleştirilmiş DNA profili - scanner'daki get_profile_simple benzeri"""
    try:
        daily_integrity_cutoff = day.normalize()
        
        # --- IRON WALL FIX ---
        # 1H Fix
        h1_cutoff = day - pd.Timedelta(hours=1)
        sub_h1_24 = df_h1[df_h1.index <= h1_cutoff].tail(24)
        
        # 4H Fix
        h4_cutoff = day - pd.Timedelta(hours=4)
        sub_h4 = df_h4[df_h4.index <= h4_cutoff].tail(42)
        
        # Daily
        sub_d = df_d[df_d.index < daily_integrity_cutoff].tail(100)
        
        # Weekly Fix
        weekly_cutoff = day - pd.Timedelta(days=7)
        sub_w = df_w[df_w.index < weekly_cutoff].tail(52)
        # ---------------------
        
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
            sub_h1_24['ema9'] = sub_h1_24['close'].ewm(span=9, adjust=False).mean()
            sub_h1_24['ema21'] = sub_h1_24['close'].ewm(span=21, adjust=False).mean()
            squeeze_pct = abs(sub_h1_24['ema9'].iloc[-1] - sub_h1_24['ema21'].iloc[-1]) / sub_h1_24['close'].iloc[-1] * 100
            if squeeze_pct <= 0.3: acc = "tight_squeeze"
            elif squeeze_pct <= 0.8: acc = "micro_squeeze"
            elif squeeze_pct <= 1.5: acc = "normal_gap"
            else: acc = "expanded_gap"
        else:
            acc = "no_data"
        
        # Harmoni (çoklu TF trend uyumu)
        if len(sub_h1_24) >= 21:
            sub_h1_24['ema21_h'] = sub_h1_24['close'].ewm(span=21, adjust=False).mean()
            h1_trend = sub_h1_24['close'].iloc[-1] > sub_h1_24['ema21_h'].iloc[-1]
        else:
            h1_trend = True
        
        if len(sub_h4) >= 21:
            sub_h4['ema21_4h'] = sub_h4['close'].ewm(span=21, adjust=False).mean()
            h4_trend = sub_h4['close'].iloc[-1] > sub_h4['ema21_4h'].iloc[-1]
        else:
            h4_trend = True
        
        if len(sub_d) >= 21:
            sub_d['ema21_d'] = sub_d['close'].ewm(span=21, adjust=False).mean()
            d_trend = sub_d['close'].iloc[-1] > sub_d['ema21_d'].iloc[-1]
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
    except:
        return "neutral"

def get_tier(max_pct):
    """MAX değerine göre tier ata"""
    if max_pct >= 30: return "Diamond"
    elif max_pct >= 20: return "Gold"
    elif max_pct >= 10: return "Silver"
    elif max_pct >= 5: return "Bronze"
    else: return "NoTier"

def scan_symbol(symbol):
    """Bir coin için tarihsel tarama yap"""
    results = []
    try:
        df_15m = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet")
        df_1h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet")
        df_4h = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet")
        df_1d = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
        df_1w = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1w.parquet")
        
        if len(df_15m) < 500:
            return results
        
        # RSI hesapla
        delta = df_15m['close'].diff()
        alpha = 1 / 11
        gain = delta.where(delta > 0, 0).ewm(alpha=alpha, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=alpha, adjust=False).mean().replace(0, 0.001)
        df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
        df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
        
        # Ribbon
        ribbon_periods = [20, 25, 30, 35, 40, 45, 50, 55]
        rsi_ribbon_cols = []
        for p in ribbon_periods:
            df_15m[f'rsi_rib_{p}'] = df_15m['rsi_ema'].ewm(span=p, adjust=False).mean()
            rsi_ribbon_cols.append(f'rsi_rib_{p}')
        
        # Yeni tetik: RSI-EMA tüm ribbon'un üzerinde
        rsi_ema_vals = df_15m['rsi_ema'].values
        all_above = np.ones(len(df_15m), dtype=bool)
        for col in rsi_ribbon_cols:
            all_above &= (rsi_ema_vals > df_15m[col].values)
        
        prev_not_above = ~np.roll(all_above, 1)
        prev_not_above[0] = True
        trigger_mask = prev_not_above & all_above
        trigger_indices = np.where(trigger_mask)[0]
        
        # Tarih aralığında filtrele
        for idx in trigger_indices:
            if idx < 100 or idx >= len(df_15m) - 21:
                continue
            
            trigger_time = df_15m.index[idx]
            if trigger_time < START_DATE or trigger_time > END_DATE:
                continue
            
            # Sonraki 21 bar MAX
            future_slice = df_15m.iloc[idx:idx+22]
            if len(future_slice) < 21:
                continue
            
            trigger_close = future_slice.iloc[0]['close']
            max_high = future_slice['high'].max()
            max_pct = ((max_high / trigger_close) - 1) * 100
            close_21 = future_slice.iloc[-1]['close']
            close_pct = ((close_21 / trigger_close) - 1) * 100
            
            # DNA profili
            dna = get_dna_profile(trigger_time, df_1w, df_1h, df_1d, df_4h)
            
            # Tier
            tier = get_tier(max_pct)
            
            results.append({
                'symbol': symbol,
                'trigger_time': trigger_time,
                'date': trigger_time.normalize(),
                'max_pct': max_pct,
                'close_pct': close_pct,
                'tier': tier,
                'dna': dna
            })
    except Exception as e:
        pass
    
    return results

def main():
    print("=" * 60)
    print("AYAŞ TÜNELİ-2: FAZ 1 - TARİHSEL TARAMA")
    print("=" * 60)
    print(f"Tarih Aralığı: {START_DATE.date()} → {END_DATE.date()}")
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    print(f"Toplam Coin: {len(symbols)}")
    
    all_results = []
    for i, symbol in enumerate(symbols):
        results = scan_symbol(symbol)
        all_results.extend(results)
        if (i + 1) % 50 == 0:
            print(f"  İşlenen: {i+1}/{len(symbols)} - Tetik: {len(all_results)}")
    
    df = pd.DataFrame(all_results)
    
    if df.empty:
        print("Hiç tetik bulunamadı!")
        return
    
    # Kaydet
    df.to_parquet(OUTPUT_FILE)
    print(f"\nKaydedildi: {OUTPUT_FILE}")
    
    # Özet
    print("\n" + "=" * 60)
    print("📊 ÖZET İSTATİSTİKLER")
    print("=" * 60)
    print(f"Toplam Tetik: {len(df)}")
    print(f"Ortalama MAX: +{df['max_pct'].mean():.2f}%")
    print(f"Ortalama CLOSE: {df['close_pct'].mean():+.2f}%")
    
    # Tier dağılımı
    print("\n🏆 TIER DAĞILIMI (OLAN)")
    print("-" * 40)
    tier_counts = df['tier'].value_counts()
    tier_order = ['Diamond', 'Gold', 'Silver', 'Bronze', 'NoTier']
    tier_icons = {'Diamond': '💎', 'Gold': '🥇', 'Silver': '🥈', 'Bronze': '🥉', 'NoTier': '-'}
    
    for tier in tier_order:
        count = tier_counts.get(tier, 0)
        pct = (count / len(df)) * 100
        print(f"  {tier_icons[tier]} {tier:8s}: {count:5d}  ({pct:5.1f}%)")
    
    # Başarılı tier oranı (Bronze+)
    success_count = len(df[df['tier'].isin(['Diamond', 'Gold', 'Silver', 'Bronze'])])
    success_pct = (success_count / len(df)) * 100
    print(f"\n  ✅ Başarılı (≥Bronze): {success_count} ({success_pct:.1f}%)")
    print(f"  ❌ Başarısız (NoTier): {len(df) - success_count} ({100 - success_pct:.1f}%)")

if __name__ == "__main__":
    main()
