#!/usr/bin/env python3
"""
Extract t-stages (state timeline) from rally 15M data
Creates timeline showing when each state occurs during rallies
"""

from datetime import datetime
import json

# 1️⃣ Veriyi yükle
with open("/Users/alisaglam/TezaverMac/data/algo_rally_days_15m.json", "r") as f:
    rally_data = json.load(f)

# 2️⃣ Fonksiyon: State belirleme (örnek ASM mantığı)
def determine_state(m):
    # Handle None values
    if any(m[k] is None for k in ['ema9', 'ema21', 'ema50', 'rsi', 'atr', 'atr_ma', 'vol_ratio']):
        return "IDLE"
    
    # Örnek basitleştirilmiş mantık; COMMITTED koşulları burada yer alacak
    if m['ema9'] > m['ema21'] > m['ema50'] and 55 < m['rsi'] < 75 and m['vol_ratio'] > 1.5:
        return "COMMITTED"
    elif m['atr'] < m['atr_ma'] * 0.7:
        return "SQUEEZED"
    elif m['ema9'] > m['ema21']:
        return "AWAKENING"
    elif m['rsi'] > 80:
        return "EXHAUSTED"
    else:
        return "IDLE"

# 3️⃣ Her ralli günü için t zamanlarını çıkar
rally_timeline = []

for day in rally_data:
    day_result = {
        "date": day["date"], 
        "tier": day["tier"],
        "rally_pct": day["rally_pct"],
        "t_stages": {}, 
        "states": []
    }
    
    for m in day["15m_data"]:
        state = determine_state(m)
        day_result["states"].append({"timestamp": m["timestamp"], "state": state})
    
    # t0-t4 atamaları (ilk SQUEEZED -> AWAKENING -> COMMITTED -> EXTENSION -> EXHAUSTED)
    for stage in ["SQUEEZED", "AWAKENING", "COMMITTED", "EXTENSION", "EXHAUSTED"]:
        for s in day_result["states"]:
            if s["state"] == stage:
                day_result["t_stages"][stage] = s["timestamp"]
                break  # ilk occurrence
    
    rally_timeline.append(day_result)

# 4️⃣ Sonucu JSON olarak kaydet
with open("/Users/alisaglam/TezaverMac/data/algo_rally_timeline_15m.json", "w") as f:
    json.dump(rally_timeline, f, indent=2)

print("✅ T zamanları ve ASM state haritası başarıyla çıkarıldı.")
print(f"📁 Çıktı: /Users/alisaglam/TezaverMac/data/algo_rally_timeline_15m.json")

# 5️⃣ Özet istatistikler
print("\n📊 ÖZET İSTATİSTİKLER:")
print(f"Toplam rally günü: {len(rally_timeline)}")

stages_found = {}
for stage in ["SQUEEZED", "AWAKENING", "COMMITTED", "EXTENSION", "EXHAUSTED"]:
    count = sum(1 for day in rally_timeline if stage in day["t_stages"])
    stages_found[stage] = count
    print(f"  {stage}: {count}/{len(rally_timeline)} günde tespit edildi ({count/len(rally_timeline)*100:.1f}%)")

# 6️⃣ Örnek çıktı göster
print("\n📋 İLK 3 RALLİ ÖRNEĞİ:")
for i, day in enumerate(rally_timeline[:3]):
    print(f"\n{i+1}. {day['date']} ({day['tier']}, {day['rally_pct']:+.1f}%)")
    print(f"   Tespit edilen stage'ler:")
    for stage, ts in day['t_stages'].items():
        print(f"     {stage}: {ts}")
