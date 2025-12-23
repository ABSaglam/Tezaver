# Phase 5A: Portfolio Provider v2 (REAL/SIM Bridge)

**Tarih:** 2025-12-23
**Durum:** ✅ COMPLETED

---

## 1. Özet
Pool capacity artık SIM state'ten okunuyor. SIM Execution intents'lerinden pozisyon state'i türetiliyor.

---

## 2. Değişiklikler

### Yeni Modüller
*   **`portfolio_state_store_sim_v1.py`:** OPEN/CLOSE intent → position state
*   **`portfolio_provider_v2.py`:** SIM_STATE / EMPTY modları

### UI
*   **[MODIFY] `matrix_v4_tab.py`:** **"🌊 Portfolio Snapshot v2"** paneli

---

## 3. Provider Modları

| Mode | Kaynak | open_now |
|------|--------|----------|
| EMPTY | Stub (backward compat) | 0 |
| SIM_STATE | pool_portfolio_state_sim_v1.json | len(positions) |

**capacity = max(0, max_open_positions - open_now)**

---

## 4. Doğrulama

### Testler
`tests/matrix/pool/test_pool_phase5a_portfolio_provider.py`:

1. **test_empty_snapshot:** EMPTY → open_now=0, capacity=20 ✅
2. **test_sim_state_with_positions:** 5 pozisyon → capacity=15 ✅
3. **test_deterministic_pos_id:** Aynı order_key → aynı pos_id ✅
4. **test_close_removes_position:** CLOSE → pozisyon çıkarılır ✅
5. **test_capacity_respects_max:** 18 pozisyon → capacity=2 ✅

**Test Çıktısı:**
```bash
tests/matrix/pool/test_pool_phase5a_portfolio_provider.py ..... [100%]
5 passed in 0.05s
```

**Core Regression:**
```bash
7 passed, 304 deselected
```

---

## 5. Sonuç
Pool artık gerçek SIM state'ten capacity okuyor. Testnet/mainnet adaptörleri için altyapı hazır.
