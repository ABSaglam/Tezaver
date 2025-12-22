# FAZ 1 — Stabilizasyon Raporu #2 (PHASE1_STABILIZATION_02_MISSING_CHART)

**Tarih:** 2025-12-22  
**Durum:** ✅ FIXED

---

## Sorun Tanımı
**Bug:** Coin Detail → Rally → 15m sekmesinde "Feature merge failed" uyarısı gitmiş olsa da, grafik boş/eksik geliyordu.
**Root Cause:** `open_time` eşleşmesi tam sağlanamadığında `pd.merge(how='left')` teknik olarak satırları korusa da, eğer merge key tipleri uyuşmazlığı veya boş dataframe durumlarında UI kod akışı grafiği çizmeden çıkabiliyordu. Ayrıca features (RSI/MACD) verisi ile bar verisi arasında milisaniye/dakika farkları olduğunda exact merge başarısız oluyor ve features gösterilmiyordu.

---

## Çözüm Özeti

### 1. `safe_merge_features` Utility
`src/tezaver/core/dataframe_utils.py` içine yeni bir fonksiyon eklendi:
- **Fallback Garantisi:** Merge işlemi ne olursa olsun (başarılı/başarısız), en kötü ihtimalle sadece fiyat barlarını içeren dataframe döner. Grafik asla boş kalmaz.
- **ASOF Merge Desteği:** Exact merge (tam eşleşme) sonucu features bulunamazsa, `pd.merge_asof` ile `tolerance=15m` aralığında en yakın feature eşleşmesi denenir.
- **Diagnostics:** Merge modu (exact, asof, fallback) ve eşleşme sayıları raporlanır.

### 2. Chart Area Entegrasyonu
`src/tezaver/ui/chart_area.py` güncellendi:
- `safe_merge_features` fonksiyonu kullanıldı.
- Eğer fallback moduna düşülürse (features eklenemezse), UI'da küçük bir uyarı ile "Rendering price only" bilgisi verilir.
- "Chart missing" durumu engellendi.

---

## Test Sonuçları

**Test Dosyası:** `tests/core/test_safe_merge.py`

```bash
pytest tests/core/test_safe_merge.py -v
```

**Çıktı:**
```
tests/core/test_safe_merge.py::test_safe_merge_exact_success PASSED
tests/core/test_safe_merge.py::test_safe_merge_fallback_empty_feats PASSED
tests/core/test_safe_merge.py::test_safe_merge_asof_recovery PASSED
tests/core/test_safe_merge.py::test_safe_merge_fallback_total_mismatch PASSED
```

---

## Değişen Dosyalar

| Aksiyon | Dosya |
|---------|-------|
| **MODIFY** | `src/tezaver/core/dataframe_utils.py` (safe_merge_features eklendi) |
| **MODIFY** | `src/tezaver/ui/chart_area.py` (render mantığı güncellendi) |
| **YENİ** | `tests/core/test_safe_merge.py` |

---

## Manuel Doğrulama
Coin Detail → Rally → 15m tab'ı açıldığında:
1. Normal durumda (keys match): Grafik + RSI/MACD görünür.
2. Key mismatch (örn: 1dk kayma): ASOF devreye girer, grafik + RSI/MACD görünür.
3. Features yok: Sadece fiyat grafiği görünür, "Rendering price only" uyarısı çıkar.
WARNING: Chart boş kalmaz.
