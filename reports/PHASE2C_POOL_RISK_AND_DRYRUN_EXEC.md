# Phase 2C: Risk Report v1 + Execution Summary v1 (DRY-RUN, NON-TRADING)

**Tarih:** 2025-12-23
**Durum:** ✅ COMPLETED

---

## 1. Özet
Phase 2B'nin seçtiği intents üzerinden **Risk Değerlendirmesi** ve **Dry-Run Yürütme Planı** oluşturuldu. **Bu fazda gerçek emir gönderilmez (NO ORDER SEND).**

*   **Risk Engine:** Missing policy, Kill Switch, Global Notional Limit kontrolü.
*   **Execution Plan:** Allowed intents için `PLACE_ORDER` (dry-run), blocked için `SKIP_BLOCKED`.
*   **Determinism:** Tüm raporlarda `engine_version`, `data_fingerprint`, `config_signature` zorunlu.

---

## 2. Değişiklikler

### Yeni Modüller
*   **`pool_risk_engine_v1.py`:** Stop extraction, notional calculation, risk verdict logic.

### Model Güncellemeleri
*   **[MODIFY] `pool_models_v1.py`:** `PoolRiskItemV1`, `PoolRiskReportV1`, `PoolExecutionPlanItemV1`, `PoolExecutionSummaryV1` eklendi.

### Engine Entegrasyonu
*   **[MODIFY] `pool_engine_v1.py`:** `run_pool_phase2c` fonksiyonu eklendi.

### UI
*   **[MODIFY] `matrix_v4_tab.py`:** **"🌊 Pool Reports (Phase 2C)"** bölümü (Risk + Execution Summary) eklendi.

---

## 3. Kill Switch / Risk Limiter Entegrasyonu

Şu an projede aktif Kill Switch veya Global Risk Limiter modülü bulunmamaktadır. Engine bu sinyalleri parametre olarak alır:
- `kill_switch_triggered=True` → Tüm intents **BLOCK** ("KILL_SWITCH")
- `risk_limiter_triggered=True` → Tüm intents **BLOCK** ("GLOBAL_RISK_LIMIT")

Gerçek sistem entegrasyonu ilerideki fazlarda yapılacaktır (stub/param olarak çalışır).

---

## 4. Doğrulama (Verification)

### Otomatik Testler
`tests/matrix/pool/test_pool_phase2c_risk_execution.py`:

1. **test_missing_policy_blocks:** Policy'si olmayan bundle -> BLOCK (MISSING_POLICY) ✅
2. **test_kill_switch_blocks_all:** Kill switch aktifken tüm intents'ler engelleniyor ✅
3. **test_global_notional_limit_trims:** Notional limit aşımında en düşük puanlılar engelleniyor (deterministic) ✅
4. **test_execution_summary_dry_run:** DRY_RUN modunda plan doğru üretiliyor ✅

**Test Çıktısı:**
```bash
tests/matrix/pool/test_pool_phase2c_risk_execution.py .... [100%]
4 passed in 0.06s
```

**Core Regression:**
```bash
7 passed, 274 deselected
```

---

## 5. Örnek Rapor Çıktısı

**pool_risk_report_v1.json**:
```json
{
  "allowed_count": 2,
  "blocked_count": 1,
  "blocked_reasons_count": {"GLOBAL_NOTIONAL_LIMIT": 1},
  "kill_switch": {"triggered": false}
}
```

**pool_execution_summary_v1.json**:
```json
{
  "mode": "DRY_RUN",
  "planned_orders": 2,
  "plan": [
    {"action": "PLACE_ORDER", "notes": ["dry_run"]},
    ...
  ]
}
```

## 6. Sonuç
Pool motoru artık emir göndermeden önce hangi işlemlerin onaylanacağını ve reddedileceğini biliyor. Bir sonraki fazda gerçek veya simülasyon emir gönderimi yapılabilir.
