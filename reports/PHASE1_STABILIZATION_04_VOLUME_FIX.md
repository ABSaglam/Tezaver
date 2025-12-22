# FAZ 1 — Stabilizasyon Raporu #4 (PHASE1_STABILIZATION_04_VOLUME_FIX)

**Tarih:** 2025-12-22  
**Durum:** ✅ FIXED

---

## Sorun Tanımı
**Bug:** 15m Rally grafiği "Feature merge failed" uyarısı verse bile çizilmeliydi, ancak "Grafik hatası: 'volume'" hatasıyla tamamen boş geliyordu.
**Root Cause:**
1. Veri setinde `volume` sütunu eksik olabilir veya ismi farklı (`vol` vs.) olabilir.
2. Merge işlemi (fallback durumunda) sütunları korusa da, eğer kaynakta yoksa `render_rally_event_chart` fonksiyonu `df['volume']` erişiminde patlıyordu.
3. ONY stüdyosu da aynı hataya açıktı.

---

## Çözüm Özeti

### 1. Loader İyileştirmesi (`chart_area.py:load_history_data`)
- Parquet yüklendiğinde `vol` veya `Volume` sütunları varsa otomatik olarak `volume` ismine dönüştürülüyor.
- `datetime`, `timestamp` normalizasyonu zaten vardı.

### 2. Grafik Çizim Robustness (`render_rally_event_chart` & `render_sniper_studio_chart`)
- Hacim (Volume) barlarını çizen bloklar `if 'volume' in df.columns:` kontrolüne alındı.
- Eğer hacim verisi yoksa, grafik patlamaz; sadece hacim barları çizilmez (Fiyat, RSI, MACD çizilmeye devam eder).

### 3. Syntax Fix
- `render_sniper_studio_chart` içinde yapılan değişiklik sırasında oluşan parantez hatası giderildi.

---

## Beklenen Sonuç
- Coin Detay -> Rally -> 15m sekmesi artık grafik göstermelidir.
- Eğer hacim verisi varsa, hacim barları görünür.
- Eğer hacim verisi yoksa, grafik görünür ama 2. satır boş kalır.
- "Debug" kutucuğu ile `df_history` sütunları kontrol edilebilir.

---

## Değişen Dosyalar

| Aksiyon | Dosya |
|---------|-------|
| **MODIFY** | `src/tezaver/ui/chart_area.py` (Volume renaming + Conditional plotting) |

---

## Doğrulama
Coin Detay -> Rally -> 15m sekmesini açın.
Grafik görünmelidir.
