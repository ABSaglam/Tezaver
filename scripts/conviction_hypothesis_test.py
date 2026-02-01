#!/usr/bin/env python3
"""
KAPANIS CESARETİ HİPOTEZ TESTİ
==============================
Hipotez: "Dünün son 4 saatindeki davranış (Sprint vs Fade), 
bugünün performansını tahmin eder."

Metrikler:
1. Close Sprint: Dünün 20:00-00:00 arası fiyat değişimi
2. Evening Volume Ratio: Akşam hacminin gün hacmine oranı
3. Bugünün MAX ve CLOSE performansı
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

# Son 30 gün analiz
END_DATE = pd.Timestamp.now().normalize()
START_DATE = END_DATE - pd.Timedelta(days=30)

def load_clean(path):
    df = pd.read_parquet(path)
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df = df[~df.index.duplicated(keep='last')]
    return df.sort_index()

def analyze_conviction():
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    all_results = []
    
    for symbol in symbols:
        try:
            # 15m ve 1d verileri yükle
            df_15m = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet")
            df_1d = load_clean(f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet")
            
            if len(df_15m) < 100 or len(df_1d) < 30:
                continue
            
            # Her gün için analiz
            current = START_DATE
            while current < END_DATE:
                try:
                    # BUGÜN: Performans hesapla
                    today_mask = df_15m.index.normalize() == current
                    today_data = df_15m[today_mask]
                    
                    if today_data.empty:
                        current += pd.Timedelta(days=1)
                        continue
                    
                    today_open = today_data.iloc[0]['open']
                    today_max = today_data['high'].max()
                    today_close = today_data.iloc[-1]['close']
                    
                    today_max_pct = ((today_max / today_open) - 1) * 100
                    today_close_pct = ((today_close / today_open) - 1) * 100
                    
                    # DÜN: Son 4 saat analizi (20:00 - 00:00 UTC)
                    yesterday = current - pd.Timedelta(days=1)
                    yesterday_mask = df_15m.index.normalize() == yesterday
                    yesterday_data = df_15m[yesterday_mask]
                    
                    if yesterday_data.empty:
                        current += pd.Timedelta(days=1)
                        continue
                    
                    # Son 4 saat = son 16 bar (15m * 16 = 4 saat)
                    last_4h = yesterday_data.tail(16)
                    first_20h = yesterday_data.head(len(yesterday_data) - 16)
                    
                    if len(last_4h) < 10 or len(first_20h) < 10:
                        current += pd.Timedelta(days=1)
                        continue
                    
                    # 1. Close Sprint: Son 4 saatteki fiyat değişimi
                    evening_start_price = last_4h.iloc[0]['open']
                    evening_end_price = last_4h.iloc[-1]['close']
                    close_sprint = ((evening_end_price / evening_start_price) - 1) * 100
                    
                    # 2. Evening Volume Ratio: Akşam hacmi / Gündüz hacmi
                    evening_vol = last_4h['volume'].sum()
                    day_vol = first_20h['volume'].sum()
                    evr = evening_vol / (day_vol + 1) if day_vol > 0 else 0
                    
                    # 3. Dünün toplam performansı
                    yesterday_open = yesterday_data.iloc[0]['open']
                    yesterday_close = yesterday_data.iloc[-1]['close']
                    yesterday_close_pct = ((yesterday_close / yesterday_open) - 1) * 100
                    
                    all_results.append({
                        'symbol': symbol,
                        'date': current,
                        'yesterday_close_pct': yesterday_close_pct,
                        'close_sprint': close_sprint,  # Dünün son 4 saat sprinti
                        'evr': evr,                    # Akşam hacim oranı
                        'today_max_pct': today_max_pct,
                        'today_close_pct': today_close_pct,
                    })
                    
                except Exception as e:
                    pass
                
                current += pd.Timedelta(days=1)
                
        except Exception as e:
            continue
    
    return pd.DataFrame(all_results)

def print_analysis(df):
    print("\n" + "="*60)
    print("🔬 KAPANIS CESARETİ HİPOTEZ TESTİ SONUÇLARI")
    print("="*60)
    print(f"Toplam Gözlem: {len(df)}")
    print(f"Tarih Aralığı: {df['date'].min().date()} → {df['date'].max().date()}")
    
    # Korelasyon Analizi
    print("\n📊 KORELASYON ANALİZİ:")
    print("-" * 40)
    
    corr_sprint_max = df['close_sprint'].corr(df['today_max_pct'])
    corr_sprint_close = df['close_sprint'].corr(df['today_close_pct'])
    corr_evr_max = df['evr'].corr(df['today_max_pct'])
    corr_evr_close = df['evr'].corr(df['today_close_pct'])
    
    print(f"Dün Sprint → Bugün MAX:    r = {corr_sprint_max:+.3f}")
    print(f"Dün Sprint → Bugün CLOSE:  r = {corr_sprint_close:+.3f}")
    print(f"Akşam Hacim → Bugün MAX:   r = {corr_evr_max:+.3f}")
    print(f"Akşam Hacim → Bugün CLOSE: r = {corr_evr_close:+.3f}")
    
    # Grup Analizi: Sprint > 0 vs Sprint < 0
    print("\n📈 GRUP ANALİZİ (Sprint Pozitif vs Negatif):")
    print("-" * 40)
    
    positive_sprint = df[df['close_sprint'] > 0]
    negative_sprint = df[df['close_sprint'] <= 0]
    
    print(f"\n🟢 Dün Sprint POZİTİF (n={len(positive_sprint)}):")
    print(f"   Bugün Ortalama MAX:   {positive_sprint['today_max_pct'].mean():+.2f}%")
    print(f"   Bugün Ortalama CLOSE: {positive_sprint['today_close_pct'].mean():+.2f}%")
    print(f"   Bugün Pozitif Kapanış: {(positive_sprint['today_close_pct'] > 0).mean()*100:.1f}%")
    
    print(f"\n🔴 Dün Sprint NEGATİF (n={len(negative_sprint)}):")
    print(f"   Bugün Ortalama MAX:   {negative_sprint['today_max_pct'].mean():+.2f}%")
    print(f"   Bugün Ortalama CLOSE: {negative_sprint['today_close_pct'].mean():+.2f}%")
    print(f"   Bugün Pozitif Kapanış: {(negative_sprint['today_close_pct'] > 0).mean()*100:.1f}%")
    
    # Fark
    max_diff = positive_sprint['today_max_pct'].mean() - negative_sprint['today_max_pct'].mean()
    close_diff = positive_sprint['today_close_pct'].mean() - negative_sprint['today_close_pct'].mean()
    
    print(f"\n⚖️ FARK (Pozitif - Negatif):")
    print(f"   MAX Farkı:   {max_diff:+.2f}%")
    print(f"   CLOSE Farkı: {close_diff:+.2f}%")
    
    # Güçlü Sprint Analizi (> +1% veya < -1%)
    print("\n🚀 GÜÇLÜ SPRİNT ANALİZİ:")
    print("-" * 40)
    
    strong_positive = df[df['close_sprint'] > 1.0]
    strong_negative = df[df['close_sprint'] < -1.0]
    
    if len(strong_positive) > 10:
        print(f"\n🟢🟢 Güçlü Pozitif Sprint (>+1%) (n={len(strong_positive)}):")
        print(f"   Bugün Ortalama MAX:   {strong_positive['today_max_pct'].mean():+.2f}%")
        print(f"   Bugün Ortalama CLOSE: {strong_positive['today_close_pct'].mean():+.2f}%")
    
    if len(strong_negative) > 10:
        print(f"\n🔴🔴 Güçlü Negatif Sprint (<-1%) (n={len(strong_negative)}):")
        print(f"   Bugün Ortalama MAX:   {strong_negative['today_max_pct'].mean():+.2f}%")
        print(f"   Bugün Ortalama CLOSE: {strong_negative['today_close_pct'].mean():+.2f}%")
    
    # Sonuç
    print("\n" + "="*60)
    if corr_sprint_close > 0.05:
        print("✅ HİPOTEZ DESTEKLENİYOR: Pozitif korelasyon mevcut.")
    elif corr_sprint_close < -0.05:
        print("❌ HİPOTEZ REDDEDİLİYOR: Negatif korelasyon (ters etki).")
    else:
        print("⚠️ HİPOTEZ BELİRSİZ: Anlamlı korelasyon bulunamadı.")
    print("="*60)

if __name__ == "__main__":
    print("Veri analiz ediliyor...")
    df = analyze_conviction()
    
    if df.empty:
        print("Yeterli veri bulunamadı.")
    else:
        print_analysis(df)
