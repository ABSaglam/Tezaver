#!/usr/bin/env python3
"""
KAPSAMLI AYAŞ TÜNELİ ANALİZİ (comprehensive_tunnel_analysis.py)
================================================================
- Pencere: 3 Gün (72 saat)
- Veri: 2 Yıl (2024-2026)
- Çözünürlük: 15 dakika
- Kapsam: Tüm Koinler (441)
- Sinyal Türleri: Normal Tünel + Zeplin
"""

import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

def classify_tier(max_gain, max_loss):
    """Tier Classification based on gain/loss (Doğru Eşikler)"""
    # Positive Tiers (based on max gain)
    if max_gain >= 30: return 'DIAMOND'   # ≥30%
    if max_gain >= 15: return 'GOLD'      # ≥15%
    if max_gain >= 10: return 'SILVER'    # ≥10%
    if max_gain >= 5: return 'BRONZE'     # ≥5%
    if max_gain >= 0: return 'IRON'       # 0-5%
    
    # Negative Tiers (based on max loss if no positive gain)
    if max_loss >= -5: return '-IRON'
    if max_loss >= -10: return '-BRONZE'
    if max_loss >= -20: return '-SILVER'
    if max_loss >= -30: return '-GOLD'
    return '-DIAMOND'

def run_comprehensive_analysis():
    print("📊 KAPSAMLI AYAŞ TÜNELİ ANALİZİ BAŞLIYOR...")
    print("   Pencere: 3 Gün | Veri: 2 Yıl | Çözünürlük: 15dk")
    print("="*70)
    
    # Load DNA
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        dna_map = dict(zip(dna['symbol'], dna['cluster_name']))
    except:
        dna_map = {}

    start_date = pd.Timestamp("2024-01-01").tz_localize('UTC')
    results = []
    
    for idx, symbol in enumerate(DEFAULT_COINS):
        if idx % 50 == 0: print(f"Tarama: {idx}/{len(DEFAULT_COINS)}...", end='\r')
        
        path_15m = coin_cell_paths.get_history_file(symbol, '15m')
        if not path_15m.exists(): continue
        
        try:
            df_15m = pd.read_parquet(path_15m)
            if len(df_15m) < 1000: continue
            
            # Ensure DatetimeIndex
            if not isinstance(df_15m.index, pd.DatetimeIndex):
                if 'datetime' in df_15m.columns:
                    df_15m['datetime'] = pd.to_datetime(df_15m['datetime'])
                    df_15m = df_15m.set_index('datetime')
                elif 'timestamp' in df_15m.columns:
                    df_15m['datetime'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
                    df_15m = df_15m.set_index('datetime')
            
            # Resample to Daily and Weekly
            df_daily = df_15m.resample('1D').agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
            }).dropna()
            
            df_weekly = df_15m.resample('W-MON').agg({'close': 'last'}).dropna()
            
            if len(df_daily) < 50 or len(df_weekly) < 10: continue
            
            # Daily Indicators
            df_daily['atr_val'] = (df_daily['high'] - df_daily['low']).rolling(14).mean()
            df_daily['atr_pct'] = (df_daily['atr_val'] / df_daily['close']) * 100
            df_daily['rsi_d'] = calculate_rsi(df_daily['close'])
            
            # Weekly RSI
            df_weekly['rsi_w'] = calculate_rsi(df_weekly['close'])
            
            cluster = dna_map.get(symbol, "UNKNOWN")
            
            # Scan for signals
            for d in df_daily.index:
                if d < start_date: continue
                
                row = df_daily.loc[d]
                rsi_d = row['rsi_d']
                atr_pct = row['atr_pct']
                
                if np.isnan(rsi_d) or np.isnan(atr_pct): continue
                
                # Get Weekly RSI
                prior_weeks = df_weekly[:d]
                rsi_w = prior_weeks.iloc[-1]['rsi_w'] if len(prior_weeks) > 0 else np.nan
                
                # Signal Detection
                signal_type = None
                
                # Normal Tunnel (RSI 55-70, ATR > 12%)
                is_trend = (atr_pct > 15) and (55 < rsi_d < 70)
                is_ninja = (12 < atr_pct <= 15) and (60 < rsi_d < 75)
                
                if is_trend:
                    signal_type = "TREND"
                elif is_ninja:
                    signal_type = "NINJA"
                # Zeppelin (RSI > 70, Weekly >= 50)
                elif rsi_d > 70 and not np.isnan(rsi_w) and rsi_w >= 50:
                    signal_type = "ZEPLIN"
                
                if signal_type is None: continue
                
                # Measure Outcome (3 Days = 72 hours = 288 x 15m candles)
                window_start = d + pd.Timedelta(hours=1)  # Start from next candle
                window_end = d + pd.Timedelta(days=3)
                
                window_data = df_15m[(df_15m.index > window_start) & (df_15m.index <= window_end)]
                
                if len(window_data) < 10: continue
                
                entry_price = row['close']
                max_price = window_data['high'].max()
                min_price = window_data['low'].min()
                
                max_gain = ((max_price - entry_price) / entry_price) * 100
                max_loss = ((min_price - entry_price) / entry_price) * 100
                
                tier = classify_tier(max_gain, max_loss)
                
                results.append({
                    'date': d.strftime('%Y-%m-%d'),
                    'symbol': symbol.replace('USDT', ''),
                    'cluster': cluster,
                    'signal_type': signal_type,
                    'rsi_d': rsi_d,
                    'rsi_w': rsi_w,
                    'atr_pct': atr_pct,
                    'entry_price': entry_price,
                    'max_gain': max_gain,
                    'max_loss': max_loss,
                    'tier': tier
                })
                
        except Exception as e:
            continue

    print(f"\nTarama tamamlandı. Toplam sinyal: {len(results)}")
    
    # Generate Report
    df_res = pd.DataFrame(results)
    
    if df_res.empty:
        print("❌ Hiç sinyal bulunamadı.")
        return
    
    # Save raw data
    df_res.to_csv('library/comprehensive_tunnel_results.csv', index=False)
    
    # Generate Markdown Report
    report = []
    report.append("# 🚇 AYAŞ TÜNELİ - KAPSAMLI ANALİZ RAPORU")
    report.append(f"**Tarih:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"**Pencere:** 3 Gün (72 Saat) | **Çözünürlük:** 15 Dakika | **Veri:** 2024-2026")
    report.append("")
    
    # Summary
    total = len(df_res)
    report.append("## 📊 GENEL ÖZET")
    report.append("")
    report.append(f"- **Toplam Sinyal:** {total}")
    report.append(f"- **Ortalama Maksimum Kazanç:** {df_res['max_gain'].mean():.1f}%")
    report.append(f"- **Ortalama Maksimum Kayıp:** {df_res['max_loss'].mean():.1f}%")
    report.append("")
    
    # Tier Distribution
    tier_order = ['DIAMOND', 'GOLD', 'SILVER', 'BRONZE', 'IRON', '-IRON', '-BRONZE', '-SILVER', '-GOLD', '-DIAMOND']
    report.append("## 🏆 TİER DAĞILIMI")
    report.append("")
    report.append("| Tier | Sayı | Oran | Ort. Kazanç |")
    report.append("|:---|---:|---:|---:|")
    
    for t in tier_order:
        subset = df_res[df_res['tier'] == t]
        count = len(subset)
        pct = count / total * 100 if total > 0 else 0
        avg_gain = subset['max_gain'].mean() if count > 0 else 0
        emoji = "💎" if t == "DIAMOND" else "🥇" if t == "GOLD" else "🥈" if t == "SILVER" else "🥉" if t == "BRONZE" else "🔩" if t == "IRON" else "❌"
        report.append(f"| {emoji} {t} | {count} | {pct:.1f}% | {avg_gain:.1f}% |")
    
    report.append("")
    
    # Positive vs Negative
    positive_tiers = ['DIAMOND', 'GOLD', 'SILVER']
    neutral_tiers = ['BRONZE', 'IRON']
    negative_tiers = ['-IRON', '-BRONZE', '-SILVER', '-GOLD', '-DIAMOND']
    
    pos_count = len(df_res[df_res['tier'].isin(positive_tiers)])
    neu_count = len(df_res[df_res['tier'].isin(neutral_tiers)])
    neg_count = len(df_res[df_res['tier'].isin(negative_tiers)])
    
    report.append("### Özet:")
    report.append(f"- **Ralli (D+G+S):** {pos_count} ({pos_count/total*100:.1f}%)")
    report.append(f"- **Nötr (B+I):** {neu_count} ({neu_count/total*100:.1f}%)")
    report.append(f"- **Kayıp (Negatif):** {neg_count} ({neg_count/total*100:.1f}%)")
    report.append("")
    
    # By Signal Type
    report.append("## 📡 SİNYAL TÜRÜNE GÖRE")
    report.append("")
    report.append("| Tür | Sayı | Başarı% | Ort. Kazanç | Diamond% |")
    report.append("|:---|---:|---:|---:|---:|")
    
    for sig_type in ['TREND', 'NINJA', 'ZEPLIN']:
        subset = df_res[df_res['signal_type'] == sig_type]
        if len(subset) == 0: continue
        
        success = len(subset[subset['max_gain'] >= 5]) / len(subset) * 100
        diamond = len(subset[subset['tier'] == 'DIAMOND']) / len(subset) * 100
        avg = subset['max_gain'].mean()
        report.append(f"| {sig_type} | {len(subset)} | {success:.1f}% | {avg:.1f}% | {diamond:.1f}% |")
    
    report.append("")
    
    # By Cluster
    report.append("## 🧬 KÜMELERE GÖRE")
    report.append("")
    report.append("| Küme | Sayı | Başarı% | Ort. Kazanç | Diamond% |")
    report.append("|:---|---:|---:|---:|---:|")
    
    cluster_order = ['ROCKET', 'ACTIVE', 'NEEDLE', 'CALM', 'STABLE', 'UNKNOWN']
    emojis = {'ROCKET': '🚀', 'ACTIVE': '🏃', 'NEEDLE': '💉', 'CALM': '🐢', 'STABLE': '=', 'UNKNOWN': '❓'}
    
    for c in cluster_order:
        subset = df_res[df_res['cluster'] == c]
        if len(subset) == 0: continue
        
        success = len(subset[subset['max_gain'] >= 5]) / len(subset) * 100
        diamond = len(subset[subset['tier'] == 'DIAMOND']) / len(subset) * 100
        avg = subset['max_gain'].mean()
        report.append(f"| {emojis.get(c, '')} {c} | {len(subset)} | {success:.1f}% | {avg:.1f}% | {diamond:.1f}% |")
    
    report.append("")
    
    # Top Performers
    report.append("## 🌟 EN İYİ PERFORMANSLAR (Top 20)")
    report.append("")
    top20 = df_res.nlargest(20, 'max_gain')
    report.append("| Tarih | Koin | Küme | Sinyal | Kazanç |")
    report.append("|:---|:---|:---|:---|---:|")
    for _, r in top20.iterrows():
        report.append(f"| {r['date']} | {r['symbol']} | {r['cluster']} | {r['signal_type']} | +{r['max_gain']:.1f}% |")
    
    report.append("")
    
    # Worst Performers
    report.append("## 💀 EN KÖTÜ PERFORMANSLAR (Bottom 20)")
    report.append("")
    bottom20 = df_res.nsmallest(20, 'max_loss')
    report.append("| Tarih | Koin | Küme | Sinyal | Kayıp |")
    report.append("|:---|:---|:---|:---|---:|")
    for _, r in bottom20.iterrows():
        report.append(f"| {r['date']} | {r['symbol']} | {r['cluster']} | {r['signal_type']} | {r['max_loss']:.1f}% |")
    
    # Save Report
    report_path = 'analysis/ayas_tuneli_kapsamli_rapor.md'
    os.makedirs('analysis', exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print(f"\n✅ Rapor kaydedildi: {report_path}")
    print(f"✅ Ham veri: library/comprehensive_tunnel_results.csv")
    
    # Print Summary
    print("\n" + "="*70)
    print("📊 SONUÇ ÖZETİ")
    print("="*70)
    print(f"Ralli Oranı (D+G+S): {pos_count/total*100:.1f}%")
    print(f"Nötr Oran (B+I):     {neu_count/total*100:.1f}%")
    print(f"Kayıp Oranı:         {neg_count/total*100:.1f}%")

if __name__ == "__main__":
    run_comprehensive_analysis()
