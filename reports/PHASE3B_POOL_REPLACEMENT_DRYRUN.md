# Phase 3B: Replacement v1 (BONUS) - DRY-RUN + Court-Gated

**Tarih:** 2025-12-23
**Durum:** ✅ COMPLETED

---

## 1. Özet
Kapasite doluyken (capacity=0) daha iyi bir intent gelirse, en zayıf pozisyonu değiştirme önerisi sunan sistem kuruldu. **Emir gönderilmez, sadece öneri. İnsan onayı gerekir.**

---

## 2. Değişiklikler

### Yeni Modüller
*   **`replacement_engine_v1.py`:** Değiştirme mantığı (worst position vs best intent karşılaştırması).

### Model Güncellemeleri
*   **[MODIFY] `pool_models_v1.py`:** `PoolReplacementCandidateV1`, `PoolReplacementReportV1` eklendi.

### Engine Entegrasyonu
*   **[MODIFY] `pool_engine_v1.py`:** `run_pool_phase3b_replacement` fonksiyonu eklendi.

### UI
*   **[MODIFY] `matrix_v4_tab.py`:** **"♻️ Replacement (DRY-RUN)"** paneli eklendi.

---

## 3. Replacement Mantığı

| Adım | Kriter | Sonuç |
|------|--------|-------|
| 1 | `replacement_enabled=False` | SKIPPED (DISABLED) |
| 2 | `capacity > 0` | SKIPPED (CAPACITY_AVAILABLE) |
| 3 | `reconcile_verdict != OK` | SKIPPED (DRIFT) |
| 4 | `kill_switch/risk_limiter` | SKIPPED |
| 5 | `delta < min_delta` | SKIPPED (NO_BETTER_THAN_WORST) |
| 6 | `delta >= min_delta` | **SUGGESTED** |

**Defaults:**
- `replacement_enabled`: `False`
- `replacement_min_delta`: `15.0`
- `replacement_min_rank`: `90.0`

---

## 4. Doğrulama

### Testler
`tests/matrix/pool/test_pool_phase3b_replacement.py`:

1. **test_disabled_skipped:** Disabled → SKIPPED (DISABLED) ✅
2. **test_capacity_available_skipped:** Capacity>0 → SKIPPED ✅
3. **test_drift_skipped:** Drift → SKIPPED (DRIFT) ✅
4. **test_suggested_replacement:** Delta ≥ 15 → SUGGESTED ✅
5. **test_not_better_skipped:** Delta < 15 → SKIPPED ✅

**Test Çıktısı:**
```bash
tests/matrix/pool/test_pool_phase3b_replacement.py ..... [100%]
5 passed in 0.04s
```

**Core Regression:**
```bash
7 passed, 290 deselected
```

---

## 5. Sonuç
Replacement artık "bonus öneri" olarak çalışıyor. Varsayılan kapalı, aktif edildiğinde insan onayı gerektirir.
