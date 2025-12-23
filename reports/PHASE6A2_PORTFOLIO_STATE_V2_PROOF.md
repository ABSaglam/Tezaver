# Phase 6A.2: Portfolio State v2 (PnL + Exposure)

**Tarih:** 2025-12-23
**Durum:** ✅ COMPLETED

---

## 1. Özet
Portfolio state güncellendi: avg_entry, qty, realized/unrealized PnL, fees, slippage tracking.

---

## 2. Değişiklikler

### Yeni Modüller
*   **`portfolio_models_v2.py`:** PortfolioPositionV2, PortfolioStateV2, compute_totals

### State Store
*   **[MODIFY] `portfolio_state_store_sim_v1.py`:** load_state_v2, save_state_v2, migration, position update funcs

### Provider
*   **[MODIFY] `portfolio_provider_v2.py`:** Uses load_state_v2

---

## 3. Position Schema v2

| Field | Type | Açıklama |
|-------|------|----------|
| avg_entry | float | Girişentryfiyfiat |
| qty | float | Miktar |
| notional_entry | float | Giriş notional |
| fees_paid | float | Ödenen komisyon |
| slippage_paid | float | Ödenen slippage |
| realized_pnl | float | Kapatma sonrası PnL |
| unrealized_pnl | float | Açık pozisyon PnL |

---

## 4. Doğrulama

### Testler
**test_portfolio_state_v2.py:** (4 test)
- open_creates_position ✅
- close_realizes_pnl ✅
- migration_v1_to_v2 ✅
- load_state_v2_priority ✅

**test_portfolio_provider_v2_pnl.py:** (2 test)
- provider_reads_open_now ✅
- provider_includes_totals ✅

```bash
tests/matrix/pool/test_portfolio_state_v2.py .... [66%]
tests/matrix/pool/test_portfolio_provider_v2_pnl.py .. [100%]
6 passed in 0.07s
```

**Core Regression:**
```bash
7 passed, 329 deselected
```

---

## 5. Sonuç
Portfolio State artık tam PnL hesaplıyor.
