# Phase 6A.1: Fee + Slippage Model v1 (SIM Quality)

**Tarih:** 2025-12-23
**Durum:** ✅ COMPLETED

---

## 1. Özet
SIM Execution'a gerçekçi fee + slippage uygulandı. Her fill için maliyet hesaplanıyor.

---

## 2. Değişiklikler

### Yeni Modüller
*   **`sim_fill_model_v1.py`:** SimFillResultV1, simulate_fill, apply_bps

### Executor Hook
*   **[MODIFY] `pool_executor_sim_v0.py`:** Fill simulation + fill report

### UI
*   **[MODIFY] `matrix_v4_tab.py`:** "💰 SIM Fills (Fee+Slip)" expander

### Yeni Rapor
*   `pool_sim_fill_report_v1.json`: fills + totals

---

## 3. Model

| Param | Default | Açıklama |
|-------|---------|----------|
| fee_bps | 4.0 | 0.04% komisyon |
| slippage_bps | 8.0 | 0.08% kayma |

**apply_bps:**
- OPEN: `price * (1 + bps/10000)` (kötü yön)
- CLOSE: `price * (1 - bps/10000)` (kötü yön)

---

## 4. Doğrulama

### Testler
**test_sim_fill_model_v1.py:** (6 test)
- apply_bps open/close ✅
- compute_fee ✅
- slippage_cost ✅
- simulate_fill open/close ✅

**test_pool_execution_sim_fills_v1.py:** (2 test)
- executor writes fill report ✅
- policy overrides defaults ✅

```bash
tests/matrix/pool_exec/test_sim_fill_model_v1.py ...... [75%]
tests/matrix/pool_exec/test_pool_execution_sim_fills_v1.py .. [100%]
8 passed in 0.06s
```

**Core Regression:**
```bash
7 passed, 323 deselected
```

---

## 5. Örnek Fill Report
```json
{
  "fills_total": 2,
  "fills": [
    {"symbol": "BTC", "ref_price": 100.0, "eff_price": 100.08, "fee_cost": 0.04, "slippage_cost": 0.08}
  ],
  "totals": {"fee_cost": 0.08, "slippage_cost": 0.16}
}
```

## 6. Sonuç
SIM Execution artık gerçekçi maliyet hesaplıyor.
