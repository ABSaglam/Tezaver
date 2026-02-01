#!/usr/bin/env python3
"""
RSI-EMA TIER ANALİZİ
Tetik: RSI-EMA > Ribbon (Hepsi)
Amaç: 20,500 tetik içindeki başarı oranını ve Tier dağılımını ölçmek.
Portakal Sıkacağı: KAPALI (Ham veri analizi)
"""

import pandas as pd
import numpy as np
import os
import json
import re
import math
import sys
from datetime import datetime

TARGET_START_DATE = "2026-01-15"
TARGET_END_DATE   = "2026-01-31"
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
OUTPUT_FILE = "rsi_ema_tier_analiz.md"
DISABLE_AYAS_CHECK = True

def run_analysis():
    print(f"RSI-EMA Tier Analizi Başlıyor...")
    print(f"Tarih: {TARGET_START_DATE} - {TARGET_END_DATE}")
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    all_triggers = []
    
    start_d = pd.Timestamp(TARGET_START_DATE)
    end_d = pd.Timestamp(TARGET_END_DATE) + pd.Timedelta(days=1)
    
    # Process symbols
    for symbol in symbols:
        try:
            # Load Data
            try:
                df_15m = pd.read_parquet(f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet")
                df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
                df_15m.set_index('dt', inplace=True)
                df_15m = df_15m[~df_15m.index.duplicated(keep='last')].sort_index()
            except: continue

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
            
            # Global Trigger Calc
            ribbon_max = df_15m[rsi_ribbon_cols].max(axis=1)
            rsi_ema = df_15m['rsi_ema']
            cond_now = rsi_ema > ribbon_max
            # Same logic as before: Shift 1 was NOT fully above (meaning at least one was above or equal)
            triggers = (cond_now) & (~cond_now.shift(1).fillna(False))
            all_trigger_indices = np.where(triggers)[0]

            # Iterate days
            current = start_d
            while current <= end_d:
                current_utc = current.normalize()
                day_mask = (df_15m.index.normalize() == current_utc)
                day_indices = np.where(day_mask)[0]
                
                if len(day_indices) == 0:
                    current += pd.Timedelta(days=1); continue

                for i in day_indices:
                    if i < 21: continue
                    if i not in all_trigger_indices: continue
                    
                    # Found Trigger
                    trigger_time = df_15m.index[i]
                    close_p = df_15m['close'].values[i]
                    
                    # Calculate Peak
                    search_limit = min(i + 22, len(df_15m))
                    if i + 1 < len(df_15m):
                        val_slice = df_15m['high'].values[i + 1 : search_limit + 1]
                        if len(val_slice) > 0:
                            peak_price = val_slice.max()
                        else:
                            peak_price = close_p
                    else:
                        peak_price = close_p
                    
                    peak_pct = ((peak_price / close_p) - 1) * 100
                    
                    all_triggers.append({
                        'symbol': symbol,
                        'time': trigger_time,
                        'peak': peak_pct
                    })
                
                current += pd.Timedelta(days=1)
        except Exception as e:
            continue

    df = pd.DataFrame(all_triggers)
    total_count = len(df)
    
    if total_count == 0:
        print("Hiç tetik bulunamadı.")
        return

    # Categorize
    diamond = df[df['peak'] >= 30]
    gold = df[(df['peak'] >= 20) & (df['peak'] < 30)]
    silver = df[(df['peak'] >= 10) & (df['peak'] < 20)]
    bronze = df[(df['peak'] >= 5) & (df['peak'] < 10)]
    fail = df[df['peak'] < 5]
    
    success_count = len(diamond) + len(gold) + len(silver) + len(bronze)
    success_rate = (success_count / total_count) * 100
    
    print(f"\nSONUÇLAR:")
    print(f"Toplam Tetik: {total_count}")
    print(f"Başarılı (Tier + Bronze >= 5%): {success_count} (%{success_rate:.1f})")
    print(f"Başarısız (< 5%): {len(fail)} (%{len(fail)/total_count*100:.1f})")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# 📊 RSI-EMA TIER ANALİZİ (Portakal Filtresi YOK)\n")
        f.write(f"**Tarih:** {TARGET_START_DATE} - {TARGET_END_DATE}\n")
        f.write(f"**Strateji:** RSI-EMA > Ribbon (20-55)\n\n")
        
        f.write("## 📈 Özet İstatistikler\n")
        f.write("| Kategori | Kriter | Adet | Oran |\n")
        f.write("|---|---|---|---|\n")
        f.write(f"| **TOPLAM** | - | **{total_count}** | 100% |\n")
        f.write(f"| 💎 **Elmas** | > %30 | {len(diamond)} | %{len(diamond)/total_count*100:.1f} |\n")
        f.write(f"| 🥇 **Altın** | %20 - %30 | {len(gold)} | %{len(gold)/total_count*100:.1f} |\n")
        f.write(f"| 🥈 **Gümüş** | %10 - %20 | {len(silver)} | %{len(silver)/total_count*100:.1f} |\n")
        f.write(f"| 🥉 **Bronz** | %5 - %10 | {len(bronze)} | %{len(bronze)/total_count*100:.1f} |\n")
        f.write(f"| ❌ **Başarısız** | < %5 | {len(fail)} | %{len(fail)/total_count*100:.1f} |\n")
        
        f.write(f"\n### 🏆 Genel Başarı Oranı (>= %5): **%{success_rate:.1f}**\n\n")
        
        def write_list(title, sub_df):
            f.write(f"## {title} ({len(sub_df)})\n")
            if sub_df.empty:
                f.write("_Veri yok._\n\n")
                return
            
            sub_df = sub_df.sort_values(by='peak', ascending=False)
            # Limit listing if too long (e.g. Bronze might have thousands)
            limit = 100
            
            f.write(f"| Tarih | Sembol | Peak |\n")
            f.write(f"|---|---|---|\n")
            for _, r in sub_df.head(limit).iterrows():
                f.write(f"| {r['time'].strftime('%Y-%m-%d %H:%M')} | **{r['symbol']}** | %{r['peak']:.1f} |\n")
            
            if len(sub_df) > limit:
                f.write(f"| ... | ... | ... (+{len(sub_df)-limit} daha) |\n")
            f.write("\n")

        write_list("💎 ELMAS LİSTESİ (>%30)", diamond)
        write_list("🥇 ALTIN LİSTESİ (%20-%30)", gold)
        write_list("🥈 GÜMÜŞ LİSTESİ (%10-%20)", silver)
        write_list("🥉 BRONZ LİSTESİ (%5-%10)", bronze)

    print(f"Rapor dosyaya yazıldı: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_analysis()
