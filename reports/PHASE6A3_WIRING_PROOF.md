# Phase 6A.3 Wiring: Risk Limiter Integration & Court Gates

**Tarih:** 2025-12-23
**Durum:** ✅ COMPLETED

---

## 1. Özet
Risk Limiter v1 (kernel) artık Phase 2C akışına bağlandı. Yeni risk raporu (V2) üretiliyor ve Court tarafından kontrol ediliyor.

---

## 2. Değişiklikler

### Wiring (Engine)
*   **`pool_engine_v1.py`:**
    *   `apply_limits()` entegrasyonu.
    *   `pool_risk_report_v2.json` üretimi (yeni).
    *   `pool_risk_report_v1.json` üretimi (legacy support).
    *   Return dict güncellemesi (statlar).

### Court
*   **`pool_court_models_v1.py`:** Scorecard'a `blocked_reasons_count` ve `limits` eklendi.
*   **`pool_jury_v1.py`:** Risk raporu V2 (öncelikli) veya V1 okuma mantığı.
*   **`pool_judge_v1.py`:** Yeni Gate'ler:
    *   `GLOBAL_RISK_OK`: Global cap aşılırsa IMPROVE.
    *   `PER_COIN_RISK_OK`: Per-coin cap aşılırsa IMPROVE.

### UI
*   **`matrix_v4_tab.py`:** Risk Bölümünde V2 raporu, limit kullanımı (%) ve blok sebepleri gösterimi.

---

## 3. Doğrulama

### Testler
```bash
tests/matrix/pool/test_pool_phase6a3_wiring_risk_report_v2.py ..
tests/matrix/pool_court/test_pool_phase6a3_court_risk_gates.py ....
6 passed in 0.06s
```

**Senaryolar:**
1.  **V2 Generation:** Engine v2 ve v1 raporlarını aynı anda üretir.
2.  **Global Trim:** Kapasite aşımında zayıf intent'ler deterministik bloklanır.
3.  **Court Global Gate:** Global blok varsa verdict IMPROVE olur.
4.  **Court Per-Coin Gate:** Coin limiti aşılırsa verdict IMPROVE olur.

**Core Regresyon:**
```bash
7 passed, 342 deselected
```

---

## 4. Örnek Risk Report V2
```json
{
  "version": "pool_risk_report_v2",
  "limits": {
    "global_notional_cap": 2000.0,
    "per_coin_notional_cap": 300.0
  },
  "blocked_reasons_count": {
    "GLOBAL_NOTIONAL_CAP": 1
  },
  "blocked": [
    {
      "intent_id": "weak_intent",
      "reason": "GLOBAL_NOTIONAL_CAP"
    }
  ]
}
```

## 5. Sonuç
Sistem artık risk limitlerini gerçek zamanlı uyguluyor ve Court buna göre karar veriyor. UI üzerinden izlenebilir.
