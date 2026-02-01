#!/usr/bin/env python3
"""
ELEME TAKTİĞİ ANALİZİ
=====================
Hangi ek filtre en çok düşük tier'i eler, en az yüksek tier'i kaybettirir?
"""

import re
import pandas as pd
import numpy as np

REPORT_FILE = "refined_global_report_v17.md"

def strip_html(text):
    return re.sub(r'<[^>]+>', '', str(text))

def parse_percent(val):
    val = strip_html(str(val))
    val = val.replace('%', '').replace('+', '').replace('*', '').strip()
    try:
        return float(val)
    except:
        return None

def parse_number(val):
    val = strip_html(str(val))
    val = val.replace('x', '').replace('*', '').strip()
    val = re.sub(r'[🔝🔻]', '', val)
    try:
        return float(val)
    except:
        return None

def parse_report():
    with open(REPORT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    triggers = []
    lines = content.split('\n')
    current_date = None
    
    for line in lines:
        if line.startswith('## 📅'):
            match = re.search(r'(\d+ \w+ \d+)', line)
            if match:
                current_date = match.group(1)
            continue
        
        if not line.startswith('|') or line.startswith('| NO') or line.startswith('|--'):
            continue
        
        cells = [c.strip() for c in line.split('|')[1:-1]]
        
        if len(cells) < 27:
            continue
        
        tier_cell = cells[11] if len(cells) > 11 else ""
        tier = "NONE"
        if '💎' in tier_cell: tier = "DIAMOND"
        elif '🥇' in tier_cell: tier = "GOLD"
        elif '🥈' in tier_cell: tier = "SILVER"
        elif '🥉' in tier_cell: tier = "BRONZE"
        
        try:
            trigger = {
                'date': current_date,
                'symbol': strip_html(cells[1]),
                'tier': tier,
                'has_tier': tier != "NONE",
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
            }
            triggers.append(trigger)
        except:
            continue
    
    return pd.DataFrame(triggers)

def test_filter(df, filter_func, filter_name):
    """Test a filter and return elimination stats."""
    
    before_none = len(df[df['tier'] == 'NONE'])
    before_high = len(df[df['tier'].isin(['DIAMOND', 'GOLD', 'SILVER', 'BRONZE'])])
    
    filtered = df[filter_func(df)]
    
    after_none = len(filtered[filtered['tier'] == 'NONE'])
    after_high = len(filtered[filtered['tier'].isin(['DIAMOND', 'GOLD', 'SILVER', 'BRONZE'])])
    
    none_eliminated = before_none - after_none
    high_lost = before_high - after_high
    
    none_elim_pct = (none_eliminated / before_none * 100) if before_none > 0 else 0
    high_loss_pct = (high_lost / before_high * 100) if before_high > 0 else 0
    
    # Efficiency score: High elimination of NONE, low loss of tiers
    efficiency = none_elim_pct - (high_loss_pct * 2)  # Penalize tier loss more
    
    return {
        'filter': filter_name,
        'none_elim': none_eliminated,
        'none_elim_pct': none_elim_pct,
        'high_lost': high_lost,
        'high_loss_pct': high_loss_pct,
        'efficiency': efficiency,
        'remaining': len(filtered)
    }

def run_elimination_analysis(df):
    print("=" * 80)
    print("🎯 ELEME TAKTİĞİ ANALİZİ")
    print("=" * 80)
    
    print(f"\n📊 Mevcut Durum:")
    print(f"   Toplam: {len(df)} trigger")
    print(f"   NONE: {len(df[df['tier'] == 'NONE'])} ({len(df[df['tier'] == 'NONE'])/len(df)*100:.1f}%)")
    print(f"   Tier'li: {len(df[df['tier'] != 'NONE'])} ({len(df[df['tier'] != 'NONE'])/len(df)*100:.1f}%)")
    
    # Define filters to test
    filters = [
        # ATR filters
        (lambda d: d['atr_pct'] >= 1.0, "ATR% >= 1.0%"),
        (lambda d: d['atr_pct'] >= 1.5, "ATR% >= 1.5%"),
        (lambda d: d['atr_pct'] >= 2.0, "ATR% >= 2.0%"),
        
        # Harmony filters
        (lambda d: d['harmony'].isin(['🎵', '🎶', '']), "Harmony != 🔇"),
        (lambda d: d['harmony'] == '🎵', "Harmony = 🎵 (sadece)"),
        
        # Trend filters
        (lambda d: d['trend'] != '🔴🔴', "TREND != 🔴🔴"),
        (lambda d: d['trend'] == '🟢🟢', "TREND = 🟢🟢 (sadece)"),
        
        # RngPos filters
        (lambda d: d['rng_pos'] <= 70, "RngPos <= 70"),
        (lambda d: d['rng_pos'] <= 50, "RngPos <= 50"),
        
        # V-Avg filters
        (lambda d: d['v_avg'] >= 100, "V-Avg >= +100%"),
        (lambda d: d['v_avg'] >= 200, "V-Avg >= +200%"),
        
        # V21 filters
        (lambda d: d['v21'] >= 5.0, "V21 >= 5.0"),
        (lambda d: d['v21'] >= 7.0, "V21 >= 7.0"),
        
        # V-Mom filters
        (lambda d: d['v_mom'] >= 1.5, "V-Mom >= 1.5x"),
        (lambda d: d['v_mom'] >= 2.0, "V-Mom >= 2.0x"),
        
        # Kombinasyonlar
        (lambda d: (d['atr_pct'] >= 1.5) & (d['trend'] != '🔴🔴'), "ATR% >= 1.5% + TREND != 🔴🔴"),
        (lambda d: (d['atr_pct'] >= 1.5) & (d['harmony'].isin(['🎵', '🎶', ''])), "ATR% >= 1.5% + Harmony != 🔇"),
        (lambda d: (d['v21'] >= 5.0) & (d['atr_pct'] >= 1.0), "V21 >= 5.0 + ATR% >= 1.0%"),
    ]
    
    results = []
    for filter_func, filter_name in filters:
        try:
            result = test_filter(df, filter_func, filter_name)
            results.append(result)
        except Exception as e:
            print(f"Error with {filter_name}: {e}")
    
    # Sort by efficiency
    results.sort(key=lambda x: x['efficiency'], reverse=True)
    
    print("\n" + "=" * 80)
    print("📋 FİLTRE ETKİNLİK TABLOSU (Verimlilik sırasına göre)")
    print("=" * 80)
    
    print(f"\n{'Filtre':<40} {'NONE Elenen':>12} {'Tier Kayıp':>12} {'Verimlilik':>12} {'Kalan':>8}")
    print("-" * 90)
    
    for r in results:
        eff_icon = "✅" if r['efficiency'] > 5 else "⚠️" if r['efficiency'] > 0 else "❌"
        print(f"{r['filter']:<40} {r['none_elim']:>5} ({r['none_elim_pct']:>5.1f}%) {r['high_lost']:>5} ({r['high_loss_pct']:>5.1f}%) {r['efficiency']:>+10.1f} {eff_icon} {r['remaining']:>7}")
    
    # Best filters
    print("\n" + "=" * 80)
    print("🏆 EN ETKİLİ ELEME FİLTRELERİ")
    print("=" * 80)
    
    top_filters = [r for r in results if r['efficiency'] > 5][:5]
    
    for i, r in enumerate(top_filters, 1):
        print(f"\n{i}. {r['filter']}")
        print(f"   NONE'dan {r['none_elim']} trigger elendi (%{r['none_elim_pct']:.1f})")
        print(f"   Tier'li sadece {r['high_lost']} kayıp (%{r['high_loss_pct']:.1f})")
        print(f"   Verimlilik Skoru: {r['efficiency']:+.1f}")
    
    # Recommendation
    print("\n" + "=" * 80)
    print("💡 ÖNERİ")
    print("=" * 80)
    
    print("""
Mevcut filtrelerinize (Vrsi>=10 OR V100>=10 OR Tier) ek olarak:

🎯 ÖNERILEN EK FİLTRE:
   ATR% >= 1.5%
   
Bu filtre:
- Düşük volatiliteli (hareket etmeyen) coinleri eler
- Yüksek tier kayıp oranı düşük
- Kalan coinler gerçek hareket potansiyeli taşır
""")

if __name__ == "__main__":
    df = parse_report()
    print(f"\n{len(df)} trigger yüklendi.\n")
    run_elimination_analysis(df)
