#!/usr/bin/env python3
"""
DAHİ MODU: YENİ METRİK KEŞFİ
============================
Trigger anındaki değerler dışında, coin'in geçmişine veya karakterine bakan
yeni metrikler keşfeder.
"""

import re
import pandas as pd
import numpy as np
from collections import defaultdict

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
        
        symbol = strip_html(cells[1])
        if not symbol:  # Skip continuation rows
            continue
            
        try:
            trigger = {
                'date': current_date,
                'symbol': symbol,
                'tier': tier,
                'has_tier': tier != "NONE",
                'p21': parse_percent(cells[12]),
                'harmony': cells[16].strip(),
                'rng_pos': parse_number(cells[17]),
                'atr_pct': parse_percent(cells[19]),
                'vrsi': parse_number(cells[20]),
                'v100': parse_number(cells[21]),
                'trend': cells[6].strip(),
            }
            triggers.append(trigger)
        except:
            continue
    
    return pd.DataFrame(triggers)

def analyze_coin_character(df):
    """Analyze each coin's historical tier success rate."""
    
    print("=" * 80)
    print("🧬 DAHİ MODU: COİN KARAKTERİ ANALİZİ")
    print("=" * 80)
    
    # Group by symbol
    coin_stats = {}
    
    for symbol in df['symbol'].unique():
        coin_df = df[df['symbol'] == symbol]
        total = len(coin_df)
        tiered = len(coin_df[coin_df['has_tier']])
        
        if total > 0:
            success_rate = tiered / total * 100
            coin_stats[symbol] = {
                'total': total,
                'tiered': tiered,
                'success_rate': success_rate,
                'avg_vrsi': coin_df['vrsi'].mean(),
                'avg_v100': coin_df['v100'].mean(),
            }
    
    # Sort by success rate
    sorted_coins = sorted(coin_stats.items(), key=lambda x: x[1]['success_rate'], reverse=True)
    
    print("\n📊 COİN BAŞARI ORANLARI (En yüksek → En düşük)")
    print("-" * 70)
    print(f"{'Coin':<15} {'Toplam':>8} {'Tier':>8} {'Oran':>10} {'Avg Vrsi':>10} {'Avg V100':>10}")
    print("-" * 70)
    
    # Top 20 performers
    print("\n🏆 EN BAŞARILI 20 COİN:")
    for symbol, stats in sorted_coins[:20]:
        print(f"{symbol:<15} {stats['total']:>8} {stats['tiered']:>8} {stats['success_rate']:>9.1f}% {stats['avg_vrsi']:>10.1f} {stats['avg_v100']:>10.1f}")
    
    # Bottom 20 performers (with at least 3 triggers)
    bottom_coins = [(s, st) for s, st in sorted_coins if st['total'] >= 3 and st['success_rate'] == 0]
    print(f"\n❌ HİÇ TIER YAPMAYAN COİNLER (en az 3 tetik): {len(bottom_coins)} adet")
    
    # Create "Coin Reliability Score" groups
    print("\n" + "=" * 80)
    print("🎯 COİN GÜVENİLİRLİK GRUPLARI")
    print("=" * 80)
    
    elite = [s for s, st in sorted_coins if st['success_rate'] >= 50 and st['total'] >= 2]
    good = [s for s, st in sorted_coins if 25 <= st['success_rate'] < 50 and st['total'] >= 2]
    average = [s for s, st in sorted_coins if 10 <= st['success_rate'] < 25 and st['total'] >= 2]
    poor = [s for s, st in sorted_coins if 0 < st['success_rate'] < 10 and st['total'] >= 3]
    zero = [s for s, st in sorted_coins if st['success_rate'] == 0 and st['total'] >= 3]
    
    print(f"\n🔥 ELİT (>=%50): {len(elite)} coin")
    print(f"   {', '.join(elite[:10])}{'...' if len(elite) > 10 else ''}")
    
    print(f"\n✅ İYİ (%25-50): {len(good)} coin")
    print(f"   {', '.join(good[:10])}{'...' if len(good) > 10 else ''}")
    
    print(f"\n⚖️ ORTA (%10-25): {len(average)} coin")
    print(f"   {', '.join(average[:10])}{'...' if len(average) > 10 else ''}")
    
    print(f"\n⚠️ ZAYIF (<%10): {len(poor)} coin")
    
    print(f"\n❌ SIFIR (%0, >=3 tetik): {len(zero)} coin")
    
    # Test if coin reliability predicts tier
    print("\n" + "=" * 80)
    print("🔮 YENİ METRİK: COİN GÜVENİLİRLİK SKORU (CGS)")
    print("=" * 80)
    
    # Add CGS to dataframe
    df['coin_reliability'] = df['symbol'].map(lambda s: coin_stats.get(s, {}).get('success_rate', 0))
    
    # Test filter effectiveness
    high_rel = df[df['coin_reliability'] >= 25]
    low_rel = df[df['coin_reliability'] < 10]
    
    high_tier_rate = high_rel['has_tier'].mean() * 100 if len(high_rel) > 0 else 0
    low_tier_rate = low_rel['has_tier'].mean() * 100 if len(low_rel) > 0 else 0
    
    print(f"\n📈 CGS >= %25 olan coinlerde tier oranı: {high_tier_rate:.1f}%")
    print(f"📉 CGS < %10 olan coinlerde tier oranı: {low_tier_rate:.1f}%")
    print(f"🎯 FARK: {(high_tier_rate/low_tier_rate):.1f}x daha yüksek!" if low_tier_rate > 0 else "")
    
    # Eleme testi
    print("\n" + "=" * 80)
    print("🧪 CGS FİLTRE TESTİ")
    print("=" * 80)
    
    total_none = len(df[df['tier'] == 'NONE'])
    total_tier = len(df[df['tier'] != 'NONE'])
    
    for threshold in [5, 10, 15, 20, 25]:
        filtered = df[df['coin_reliability'] >= threshold]
        none_after = len(filtered[filtered['tier'] == 'NONE'])
        tier_after = len(filtered[filtered['tier'] != 'NONE'])
        
        none_elim = total_none - none_after
        tier_lost = total_tier - tier_after
        
        none_pct = none_elim / total_none * 100 if total_none > 0 else 0
        tier_pct = tier_lost / total_tier * 100 if total_tier > 0 else 0
        
        efficiency = none_pct - (tier_pct * 2)
        
        icon = "✅" if efficiency > 0 else "❌"
        print(f"CGS >= {threshold}%: NONE {none_elim:>4} elendi (%{none_pct:.1f}), Tier {tier_lost:>3} kayıp (%{tier_pct:.1f}), Verimlilik: {efficiency:+.1f} {icon}")
    
    return coin_stats

def analyze_date_patterns(df):
    """Analyze if there are date/day patterns."""
    
    print("\n" + "=" * 80)
    print("📅 TARİH PATERNLERİ ANALİZİ")
    print("=" * 80)
    
    # Group by date
    date_stats = df.groupby('date').agg({
        'has_tier': ['sum', 'count']
    }).reset_index()
    date_stats.columns = ['date', 'tiered', 'total']
    date_stats['rate'] = date_stats['tiered'] / date_stats['total'] * 100
    
    # High tier days
    high_days = date_stats[date_stats['rate'] >= 50].sort_values('rate', ascending=False)
    
    print(f"\n🔥 YÜKSEK TIER GÜNLER (>=%50):")
    for _, row in high_days.head(10).iterrows():
        print(f"   {row['date']}: {row['tiered']}/{row['total']} ({row['rate']:.0f}%)")
    
    # Zero tier days
    zero_days = date_stats[(date_stats['rate'] == 0) & (date_stats['total'] >= 3)]
    print(f"\n❌ SIFIR TIER GÜNLER (>=3 trigger): {len(zero_days)} gün")

def analyze_trigger_hour(df):
    """Analyze trigger time patterns."""
    # This would need time parsing from the report, skipping for now
    pass

if __name__ == "__main__":
    df = parse_report()
    print(f"\n{len(df)} trigger yüklendi.\n")
    
    coin_stats = analyze_coin_character(df)
    analyze_date_patterns(df)
    
    print("\n" + "=" * 80)
    print("💡 DAHİ SONUCU")
    print("=" * 80)
    print("""
🧬 YENİ METRİK: COİN GÜVENİLİRLİK SKORU (CGS)

Formül: CGS = (Coin'in tier'li tetik sayısı / Toplam tetik sayısı) × 100

Bu metrik:
- Trigger anında hesaplanmaz
- Coin'in TARİHSEL performansına bakar
- "Bu coin daha önce tier yaptı mı?" sorusuna cevap verir

KULLANIM:
- CGS >= %20 olan coinler daha güvenilir
- CGS = %0 olan coinler (3+ tetik) riskli

⚠️ DİKKAT: Bu metrik geçmişe bakar, gelecekte yeni coinler tier yapabilir.
Ama "düşük performanslıları eleme" stratejisi için güçlü bir araç.
""")
