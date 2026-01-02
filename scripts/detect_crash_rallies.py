"""
Crash Rally Detector
====================

Piyasa çöküşünden oluşan "reflex rally"leri tespit eder ve ayırır.

CRASH kriterleri:
1. RSI < 10 (ekstrem oversold)
2. Price Change < -15% (7 bar içinde derin düşüş)
3. Volume Spike > 2.5x (panik satış)
4. Price vs EMA-9 < -15% (EMA'dan çok uzak)

Normal DIAMOND: Sağlıklı dip alım fırsatı
CRASH DIAMOND: Piyasa çöküşü reflex'i - farklı risk profili
"""

import pandas as pd
import numpy as np
from pathlib import Path

print("=" * 80)
print("CRASH RALLY DETECTOR")
print("=" * 80)

# Load clustering results
df = pd.read_csv('.tezaver_matrix/harmony_mining/diamond_clusters.csv')

print(f"\n📊 Toplam Diamond Rally: {len(df)}")

# Define CRASH criteria
CRASH_CRITERIA = {
    'rsi_threshold': 15,           # RSI < 15 = ekstrem oversold
    'price_drop_threshold': -12,   # 7 bar'da -12% veya daha fazla düşüş
    'volume_spike_threshold': 2.5,  # 2.5x normal hacim
    'ema_distance_threshold': -10   # EMA-9'dan %10+ uzak
}

print("\n🔍 CRASH Kriterleri:")
print(f"   1. RSI < {CRASH_CRITERIA['rsi_threshold']}")
print(f"   2. Price Drop > {CRASH_CRITERIA['price_drop_threshold']}%")
print(f"   3. Volume Spike > {CRASH_CRITERIA['volume_spike_threshold']}x")
print(f"   4. Price vs EMA-9 < {CRASH_CRITERIA['ema_distance_threshold']}%")

# Apply criteria
crash_mask = (
    (df['rsi'] < CRASH_CRITERIA['rsi_threshold']) |
    (df['price_change_pct'] < CRASH_CRITERIA['price_drop_threshold']) |
    (df['volume_ratio'] > CRASH_CRITERIA['volume_spike_threshold']) |
    (df['price_vs_ema9_pct'] < CRASH_CRITERIA['ema_distance_threshold'])
)

# Severity scoring (how many criteria matched)
severity_score = (
    (df['rsi'] < CRASH_CRITERIA['rsi_threshold']).astype(int) +
    (df['price_change_pct'] < CRASH_CRITERIA['price_drop_threshold']).astype(int) +
    (df['volume_ratio'] > CRASH_CRITERIA['volume_spike_threshold']).astype(int) +
    (df['price_vs_ema9_pct'] < CRASH_CRITERIA['ema_distance_threshold']).astype(int)
)

df['crash_severity'] = severity_score
df['is_crash'] = crash_mask

crash_rallies = df[df['is_crash']]
normal_rallies = df[~df['is_crash']]

print("\n" + "=" * 80)
print("SONUÇLAR")
print("=" * 80)

print(f"\n🔴 CRASH RALLIES: {len(crash_rallies)} ({len(crash_rallies)/len(df)*100:.1f}%)")
print(f"🟢 NORMAL RALLIES: {len(normal_rallies)} ({len(normal_rallies)/len(df)*100:.1f}%)")

# Analyze crash rallies
if len(crash_rallies) > 0:
    print("\n" + "=" * 80)
    print("CRASH RALLY ANALİZİ")
    print("=" * 80)
    
    print(f"\n📊 Ortalama Teknik Profil:")
    print(f"   RSI: {crash_rallies['rsi'].mean():.1f} (vs Normal: {normal_rallies['rsi'].mean():.1f})")
    print(f"   Price Drop: {crash_rallies['price_change_pct'].mean():.1f}% (vs Normal: {normal_rallies['price_change_pct'].mean():.1f}%)")
    print(f"   Volume Spike: {crash_rallies['volume_ratio'].mean():.2f}x (vs Normal: {normal_rallies['volume_ratio'].mean():.2f}x)")
    print(f"   EMA Distance: {crash_rallies['price_vs_ema9_pct'].mean():.1f}% (vs Normal: {normal_rallies['price_vs_ema9_pct'].mean():.1f}%)")
    
    # Severity distribution
    print(f"\n🔥 Crash Severity Dağılımı:")
    for severity in range(5):
        count = (crash_rallies['crash_severity'] == severity).sum()
        if count > 0:
            pct = count / len(crash_rallies) * 100
            stars = "⭐" * severity
            print(f"   {severity}/4 kritere uygun {stars}: {count} rally ({pct:.1f}%)")
    
    # Top crash symbols
    print(f"\n🔴 En Çok Crash Olan Coinler:")
    top_crash_symbols = crash_rallies['symbol'].value_counts().head(10)
    for sym, count in top_crash_symbols.items():
        print(f"   {sym}: {count}")
    
    # Extreme crashes (severity >= 3)
    extreme_crashes = crash_rallies[crash_rallies['crash_severity'] >= 3]
    print(f"\n🚨 Ekstrem Crash'ler (3+ kriter): {len(extreme_crashes)}")
    if len(extreme_crashes) > 0:
        print("   Örnekler:")
        for idx, row in extreme_crashes.head(10).iterrows():
            print(f"   - {row['symbol']} (ID: {row['rally_id']})")
            print(f"      RSI:{row['rsi']:.1f}, Drop:{row['price_change_pct']:.1f}%, Vol:{row['volume_ratio']:.1f}x")

# Analyze normal rallies
if len(normal_rallies) > 0:
    print("\n" + "=" * 80)
    print("NORMAL RALLY ANALİZİ")
    print("=" * 80)
    
    print(f"\n📊 Ortalama Teknik Profil:")
    print(f"   RSI: {normal_rallies['rsi'].mean():.1f}")
    print(f"   Price Drop: {normal_rallies['price_change_pct'].mean():.1f}%")
    print(f"   Volume: {normal_rallies['volume_ratio'].mean():.2f}x")
    print(f"   EMA Distance: {normal_rallies['price_vs_ema9_pct'].mean():.1f}%")
    
    print(f"\n🟢 En Çok Normal Rally Olan Coinler:")
    top_normal_symbols = normal_rallies['symbol'].value_counts().head(10)
    for sym, count in top_normal_symbols.items():
        print(f"   {sym}: {count}")

# Save results
output_dir = Path(".tezaver_matrix/harmony_mining")

# Add classification column
df['rally_type'] = df['is_crash'].map({True: 'CRASH', False: 'NORMAL'})

# Save classified data
output_file = output_dir / "diamond_crash_classification.csv"
df.to_csv(output_file, index=False)

print(f"\n✅ Sonuçlar kaydedildi: {output_file}")

# Create report
report_lines = []
report_lines.append("# Crash Rally Detection Report\n\n")

report_lines.append("## Özet\n\n")
report_lines.append(f"- **Toplam Diamond Rally:** {len(df)}\n")
report_lines.append(f"- **CRASH Rally:** {len(crash_rallies)} ({len(crash_rallies)/len(df)*100:.1f}%)\n")
report_lines.append(f"- **NORMAL Rally:** {len(normal_rallies)} ({len(normal_rallies)/len(df)*100:.1f}%)\n\n")

report_lines.append("## Crash Kriterleri\n\n")
report_lines.append(f"1. RSI < {CRASH_CRITERIA['rsi_threshold']}\n")
report_lines.append(f"2. Price Drop > {CRASH_CRITERIA['price_drop_threshold']}%\n")
report_lines.append(f"3. Volume Spike > {CRASH_CRITERIA['volume_spike_threshold']}x\n")
report_lines.append(f"4. Price vs EMA-9 < {CRASH_CRITERIA['ema_distance_threshold']}%\n\n")

report_lines.append("## Teknik Karşılaştırma\n\n")
report_lines.append("| Metrik | CRASH | NORMAL |\n")
report_lines.append("|--------|-------|--------|\n")
report_lines.append(f"| RSI | {crash_rallies['rsi'].mean():.1f} | {normal_rallies['rsi'].mean():.1f} |\n")
report_lines.append(f"| Price Drop | {crash_rallies['price_change_pct'].mean():.1f}% | {normal_rallies['price_change_pct'].mean():.1f}% |\n")
report_lines.append(f"| Volume | {crash_rallies['volume_ratio'].mean():.2f}x | {normal_rallies['volume_ratio'].mean():.2f}x |\n")
report_lines.append(f"| EMA Dist | {crash_rallies['price_vs_ema9_pct'].mean():.1f}% | {normal_rallies['price_vs_ema9_pct'].mean():.1f}% |\n\n")

report_lines.append("## Öneri\n\n")
report_lines.append("🔴 **CRASH Rallies:** Piyasa çöküşü sonrası reflex rally'ler. Yüksek risk, farklı dinamik. Şimdilik stratejiye dahil edilmemeli.\n\n")
report_lines.append("🟢 **NORMAL Rallies:** Sağlıklı oversold dip alımları. Strateji için uygun.\n")

with open(output_dir / "crash_detection_report.md", 'w') as f:
    f.writelines(report_lines)

print(f"✅ Rapor kaydedildi: crash_detection_report.md")

print("\n" + "=" * 80)
print("ÖNERİ")
print("=" * 80)
print(f"\n🎯 Stratejiye Dahil Edilecek: {len(normal_rallies)} NORMAL Diamond Rally")
print(f"❌ Stratejiden Hariç: {len(crash_rallies)} CRASH Rally")
print(f"\n📍 Bir sonraki adım: {len(normal_rallies)} NORMAL rally üzerinde Harmony Analysis")
print("=" * 80)
