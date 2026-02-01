import os
import pandas as pd
import numpy as np
from datetime import datetime

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
REPORT_FILE = "data_inventory_report.md"

def load_clean(path):
    try:
        df = pd.read_parquet(path)
        if 'timestamp' in df.columns:
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df = df[~df.index.duplicated(keep='last')]
            return df.sort_index()
    except Exception as e:
        return pd.DataFrame()

def scan_inventory():
    print("🔍 Tarama Başlıyor: Veri Envanteri 2023-2025...")
    
    if not os.path.exists(COIN_CELLS_DIR):
        print(f"❌ Klasör bulunamadı: {COIN_CELLS_DIR}")
        return

    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    results = []
    
    tier_counts = {'A': 0, 'B': 0, 'C': 0, 'X': 0}
    
    target_start = pd.Timestamp("2023-01-01")
    target_end = pd.Timestamp("2025-12-31")
    
    for i, symbol in enumerate(sorted(symbols)):
        path_15m = os.path.join(COIN_CELLS_DIR, symbol, "data", "history_15m.parquet")
        
        if not os.path.exists(path_15m):
            tier_counts['X'] += 1
            results.append({'symbol': symbol, 'tier': 'X', 'start': '-', 'end': '-', 'rows': 0, 'missing': 0.0, 'note': 'No File'})
            continue
            
        df = load_clean(path_15m)
        if df.empty:
            tier_counts['X'] += 1
            results.append({'symbol': symbol, 'tier': 'X', 'start': '-', 'end': '-', 'rows': 0, 'missing': 0.0, 'note': 'Empty File'})
            continue
            
        start = df.index.min()
        end = df.index.max()
        rows = len(df)
        
        # Gap Analysis
        full_range = pd.date_range(start=start, end=end, freq='15min')
        total_slots = len(full_range)
        missing_slots = total_slots - rows
        missing_pct = (missing_slots / total_slots) * 100 if total_slots > 0 else 0
        
        # Tier Classification
        # Tier A: Starts very close to 2023 (or before) AND covers up to end of 2025 (or current)
        is_start_ok = start <= target_start + pd.Timedelta(days=30) # Allow 1 month grace
        is_end_ok = end >= target_end - pd.Timedelta(days=30) # Allow 1 month grace
        
        if is_start_ok and is_end_ok:
            tier = 'A'
        elif start > (target_end - pd.Timedelta(days=365)): # Starts in last year
            tier = 'C'
        else:
            tier = 'B'
            
        tier_counts[tier] += 1
        
        results.append({
            'symbol': symbol,
            'tier': tier,
            'start': start.strftime("%Y-%m-%d"),
            'end': end.strftime("%Y-%m-%d"),
            'rows': f"{rows:,}",
            'missing': f"{missing_pct:.2f}%",
            'note': ""
        })
        
        if i % 10 == 0:
            print(f"   Processed {i+1}/{len(symbols)}: {symbol} [{tier}]")

    print("\n✅ Tarama Tamamlandı.")
    print(f"   Tier A (Tam Veri): {tier_counts['A']}")
    print(f"   Tier B (Eksik/Kısmi): {tier_counts['B']}")
    print(f"   Tier C (Yeni): {tier_counts['C']}")
    print(f"   Tier X (Hata): {tier_counts['X']}")
    
    # Report Generation
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# 🧬 Coin Veri Envanteri Raporu\n")
        f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        
        f.write("## 📊 Özet Durum\n")
        f.write("| Tier | Tanım | Adet |\n")
        f.write("|---|---|---|\n")
        f.write(f"| **Tier A** | 2023-2025+ Tam Veri | **{tier_counts['A']}** |\n")
        f.write(f"| **Tier B** | Kısmi Geçmiş (2024+) | **{tier_counts['B']}** |\n")
        f.write(f"| **Tier C** | Yeni Listeleme (<1 Yıl) | **{tier_counts['C']}** |\n")
        f.write(f"| **Tier X** | Veri Yok/Hatalı | **{tier_counts['X']}** |\n\n")
        
        f.write("## 📋 Detaylı Liste\n")
        f.write("| Symbol | Tier | Başlangıç | Bitiş | Veri Sayısı (15m) | Kayıp (%) | Not |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        
        # Sort by Tier then Symbol
        results.sort(key=lambda x: (x['tier'], x['symbol']))
        
        for r in results:
            tier_icon = "🟢" if r['tier'] == 'A' else "🟡" if r['tier'] == 'B' else "🔴" if r['tier'] == 'C' else "⚫"
            f.write(f"| {r['symbol']} | {tier_icon} {r['tier']} | {r['start']} | {r['end']} | {r['rows']} | {r['missing']} | {r['note']} |\n")

    print(f"Rapor dosyaya yazıldı: {REPORT_FILE}")

if __name__ == "__main__":
    scan_inventory()
