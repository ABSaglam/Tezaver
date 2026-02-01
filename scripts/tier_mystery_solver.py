#!/usr/bin/env python3
"""
TIER GİZEM ÇÖZÜCÜ (Tier Mystery Solver)
========================================
v17 raporunu parse eder ve yüksek/düşük tier trigger'ları arasındaki
istatistiksel farkları analiz eder.
"""

import re
import pandas as pd
import numpy as np
from collections import defaultdict

REPORT_FILE = "refined_global_report_v17.md"

def strip_html(text):
    """Remove HTML/font tags from text."""
    return re.sub(r'<[^>]+>', '', str(text))

def parse_percent(val):
    """Parse percentage string to float."""
    val = strip_html(str(val))
    val = val.replace('%', '').replace('+', '').replace('*', '').strip()
    try:
        return float(val)
    except:
        return None

def parse_number(val):
    """Parse number string to float."""
    val = strip_html(str(val))
    val = val.replace('x', '').replace('*', '').strip()
    # Handle emojis in RngPos
    val = re.sub(r'[🔝🔻]', '', val)
    try:
        return float(val)
    except:
        return None

def parse_report():
    """Parse v17 report and extract all triggers with their metrics."""
    with open(REPORT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    triggers = []
    
    # Find all table rows (lines starting with |)
    lines = content.split('\n')
    
    current_date = None
    
    for line in lines:
        # Date headers
        if line.startswith('## 📅'):
            match = re.search(r'(\d+ \w+ \d+)', line)
            if match:
                current_date = match.group(1)
            continue
        
        # Skip header/separator rows
        if not line.startswith('|') or line.startswith('| NO') or line.startswith('|--'):
            continue
        
        # Parse table row
        cells = [c.strip() for c in line.split('|')[1:-1]]  # Remove empty first/last
        
        if len(cells) < 27:  # Need all columns
            continue
        
        # Extract tier
        tier_cell = cells[11] if len(cells) > 11 else ""
        tier = "NONE"
        if '💎' in tier_cell: tier = "DIAMOND"
        elif '🥇' in tier_cell: tier = "GOLD"
        elif '🥈' in tier_cell: tier = "SILVER"
        elif '🥉' in tier_cell: tier = "BRONZE"
        
        # Extract metrics
        try:
            trigger = {
                'date': current_date,
                'symbol': strip_html(cells[1]),
                'tier': tier,
                'p21': parse_percent(cells[12]),
                'harmony': cells[16].strip(),
                'rng_pos': parse_number(cells[17]),
                'rsi_v': cells[18].strip(),
                'atr_pct': parse_percent(cells[19]),
                'vrsi': parse_number(cells[20]),
                'v100': parse_number(cells[21]),
                'v21': parse_number(cells[22]),
                'v_mom': parse_number(cells[23]),
                'vboy': parse_number(cells[24]),
                'v_ch': parse_percent(cells[25]),
                'v_avg': parse_percent(cells[26]),
                'trend': cells[6].strip(),
                'pos': cells[7].strip(),
                'ang': parse_number(strip_html(cells[8])),
            }
            triggers.append(trigger)
        except Exception as e:
            continue
    
    return pd.DataFrame(triggers)

def analyze_tiers(df):
    """Analyze differences between tier groups."""
    
    print("=" * 80)
    print("🔮 TIER GİZEM ÇÖZÜCÜ - ANALİZ RAPORU")
    print("=" * 80)
    
    # Group by tier
    tier_order = ['DIAMOND', 'GOLD', 'SILVER', 'BRONZE', 'NONE']
    
    # Count per tier
    print("\n📊 TIER DAĞILIMI:")
    print("-" * 40)
    for tier in tier_order:
        count = len(df[df['tier'] == tier])
        pct = (count / len(df)) * 100 if len(df) > 0 else 0
        print(f"  {tier:10s}: {count:5d} ({pct:.1f}%)")
    
    # Numeric columns to analyze
    numeric_cols = ['p21', 'rng_pos', 'atr_pct', 'vrsi', 'v100', 'v21', 'v_mom', 'vboy', 'v_ch', 'v_avg', 'ang']
    
    print("\n" + "=" * 80)
    print("📈 ORTALvAMA KARŞILAŞTIRMASI (Tier'e Göre)")
    print("=" * 80)
    
    # Calculate means per tier
    tier_means = {}
    for tier in tier_order:
        tier_df = df[df['tier'] == tier]
        means = {}
        for col in numeric_cols:
            vals = tier_df[col].dropna()
            if len(vals) > 0:
                means[col] = vals.mean()
            else:
                means[col] = None
        tier_means[tier] = means
    
    # Print comparison table
    print(f"\n{'Metrik':<12}", end="")
    for tier in tier_order:
        print(f"{tier:>12}", end="")
    print()
    print("-" * 72)
    
    for col in numeric_cols:
        print(f"{col:<12}", end="")
        for tier in tier_order:
            val = tier_means[tier].get(col)
            if val is not None:
                print(f"{val:>12.1f}", end="")
            else:
                print(f"{'N/A':>12}", end="")
        print()
    
    # Analyze Harmony distribution
    print("\n" + "=" * 80)
    print("🎵 HARMONY DAĞILIMI (Tier'e Göre)")
    print("=" * 80)
    
    for tier in tier_order:
        tier_df = df[df['tier'] == tier]
        if len(tier_df) == 0:
            continue
        
        harmony_counts = tier_df['harmony'].value_counts()
        total = len(tier_df)
        
        music_note = harmony_counts.get('🎵', 0)
        double_note = harmony_counts.get('🎶', 0)
        mute = harmony_counts.get('🔇', 0)
        empty = total - music_note - double_note - mute
        
        print(f"\n{tier}:")
        print(f"  🎵 (Mükemmel): {music_note:4d} ({music_note/total*100:.1f}%)")
        print(f"  🎶 (Orta):     {double_note:4d} ({double_note/total*100:.1f}%)")
        print(f"  🔇 (Anti):     {mute:4d} ({mute/total*100:.1f}%)")
        print(f"  (Boş):        {empty:4d} ({empty/total*100:.1f}%)")
    
    # Analyze RngPos distribution
    print("\n" + "=" * 80)
    print("📍 RANGE POZİSYONU DAĞILIMI (Tier'e Göre)")
    print("=" * 80)
    
    for tier in tier_order:
        tier_df = df[df['tier'] == tier]
        rng_vals = tier_df['rng_pos'].dropna()
        if len(rng_vals) == 0:
            continue
        
        top = len(rng_vals[rng_vals >= 80])
        mid = len(rng_vals[(rng_vals > 20) & (rng_vals < 80)])
        bottom = len(rng_vals[rng_vals <= 20])
        
        print(f"\n{tier} (n={len(rng_vals)}):")
        print(f"  🔝 Tepe (>=80):  {top:4d} ({top/len(rng_vals)*100:.1f}%)")
        print(f"  ⚖️  Orta (20-80): {mid:4d} ({mid/len(rng_vals)*100:.1f}%)")
        print(f"  🔻 Dip (<=20):   {bottom:4d} ({bottom/len(rng_vals)*100:.1f}%)")
    
    # RSI-V Analysis
    print("\n" + "=" * 80)
    print("💉 RSI-V SİNYAL DAĞILIMI (Tier'e Göre)")
    print("=" * 80)
    
    for tier in tier_order:
        tier_df = df[df['tier'] == tier]
        if len(tier_df) == 0:
            continue
        
        dipbuy = len(tier_df[tier_df['rsi_v'].str.contains('DipBuy', na=False)])
        topsell = len(tier_df[tier_df['rsi_v'].str.contains('TopSell', na=False)])
        empty = len(tier_df) - dipbuy - topsell
        
        print(f"\n{tier} (n={len(tier_df)}):")
        print(f"  💚 DipBuy:   {dipbuy:4d} ({dipbuy/len(tier_df)*100:.1f}%)")
        print(f"  🔴 TopSell:  {topsell:4d} ({topsell/len(tier_df)*100:.1f}%)")
        print(f"  (Yok):      {empty:4d} ({empty/len(tier_df)*100:.1f}%)")
    
    # TREND Analysis
    print("\n" + "=" * 80)
    print("📈 TREND DAĞILIMI (Tier'e Göre)")
    print("=" * 80)
    
    for tier in tier_order:
        tier_df = df[df['tier'] == tier]
        if len(tier_df) == 0:
            continue
        
        trend_counts = tier_df['trend'].value_counts()
        total = len(tier_df)
        
        print(f"\n{tier}:")
        for trend, count in trend_counts.head(5).items():
            print(f"  {trend}: {count:4d} ({count/total*100:.1f}%)")
    
    # === FORMULA DISCOVERY ===
    print("\n" + "=" * 80)
    print("🧬 GİZLİ FORMÜL KEŞFİ")
    print("=" * 80)
    
    # Compare high tier (Diamond+Gold) vs low tier (None)
    high_tier = df[df['tier'].isin(['DIAMOND', 'GOLD'])]
    low_tier = df[df['tier'] == 'NONE']
    
    if len(high_tier) > 0 and len(low_tier) > 0:
        print("\n🔥 YÜKSEK TIER (Diamond+Gold) vs ❄️ DÜŞÜK TIER (None) KARŞILAŞTIRMASI:")
        print("-" * 60)
        
        differences = []
        
        for col in numeric_cols:
            high_mean = high_tier[col].dropna().mean()
            low_mean = low_tier[col].dropna().mean()
            
            if pd.notna(high_mean) and pd.notna(low_mean) and low_mean != 0:
                diff_pct = ((high_mean - low_mean) / abs(low_mean)) * 100
                differences.append((col, high_mean, low_mean, diff_pct))
        
        # Sort by absolute difference
        differences.sort(key=lambda x: abs(x[3]), reverse=True)
        
        print(f"\n{'Metrik':<12} {'Yüksek Tier':>12} {'Düşük Tier':>12} {'Fark %':>12}")
        print("-" * 50)
        
        for col, high, low, diff in differences:
            indicator = "✅" if diff > 20 else "⚠️" if diff > 10 else ""
            print(f"{col:<12} {high:>12.1f} {low:>12.1f} {diff:>+11.1f}% {indicator}")
        
        # Key findings
        print("\n" + "=" * 80)
        print("⚡ ANAHTAR BULGULAR (Key Findings)")
        print("=" * 80)
        
        # Find strongest differentiators
        strong_diffs = [d for d in differences if abs(d[3]) > 20]
        
        if strong_diffs:
            print("\n🎯 En Güçlü Ayırt Edici Faktörler (>20% fark):")
            for col, high, low, diff in strong_diffs[:5]:
                direction = "YÜKSEK" if diff > 0 else "DÜŞÜK"
                print(f"   • {col}: Yüksek tier'de {direction} (Fark: {diff:+.0f}%)")
        
        # Harmony insight
        high_harmony_perfect = len(high_tier[high_tier['harmony'] == '🎵']) / len(high_tier) * 100 if len(high_tier) > 0 else 0
        low_harmony_perfect = len(low_tier[low_tier['harmony'] == '🎵']) / len(low_tier) * 100 if len(low_tier) > 0 else 0
        
        print(f"\n🎵 Harmony Mükemmel (🎵) Oranı:")
        print(f"   • Yüksek Tier: {high_harmony_perfect:.1f}%")
        print(f"   • Düşük Tier:  {low_harmony_perfect:.1f}%")
        
        # RngPos insight
        high_rng_low = len(high_tier[high_tier['rng_pos'] <= 40]) / len(high_tier) * 100 if len(high_tier) > 0 else 0
        low_rng_low = len(low_tier[low_tier['rng_pos'] <= 40]) / len(low_tier) * 100 if len(low_tier) > 0 else 0
        
        print(f"\n📍 Range Pozisyonu Düşük (<=40) Oranı:")
        print(f"   • Yüksek Tier: {high_rng_low:.1f}%")
        print(f"   • Düşük Tier:  {low_rng_low:.1f}%")
        
        # Proposed Formula
        print("\n" + "=" * 80)
        print("🔮 ÖNERİLEN GİZLİ FORMÜL")
        print("=" * 80)
        
        print("""
Yüksek tier trigger'ları yakalamak için önerilen kriterler:

1. RANGE POZİSYONU: RngPos <= 50 (Fiyat henüz range'in üst yarısına çıkmamış)
2. TREND: 🟢🟢 (Her iki timeframe da bullish)
3. HARMONY: 🎵 veya 🎶 (Volume ve fiyat birlikte hareket ediyor)
4. RSI-V: DipBuy yoksa OK, TopSell uyarı işareti!
5. ATR%: >= 1.5% (Yeterli volatilite var)
6. V-Mom: >= 1.5x (Momentum artıyor)

KIRMIZI BAYRAKLAR:
❌ RngPos >= 80 (Zaten tepede)
❌ RSI-V = TopSell (Aşırı alım + satış baskısı)
❌ 🔇 Harmony (Anti-korelasyon)
❌ TREND = 🔴🔴 (Her iki timeframe da bearish)
""")
    
    return df

if __name__ == "__main__":
    df = parse_report()
    print(f"\nToplam {len(df)} trigger parse edildi.\n")
    analyze_tiers(df)
