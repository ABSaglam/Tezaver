# Phase 1: ApprovedRallyBundle Manifest v2 (trigger_spec_v1 + policy_spec_v1)

**Tarih:** 2025-12-23
**Durum:** ✅ COMPLETED

---

## 1. Özet
**ApprovedRallyBundleManifest** yapısı v2'ye genişletilerek `trigger_spec_v1` ve `policy_spec_v1` alanları eklendi. Bu alanlar Pool motorunun (Phase 2+) deterministik intent üretimi için kritik verileri taşır.

*   **Geriye Dönük Uyumluluk (Backward Compatible):** Mevcut v1 bundle'lar (eksik alanlarla) sorunsuzca yüklenmeye devam eder. Yeni alanlar `None` olarak işaretlenir.
*   **Schema Validasyon:** Eğer v2 alanları varsa, katı şema kontrolü (ör. `type` veya `exit_policy` zorunluluğu) uygulanır. Hatalıysa paket reddedilir.
*   **UI Entegrasyonu:** Matrix v4 Bundles tablosuna "Trigger" ve "Policy" sütunları eklendi.

---

## 2. Değişiklikler

### Model & Validation
*   **[MODIFY] `bundle_models_v1.py`:**
    *   `ApprovedRallyBundleManifestV1` sınıfına `trigger_spec_v1` ve `policy_spec_v1` (Optional[Dict]) eklendi.
    *   `from_dict` metodu, bu alanların varlığını ve zorunlu alt alanlarını (`type`, `exit_policy`) denetler hale getirildi.

### UI (Matrix V4)
*   **[MODIFY] `matrix_v4_tab.py`:**
    *   `render_bundles` fonksiyonunda tablo verilerine `Trigger` ve `Policy` sütunları eklendi.
    *   Veri yoksa "N/A", veri varsa ilgili tip (ör. "CLOSED_BAR_SIGNAL", "ATR") gösterilir.

---

## 3. Doğrulama (Verification)

### Otomatik Testler
Yeni oluşturulan `tests/matrix/bundles/test_bundle_models_v2.py` ile aşağıdaki senaryolar başarıyla test edildi:

1.  **v1_compatibility:** Eski tip manifestlerin hatasız yüklendiği ve yeni alanların `None` olduğu doğrulandı.
2.  **v2_valid:** Yeni alanları içeren manifestlerin doğru parse edildiği doğrulandı.
3.  **v2_invalid_trigger:** `trigger_spec_v1` içinde `type` eksikse `ValueError` fırlatıldığı doğrulandı.
4.  **v2_invalid_policy:** `policy_spec_v1` içinde `exit_policy` eksikse `ValueError` fırlatıldığı doğrulandı.

**Test Çıktısı (Yeni Testler):**
```bash
tests/matrix/bundles/test_bundle_models_v2.py ...... [100%]
6 passed in 0.03s
```

**Regresyon Testi (Core Gate):**
Mevcut sistemin bozulmadığı doğrulandı.
```bash
tests/matrix/test_live_v1.py . 
...
tests/matrix/test_telemetry_schema.py . 
7 passed, 263 deselected
```

### UI Görünümü
Bundles tablosunda yeni sütunlar (Trigger, Policy) başarıyla entegre edildi. Mevcut bundle'lar için "N/A" değeri görülmesi normaldir (henüz v2 paket üretilmediği için).

---

## 4. Sonuç
Matrix sistemi artık Dökümhane'den gelecek zenginleştirilmiş (v2) bundle'ları kabul etmeye hazırdır. Bu paketler geldiğinde Pool motoru trigger ve exit policy verilerini kullanarak işlem açıp kapatabilecektir.
