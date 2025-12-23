# Phase 6A.3: Risk Limiter Binding v1 (Global + Per-Coin Cap)

**Tarih:** 2025-12-23
**Durum:** ✅ COMPLETED

---

## 1. Özet
Global ve Per-Coin notional caps uygulandı. Limit aşıldığında deterministik trimming (en zayıftan başla).

---

## 2. Değişiklikler

### Yeni Modüller
*   **`pool_risk_limiter_v1.py`:** apply_limits, RiskReportV2

### Testler
*   **`test_pool_risk_limiter_v1.py`:** 4 test (global trim, per-coin, determinism, kill switch)
*   **`test_pool_risk_gates_v1.py`:** 3 test (IMPROVE on blocks, PASS, FAIL on KS)

---

## 3. Limiter Mantığı

| Limit | Default | Davranış |
|-------|---------|----------|
| Global Cap | 2000.0 | Aşarsa en zayıfı blokla (rank_score ASC) |
| Per-Coin Cap | 300.0 | Aşarsa yeni intent'i blokla, güçlüler korunur |

**Deterministik Sıralama:**
- Global trim: `rank_score ASC, intent_id ASC`
- Per-coin: `rank_score DESC, intent_id ASC`

---

## 4. Doğrulama

### Testler
```bash
tests/matrix/pool/test_pool_risk_limiter_v1.py ....
tests/matrix/pool_court/test_pool_risk_gates_v1.py ...
7 passed in 0.03s
```

**Core Regression:**
```bash
7 passed, 336 deselected
```

---

## 5. Örnek Risk Report v2 Snippet
```json
{
  "version": "pool_risk_report_v2",
  "limits": {"global_notional_cap": 2000, "per_coin_notional_cap": 300},
  "allowed_count": 5,
  "blocked_count": 2,
  "blocked_reasons_count": {"GLOBAL_NOTIONAL_CAP": 1, "PER_COIN_CAP": 1}
}
```

## 6. Sonuç
Risk Limiter artık portföy metrikleriyle çalışıyor.
