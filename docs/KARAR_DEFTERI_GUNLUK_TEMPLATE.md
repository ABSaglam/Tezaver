# 🦅 Tezaver-Mac: Günlük Operasyon Kaydı

**Tarih:** {{TARİH}}
**Coin:** {{COIN}}
**Mod:** Offline Laboratuvar Modu v1.0  
**Operatör:** Ali (Tezaver-Mac)

---

## 1. 🔮 Bilgelik (Wisdom) – İlk Durum Değerlendirmesi

Bilgelik sekmesi ve Bilge Kartlar'a göre:

- **Time-Labs – 1 Saat:**
  - Toplam rally sayısı: **{{TL_1H_EVENT_COUNT}}**
  - Yüksek kalite oranı: **{{TL_1H_HQ_RATIO}}%**
  - Ortalama kalite puanı: **{{TL_1H_QUALITY_MEAN}}**
  - Hakim kova (en çok event’in olduğu bucket): **{{TL_1H_DOMINANT_BUCKET}}**

- **Time-Labs – 4 Saat (varsa):**
  - Toplam rally sayısı: **{{TL_4H_EVENT_COUNT}}**
  - Genel durum: **{{TL_4H_ENV_STATE}}** (ör: HOT / NEUTRAL / COLD / CHAOTIC)

- **Strateji Uyumu (Sim / Affinity / Promotion):**
  - Önerilen strateji: **{{BEST_STRATEGY_ID}}**  
  - Not: **{{BEST_STRATEGY_GRADE}}** (A+, A, B, C, D)
  - Statü: **{{BEST_STRATEGY_STATUS}}** (APPROVED / CANDIDATE / REJECTED / NONE)

**Analist Yorumu:**  
{{BURAYA KENDİ CÜMLEN}}  
(Örnek: “Sinyaller kaliteli ama mevcut preset’ler fazla katı, sim tarafı henüz eşleşmiyor.”)

---

## 2. 🚀 Yükseliş Lab – Detaylı Rally İncelemesi

### 2.1 Fast15 (15 Dakika)

- Olay sayısı: **{{F15_EVENT_COUNT}}**
- Hakim kova: **{{F15_DOMINANT_BUCKET}}**
- Ortalama kazanç: **{{F15_MEAN_GAIN}}**
- Ortalama tepeye mum: **{{F15_MEAN_BARS_TO_PEAK}}**
- Dikkat çekenler:  
  - **{{F15_SPECIAL_NOTES}}**
  - (Ör: “%20-30 kovasında 2 spike var, iğneli hareket, dikkatli olmak lazım.”)

### 2.2 Time-Labs (1 Saat)

- Olay sayısı: **{{TL_1H_EVENT_COUNT}}**
- %10-20 kovası event sayısı: **{{TL_1H_10P_20P_COUNT}}**
- Bu kovadaki ortalama kalite: **{{TL_1H_10P_20P_QUALITY_MEAN}}**
- Replay notu:  
  {{TL_1H_REPLAY_NOTES}}  
  (Ör: “%10+ hareketlerde kalite 88+; genelde temiz, düşük drawdown’lı hareketler.”)

---

## 3. 🧪 Sim Lab – Strateji Test Sonuçları

Çalıştırılan preset’ler: **{{RUN_PRESETS}}**  
(Ör: FAST15_SCALPER_V1, H1_SWING_V1, H4_TREND_V1)

- Toplam işlem sayısı: **{{SIM_TOTAL_TRADES}}**
- En iyi strateji: **{{BEST_STRATEGY_ID}}**  
  - Win-rate: **{{BEST_STRATEGY_WINRATE}}%**
  - Max Drawdown: **{{BEST_STRATEGY_MAX_DD}}%**
  - Net PnL: **{{BEST_STRATEGY_NET_PNL}}**
  - Statü: **{{BEST_STRATEGY_STATUS}}** (APPROVED / CANDIDATE / REJECTED / NONE)

Eğer **SIM_TOTAL_TRADES = 0** ise:

> “Simülasyon şu an *işlemsiz* (num_trades=0). Lab verisi kaliteli olduğu halde sim giremiyorsa, preset ayarları muhtemelen fazla muhafazakardır. Özellikle:
> - RSI eşikleri
> - 4h Trend Soul barajı
> - Shape (clean-only) filtreleri  
> gözden geçirilmeli ve hafif gevşetilerek tekrar test edilmeli.”

---

## 4. 📝 Günlük Karar & Eylem Planı

**Otomatik Bot Kararı:**  
{{AUTO_DECISION}}  
(Ör: “BUGÜN OTOMATİK ALIM YOK – Sim tarafında APPROVED strateji yok.”)

**Manuel İşlem Kararı:**

- Tercih edilen zaman dilimi (lane): **{{PREFERRED_TF}}** (15m / 1h / 4h)
- Hedeflenen rally tipi: **{{TARGET_RALLY_TYPE}}**  
  (Ör: “1 Saatlik %10+ clean ralliler”)

**Eylem Planı:**

1. {{STEP_1}}
2. {{STEP_2}}
3. {{STEP_3}}

(Örnek:
1. Botu devreye almıyorum.
2. 1H Time-Labs’te kalite skoru 80+ olan sinyalleri manuel takip ediyorum.
3. Akşam, H1_SWING preset’inin filtrelerini hafif gevşetip sim tekrarı yapacağım.)

---

**Not:**  
_Bu kayıt Tezaver-Mac’in Bilgelik, Yükseliş Lab, Sim Lab ve Offline Lab verileri kullanılarak hazırlanmıştır._
