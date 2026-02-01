#!/usr/bin/env python3
"""
🍊 OCAK 2026 - PORTAKAL SIKACAĞI FİLTRELİ LİSTE
===============================================
v17 formatında liste + Portakal Sıkacağı filtresi uygulanmış hali
"""

import sys
sys.path.insert(0, '/Users/alisaglam/TezaverMac/scripts')

from layered_elimination import collect_all_triggers
from portakal_sikacagi import apply_portakal_sikacagi
import pandas as pd
from datetime import datetime

OUTPUT_FILE = "/Users/alisaglam/TezaverMac/reports/ocak2026_portakal_sikacagi.md"

def categorize_peak(peak):
    """Peak değerine göre tier belirleme"""
    if peak >= 30: return "💎"
    elif peak >= 20: return "🥇"
    elif peak >= 10: return "🥈"
    elif peak >= 5: return "🥉"
    elif peak >= 2: return "+"
    else: return "-"

def format_pct(val, positive_color='green', negative_color='red'):
    """Yüzde formatla"""
    if pd.isna(val): return "-"
    if val > 0:
        return f"<font color='{positive_color}'>+{val:.1f}%</font>"
    elif val < 0:
        return f"<font color='{negative_color}'>{val:.1f}%</font>"
    return "0.0%"

def main():
    print("=" * 60)
    print("🍊 OCAK 2026 - PORTAKAL SIKACAĞI FİLTRELİ LİSTE")
    print("=" * 60)
    
    # 1. Tüm tetikleri topla
    print("\n📥 Tetikler toplanıyor...")
    df = collect_all_triggers()
    print(f"   Toplam: {len(df)} tetik")
    
    # 2. Portakal Sıkacağı uygula
    print("\n🍊 Portakal Sıkacağı uygulanıyor...")
    filtered = apply_portakal_sikacagi(df.copy(), verbose=True)
    
    # 3. Kategori istatistikleri
    if 'cat' in filtered.columns:
        tier_count = (filtered['cat'] == 'tier').sum()
        small_count = (filtered['cat'] == 'small_gain').sum()
        noise_count = (filtered['cat'].isin(['flat', 'garbage'])).sum()
        
        print(f"\n📊 FİLTRE SONRASI:")
        print(f"   Tier (≥5%): {tier_count} ({tier_count/len(filtered)*100:.1f}%)")
        print(f"   Small (2-5%): {small_count} ({small_count/len(filtered)*100:.1f}%)")
        print(f"   Noise (<2%): {noise_count} ({noise_count/len(filtered)*100:.1f}%)")
    
    # 4. v17 formatında rapor oluştur
    print(f"\n📝 Rapor oluşturuluyor: {OUTPUT_FILE}")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# 🍊 OCAK 2026 - PORTAKAL SIKACAĞI FİLTRELİ LİSTE\n\n")
        f.write(f"**Oluşturulma:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"**Toplam Tetik:** {len(filtered)}\n\n")
        
        if 'cat' in filtered.columns:
            f.write("## 📊 Özet İstatistikler\n\n")
            f.write(f"| Kategori | Sayı | Oran |\n")
            f.write(f"|----------|------|------|\n")
            f.write(f"| Tier (≥5%) | {tier_count} | {tier_count/len(filtered)*100:.1f}% |\n")
            f.write(f"| Small (2-5%) | {small_count} | {small_count/len(filtered)*100:.1f}% |\n")
            f.write(f"| Noise (<2%) | {noise_count} | {noise_count/len(filtered)*100:.1f}% |\n")
            f.write(f"| **Başarı Oranı (Tier+Small)** | **{tier_count+small_count}** | **{(tier_count+small_count)/len(filtered)*100:.1f}%** |\n\n")
        
        f.write("---\n\n")
        
        # Günlük tablolar
        headers = ["#", "SYM", "TIER", "PEAK", "v_hyb", "v_idx", "v_eff", "v_dyn", "ATR", "ADX", "RSI", "TREND", "POS"]
        
        for date in sorted(filtered['date'].unique()):
            day_df = filtered[filtered['date'] == date].copy()
            day_df = day_df.sort_values('peak_pct', ascending=False)
            
            date_str = pd.to_datetime(date).strftime('%d %B %Y') if not isinstance(date, str) else date
            f.write(f"## 📅 {date_str} ({len(day_df)} tetik)\n\n")
            
            # Header
            f.write("| " + " | ".join(headers) + " |\n")
            f.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
            
            for idx, (_, row) in enumerate(day_df.iterrows(), 1):
                tier_icon = categorize_peak(row.get('peak_pct', 0))
                peak_val = row.get('peak_pct', 0)
                peak_str = f"+{peak_val:.1f}%" if peak_val > 0 else f"{peak_val:.1f}%"
                
                # Format values
                v_hyb = f"{row.get('v_hyb', 0):.1f}"
                v_idx = f"{row.get('v_idx', 0):.1f}"
                v_eff = f"{row.get('v_eff', 0):.1f}"
                v_dyn = f"{row.get('v_dyn', 0):.1f}"
                atr = f"{row.get('atr_adj', 0):.1f}%"
                adx = f"{row.get('d_adx', 0):.0f}"
                rsi = f"{row.get('rsi', 0):.0f}"
                trend = str(row.get('trend_str', '-'))
                pos = str(row.get('pos', '-'))
                
                f.write(f"| {idx} | {row.get('symbol', '-')} | {tier_icon} | {peak_str} | {v_hyb} | {v_idx} | {v_eff} | {v_dyn} | {atr} | {adx} | {rsi} | {trend} | {pos} |\n")
            
            f.write("\n")
        
        f.write("---\n")
        f.write("*🍊 Portakal Sıkacağı v1.0 ile filtrelenmiştir.*\n")
    
    print(f"\n✅ Rapor oluşturuldu: {OUTPUT_FILE}")
    print(f"   Toplam: {len(filtered)} tetik")

if __name__ == "__main__":
    main()
