#!/usr/bin/env python3
"""
Rally DNA by Coin Cluster - Analyze rallies per coin DNA cluster.
"""

import pandas as pd
import numpy as np
import re
from pathlib import Path
from collections import defaultdict

def parse_rallies_from_report(report_path):
    """Parse all rallies from Ayaş Tüneli report."""
    with open(report_path, 'r') as f:
        content = f.read()
    
    rallies = []
    
    # Pattern: SYMBOL(TIER+/-GAIN%)
    # Diamond: D+30%
    # Gold: G+15%
    # Silver: S+5%
    # Negative: -TIER:-XX%
    
    # Positive rallies
    pattern_positive = r'(\w+)\((D|G|S)\+(\d+)%\)'
    for match in re.finditer(pattern_positive, content):
        symbol = match.group(1)
        tier = {'D': 'DIAMOND', 'G': 'GOLD', 'S': 'SILVER'}[match.group(2)]
        gain = int(match.group(3))
        rallies.append({
            'symbol': f"{symbol}USDT",
            'tier': tier,
            'gain_pct': gain,
            'direction': 'UP'
        })
    
    # Negative
    pattern_negative = r'(\w+)\(-(\w+):-(\d+)%\)'
    for match in re.finditer(pattern_negative, content):
        symbol = match.group(1)
        tier = match.group(2)
        loss = int(match.group(3))
        rallies.append({
            'symbol': f"{symbol}USDT",
            'tier': f"-{tier}",
            'gain_pct': -loss,
            'direction': 'DOWN'
        })
    
    return pd.DataFrame(rallies)

def analyze_cluster_rallies(cluster_name, cluster_coins, df_rallies):
    """Analyze rallies for a specific coin cluster."""
    # Filter rallies for this cluster
    cluster_rallies = df_rallies[df_rallies['symbol'].isin(cluster_coins)]
    
    if len(cluster_rallies) == 0:
        return None
    
    # Separate by tier (only positive)
    positive_rallies = cluster_rallies[cluster_rallies['direction'] == 'UP']
    
    result = {
        'cluster': cluster_name,
        'total_rallies': len(positive_rallies),
        'unique_coins': positive_rallies['symbol'].nunique()
    }
    
    for tier in ['DIAMOND', 'GOLD', 'SILVER']:
        tier_data = positive_rallies[positive_rallies['tier'] == tier]
        result[f'{tier.lower()}_count'] = len(tier_data)
        result[f'{tier.lower()}_avg_gain'] = tier_data['gain_pct'].mean() if len(tier_data) > 0 else 0
        result[f'{tier.lower()}_max_gain'] = tier_data['gain_pct'].max() if len(tier_data) > 0 else 0
        
        # Top performers
        if len(tier_data) > 0:
            top_coins = tier_data.groupby('symbol')['gain_pct'].count().nlargest(5).index.tolist()
            result[f'{tier.lower()}_top_coins'] = [c.replace('USDT', '') for c in top_coins]
    
    return result

def main():
    print("=" * 80)
    print("🧬 RALLİ DNA ANALİZİ - KÜME BAZLI")
    print("=" * 80)
    
    # Load Coin DNA classification
    coin_dna = pd.read_csv('library/coin_dna/final_classification.csv')
    
    # Load rallies from report
    report_path = Path('analysis/ayas_tuneli_2y_120h_rapor.md')
    df_rallies = parse_rallies_from_report(report_path)
    
    print(f"📊 Toplam ralli: {len(df_rallies)}")
    print(f"   Pozitif: {len(df_rallies[df_rallies['direction'] == 'UP'])}")
    print(f"   Negatif: {len(df_rallies[df_rallies['direction'] == 'DOWN'])}")
    
    # Analyze each cluster
    clusters = ['ROCKET', 'ACTIVE', 'CALM', 'NEEDLE', 'STABLE']
    
    all_results = []
    
    for cluster in clusters:
        cluster_coins = coin_dna[coin_dna['cluster_name'] == cluster]['symbol'].tolist()
        
        print(f"\n" + "=" * 80)
        print(f"🎯 {cluster} KÜMESİ ({len(cluster_coins)} koin)")
        print("=" * 80)
        
        result = analyze_cluster_rallies(cluster, cluster_coins, df_rallies)
        
        if result is None:
            print("  ❌ Bu kümede Ayaş Tüneli rallisi yok")
            continue
        
        all_results.append(result)
        
        print(f"\n📈 Toplam: {result['total_rallies']} ralli, {result['unique_coins']} farklı koin")
        
        for tier in ['diamond', 'gold', 'silver']:
            count = result[f'{tier}_count']
            avg = result[f'{tier}_avg_gain']
            max_g = result[f'{tier}_max_gain']
            top = result.get(f'{tier}_top_coins', [])
            
            tier_emoji = {'diamond': '💎', 'gold': '🥇', 'silver': '🥈'}[tier]
            print(f"\n  {tier_emoji} {tier.upper()}")
            print(f"     Sayı: {count}")
            print(f"     Ortalama Kazanç: +{avg:.1f}%")
            print(f"     Max Kazanç: +{max_g}%")
            if top:
                print(f"     En Aktif: {', '.join(top[:5])}")
    
    # Save summary
    if all_results:
        df_summary = pd.DataFrame(all_results)
        output_path = Path('library/rally_dna/cluster_rally_summary.csv')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_summary.to_csv(output_path, index=False)
        print(f"\n📁 Özet kaydedildi: {output_path}")

if __name__ == "__main__":
    main()
