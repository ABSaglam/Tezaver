# Phase 2A: Pool Engine Kernel v1 (Universe + Tick + Intents) + 3 Reports

**Tarih:** 2025-12-23
**Durum:** ✅ COMPLETED

---

## 1. Özet
**Pool Engine** çekirdeği (Kernel v1) başarıyla kuruldu. Bu çekirdek, `ApprovedRallyBundle`'lardan oluşan bir Evreni (`Universe`) yönetir, `BAR_CLOSED` sinyalleriyle (`Tick`) tetiklenir ve deterministik Ticaret Niyetleri (`Intents`) üretir.

Ayrıca kontratta belirtilen ilk 3 kanıt raporu (`run-scoped`) üretilebilir hale geldi:
1.  `pool_universe_report_v1.json`
2.  `pool_tick_report_v1.json`
3.  `pool_intents_report_v1.json`

---

## 2. Değişiklikler

### Yeni Modüller
*   `src/tezaver/matrix/pool/pool_models_v1.py`: Universe, Tick ve Intent modelleri.
*   `src/tezaver/matrix/pool/pool_reports_v1.py`: Rapor yazma yardımcıları.
*   `src/tezaver/matrix/pool/pool_engine_v1.py`:
    *   **Universe Build:** Bundle'ları symbol/TF bazında gruplar, en yüksek QC puanlıyı seçer.
    *   **Tick Logic:** `BAR_CLOSED` eventlerini işler.
    *   **Intent Gen:** Manifest spec'lerine (trigger, policy) bakarak işlem niyeti oluşturur.

### Güncellemeler
*   **[MODIFY] `bundle_registry.py`:** `get(id)` ve `list_loaded_bundles()` metotları eklendi.
*   **[MODIFY] `matrix_v4_tab.py`:** UI'da **"🌊 Pool Reports (Phase 2A)"** bölümü eklendi. İlgili run seçildiğinde bu 3 raporu JSON olarak gösterir.
    *   Konum: `EVIDENCE` -> `Raporlar (Reports)` -> `Pool Reports (Phase 2A)`

---

## 3. Doğrulama (Verification)

### Otomatik Testler
Yeni oluşturulan `tests/matrix/pool/test_pool_phase2a_reports.py` ile motorun davranışı doğrulandı:

1.  **test_universe_build:** Registry'den doğru hücrelerin (cells) ve en iyi bundle'ın seçildiği kanıtlandı.
2.  **test_intents_build:** Trigger/Policy spec'leri olan bundle'lar için Intent üretildiği, olmayanlar için `SKIPPED_NO_SPECS` kaydı düşüldüğü doğrulandı.
3.  **test_run_execution:** Motorun bir tick için çalıştırılıp 3 raporu da doğru path'e (`out/matrix_runs/.../reports/`) yazdığı doğrulandı.

**Test Çıktısı (Yeni Testler):**
```bash
tests/matrix/pool/test_pool_phase2a_reports.py ... [100%]
3 passed in 0.04s
```

**Regresyon Testi (Core Gate):**
```bash
tests/matrix/test_live_v1.py . 
...
tests/matrix/test_telemetry_schema.py . 
7 passed, 266 deselected
```

---

## 4. Örnek Rapor Çıktıları (JSON Snippet)

**pool_intents_report_v1.json**:
```json
{
    "run_id": "run_test_01",
    "stage": "WAR",
    "engine_version": "v1.0.TEST",
    "intents_created": 1,
    "intents_skipped": 0,
    "intents": [
        {
            "intent_id": "a1b2c3d4...",
            "symbol": "SOLUSDT",
            "timeframe": "4h",
            "trigger_type": "Signal",
            "reason": "OK"
        }
    ]
}
```

## 5. Sonraki Adımlar
Motorun Intent üretme yeteneği kazanıldı. Bir sonraki fazda (Phase 2B) bu intentlerin **Selector** (Kapasite/Limit kontrolü) ve **Execution** (Emir gönderimi) aşamaları eklenecek.
