# Phase 3C: Replacement Plan v1.1 (Close/Open, DRY-RUN)

**Tarih:** 2025-12-23
**Durum:** ✅ COMPLETED

---

## 1. Özet
Replacement SUGGESTED ise atomik **Close → Open** planı üreten sistem kuruldu. **Emir gönderilmez, insan onayı gerekir.**

---

## 2. Değişiklikler

### Yeni Modüller
*   **`replacement_plan_engine_v1.py`:** Atomik plan oluşturma mantığı.

### Model Güncellemeleri
*   **[MODIFY] `pool_models_v1.py`:** `PoolClosePlanItemV1`, `PoolOpenPlanItemV1`, `PoolReplacementPlanReportV1` eklendi.

### Engine Entegrasyonu
*   **[MODIFY] `pool_engine_v1.py`:** `run_pool_phase3c_replacement_plan` fonksiyonu eklendi.

### UI
*   **[MODIFY] `matrix_v4_tab.py`:** Replacement panelinde Plan detayları gösterimi.

---

## 3. Plan Yapısı

```json
{
  "atomic_order": ["CLOSE_POSITION", "OPEN_POSITION"],
  "close_plan": {
    "action": "CLOSE_POSITION",
    "pos_id": "weak_pos_1",
    "close_mode": "MARKET_DRYRUN"
  },
  "open_plan": {
    "action": "OPEN_POSITION",
    "intent_id": "strong_intent_1",
    "notional": 100.0,
    "open_mode": "MARKET_DRYRUN"
  },
  "requires_human_confirm": true
}
```

---

## 4. Doğrulama

### Testler
`tests/matrix/pool/test_pool_phase3c_replacement_plan.py`:

1. **test_no_suggested_replacement_skipped:** Öneri yok → SKIPPED ✅
2. **test_suggested_creates_plan:** Öneri var → plan Close+Open ✅
3. **test_drift_skipped:** Drift → SKIPPED ✅
4. **test_policy_spec_copied:** Bundle policy kopyalanıyor ✅

**Test Çıktısı:**
```bash
tests/matrix/pool/test_pool_phase3c_replacement_plan.py .... [100%]
4 passed in 0.04s
```

**Core Regression:**
```bash
7 passed, 294 deselected
```

---

## 5. Sonuç
Replacement planı artık atomik ve güvenli. İnsan onayı olmadan asla uygulanmaz.
