# FAZ 1 — Stabilizasyon Raporu #5 (PHASE1_STABILIZATION_05_DATA_LOADER)

**Tarih:** 2025-12-22  
**Durum:** ✅ FIXED (Critical Data Handling)

---

## Sorun Tanımı
**Bug:** 15m Rally grafiği, kodun 1h ile eşitlenmesine rağmen görünmüyordu.
**Root Cause:** `history_15m.parquet` dosyasının yapısı 1h/4h dosyalarından farklıydı:
1. **Zaman Sütunu:** Standart `open_time` veya `timestamp` (ms) yerine `ts` adında ve saniye tabanlı (UNIX seconds) bir sütun kullanıyordu. Loader bunu tanımadığı için `open_time` oluşmuyor ve grafik x-ekseni hatası alıyordu.
2. **Hacim Sütunu:** Dosyada `volume` verisi hiç bulunmuyordu.

---

## Çözüm

### Data Loader Güncellemesi (`chart_area.py`)
`load_history_data` fonksiyonuna yeni bir mantık eklendi:
- Eğer veri setinde `ts` sütunu varsa, bunu otomatik olarak **saniye bazlı** (`unit='s'`) Datetime objesine çevirip `open_time` olarak atıyor.
- Bu sayede 15m'lik eski/farklı formatlı veriler de sistem tarafından doğru okunup grafik çizilebiliyor.

### Hacim Koruması
Önceki fix (#4) sayesinde, Hacim verisi olmasa bile grafik patlamıyor, sadece fiyat mumlarını çiziyor.

---

## Sonuç
Coin Detay -> Rally -> 15m sekmesi artık:
1. Veriyi doğru okuyor (`ts` -> `open_time`).
2. Event tarihini history içinde doğru eşleştiriyor.
3. Grafiği başarıyla çiziyor.

Tüm stabilizasyon adımları tamamlanmıştır.
