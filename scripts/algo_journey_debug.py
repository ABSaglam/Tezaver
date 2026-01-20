
import sys
import os
import pandas as pd
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ALGOUSDT'
    
    # 1. Toplam Ralli Sayısı
    rallies = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    print(f"📊 ALGO TOPLAM RALLİ SAYISI: {len(rallies)}")
    
    tier_counts = {'DIAMOND': 0, 'GOLD': 0, 'SILVER': 0}
    for d, data in rallies.items():
        tier_counts[data[0]] += 1
    print(f"   - DIAMOND: {tier_counts['DIAMOND']}")
    print(f"   - GOLD:    {tier_counts['GOLD']}")
    print(f"   - SILVER:  {tier_counts['SILVER']}")
    
    # 2. Journey Days Analysis
    # The 59 days include BOTH:
    #   - T-0 (Actual Rally Day)
    #   - T-1, T-3, T-5, T-7, T-14, T-21 (Preparation Days BEFORE a rally)
    
    rally_dates = list(rallies.keys())
    journey_offsets = [1, 3, 5, 7, 14, 21]
    
    journey_dates_map = {}
    for rd in rally_dates:
        journey_dates_map[rd] = f"T-0 (RALLİ: {rallies[rd][0]})"
        for offset in journey_offsets:
            prep_day = rd - timedelta(days=offset)
            if prep_day not in journey_dates_map:
                journey_dates_map[prep_day] = f"T-{offset} (Ralli öncesi: {rd} {rallies[rd][0]})"
    
    print(f"\n📅 JOURNEY DAYS TOPLAMI: {len(journey_dates_map)}")
    
    # 3. What were the 59 surviving days?
    # Load the profile data to check
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    df_h4 = pd.read_parquet(h4_path)
    df_h4['datetime'] = pd.to_datetime(df_h4['timestamp'], unit='ms')
    df_h4 = df_h4[df_h4['datetime'] < pd.Timestamp(TRAIN_CUTOFF)]
    
    midnight = df_h4[df_h4['datetime'].dt.hour == 0].copy()
    midnight['date'] = midnight['datetime'].dt.date
    
    # Mark which days are in journey
    midnight['is_journey'] = midnight['date'].isin(journey_dates_map.keys())
    
    journey_rows = midnight[midnight['is_journey']]
    
    print(f"\n🔍 59 GÜNÜN DETAYI:")
    print("-" * 60)
    
    # Note: 59 is the number of surviving profile OCCURRENCES
    # A profile can appear on multiple days
    # Let me list the actual days that matched surviving profiles
    
    # From the output, we know 26 were direct rallies
    # The remaining 33 were "preparation days" (T-1 to T-21)
    
    print("\n🎯 RALLİ GÜNLERİ (T-0):")
    count_t0 = 0
    for d, info in sorted(journey_dates_map.items()):
        if "T-0" in info:
            if d in rallies:
                count_t0 += 1
    print(f"   Toplam T-0 (Ralli Günü): {count_t0}")
    
    print("\n⏳ HAZIRLIK GÜNLERİ (T-1, T-3, T-5, T-7, T-14, T-21):")
    prep_count = len(journey_dates_map) - count_t0
    print(f"   Toplam Hazırlık Günü: {prep_count}")
    
    print("\n" + "="*60)
    print("📝 AÇIKLAMA:")
    print("="*60)
    print("""
59 gün açıldı demek şudur:
- 38 farklı "Yolculuk Profili" hayatta kaldı.
- Bu profiller TOPLAM 59 günde gözlendi.
- Bu 59 günün hepsi "Yolculuk Hafızası"nda:
  - Ya doğrudan ralli günü (T-0)
  - Ya da ralliden 1-21 gün önceki hazırlık günü

ÖNEMLI:
- Sistem 24 SAAT'LİK değil, GÜN BAŞI (00:00 UTC) analizi yapar.
- Her gün için tek bir karar verir: AÇIK / KAPALI
- Açık olan günler "Ralliye giden yolculuktaki günler"dir.
- Bazıları DOĞRUDAN ralli, bazıları RALLİ ÖNCESİ hazırlık.
""")

if __name__ == "__main__":
    main()
