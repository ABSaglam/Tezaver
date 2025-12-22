# FAZ 1 — Stabilizasyon Raporu #1 (PHASE1_STABILIZATION_01_OPEN_TIME)

**Tarih:** 2025-12-22  
**Durum:** ✅ FIXED

---

## Sorun Tanımı
**Bug:** Coin Detail → Rally → 15m sekmesinde chart'lar eksikti ve UI "Feature merge failed: 'open_time'" hatası veriyordu.
**Root Cause:** 15m verisetinde zaman sütunu farklı isimlendirilmiş olabilir veya features (RSI/MACD) verisi ile ana bar verisinin zaman damgaları (timezone-aware vs naive) eşleşmiyordu. Merge işlemi 'open_time' anahtarı üzerinden yapıldığı için failure oluşuyordu.

---

## Çözüm Özeti

### 1. `ensure_open_time` Utility
`src/tezaver/core/dataframe_utils.py` içinde yeni bir yardımcı fonksiyon oluşturuldu.
- Bu fonksiyon dataframe içindeki zaman sütununu otomatik tespit eder (`open_time`, `timestamp`, `date` vb. veya index).
- `open_time` adıyla standartlaştırır.
- Timezone'u kaldırır (naive datetime yapar) böylece merge güvenli hale gelir.

### 2. Chart Area Fix
`src/tezaver/ui/chart_area.py` içindeki `render_rally_event_chart` fonksiyonu güncellendi.
- Manuel timezone dönüşümleri yerine `ensure_open_time` kullanıldı.
- Hem tarihsel bar verisi hem de indicator verisi merge öncesi normalize edildi.
- Merge öncesi her iki tarafta da `open_time` olup olmadığı kontrol edildi.

---

## Test Sonuçları

**Test Dosyası:** `tests/core/test_dataframe_utils.py`

```bash
pytest tests/core/test_dataframe_utils.py -v
```

**Çıktı:**
```
tests/core/test_dataframe_utils.py::test_ensure_open_time_from_column PASSED
tests/core/test_dataframe_utils.py::test_ensure_open_time_from_alt_columns PASSED
tests/core/test_dataframe_utils.py::test_ensure_open_time_from_index PASSED
tests/core/test_dataframe_utils.py::test_ensure_open_time_merge_compat PASSED
```

---

## Değişen Dosyalar

| Aksiyon | Dosya |
|---------|-------|
| **YENİ** | `src/tezaver/core/dataframe_utils.py` |
| **YENİ** | `tests/core/test_dataframe_utils.py` |
| **MODIFY** | `src/tezaver/ui/chart_area.py` |

---

## Manuel Doğrulama
Coin Detail → Rally → 15m tab'ı açıldığında artık chart render ediliyor ve merge hatası alınmıyor.
