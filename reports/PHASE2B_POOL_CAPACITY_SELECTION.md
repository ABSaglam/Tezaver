# Phase 2B: Portfolio Snapshot + Capacity Gate + Deterministic Selection + 2 Reports

**Tarih:** 2025-12-23
**Durum:** ✅ COMPLETED

---

## 1. Özet
Phase 2A'nın ürettiği niyetler, **Portfolio Provider** (Cüzdan Sağlayıcı) ve **Selector** (Seçici) katmanlarından geçirilerek nihai alım adayları belirlendi.

*   **Toplam 20 Kuralı (Capacity Rule):** Sistem `max(0, MAX_OPEN - open_now)` formülüyle boş kapasiteyi hesaplar.
*   **Deterministik Seçim (Top-K):** Kapasite kadar intent, **Puan (QC + Tier)** ve **Intent ID** (eşitlik bozmada) önceliğine göre sıralanarak seçilir.
*   **Replacement Yok:** Şimdilik sadece boş koltuk varsa yeni işlem açılır (FIFO benzeri).
*   **Raporlar:**
    1.  `pool_portfolio_snapshot_v1.json`: O anki açık pozisyonlar ve kapasite.
    2.  `pool_selection_report_v1.json`: Seçilen ve elenen niyetlerin detaylı dökümü.

---

## 2. Değişiklikler

### Yeni Modüller
*   `src/tezaver/matrix/pool/portfolio_provider_v1.py`: Cüzdan durumunu sorgulayan arayüz. Şimdilik `Stub` (boş/sabit) veya `Matrix fallback` (boş) dönüyor.
*   `src/tezaver/matrix/pool/pool_selector_v1.py`: Puanlama ve Top-K seçim algoritması.
    *   **Score Formülü:** `QC_SCORE + TIER_BONUS` (Diamond: +30, Gold: +20, ...)
*   **[MODIFY] `pool_engine_v1.py`:** `run_pool_phase2b` fonksiyonu eklendi.

### UI (Matrix V4)
*   **[MODIFY] `matrix_v4_tab.py`:** **"🌊 Pool Reports (Phase 2B)"** bölümü eklendi. Seçili run için Snapshot ve Selection raporlarını gösterir.

---

## 3. Doğrulama (Verification)

### Otomatik Testler
Yeni oluşturulan `tests/matrix/pool/test_pool_phase2b_selection.py` ile kritik kurallar doğrulandı:

1.  **test_capacity_calc:** 20 limit varken 5 pozisyon varsa kapasitenin 15 olduğu, 20 varken 0 olduğu doğrulandı.
2.  **test_deterministic_ranking:** Farklı QC ve Tier'a sahip niyetlerin doğru puanlanıp (Score DESC) sıralandığı doğrulandı.
3.  **test_tie_breaking:** Eşit puanda `intent_id`'si küçük olanın (alfabetik/hex) seçildiği, sonucun her zaman aynı olduğu (deterministik) doğrulandı.
4.  **test_skipped_aggregation:** Kapasite dışı kalanların `SKIPPED_OVERFLOW` olarak raporlandığı doğrulandı.

**Test Çıktısı (Yeni Testler):**
```bash
tests/matrix/pool/test_pool_phase2b_selection.py .... [100%]
4 passed in 0.05s
```

**Regresyon Testi:**
```bash
tests/matrix/test_live_v1.py . 
...
tests/matrix/test_telemetry_schema.py . 
7 passed, 270 deselected
```

---

## 4. Örnek Rapor Çıktıları (JSON Snippet)

**pool_selection_report_v1.json**:
```json
{
    "run_id": "run_rank",
    "capacity": 2,
    "intents_eligible": 3,
    "selected_count": 2,
    "selected": [
        {
            "intent_id": "A",
            "rank_score": 120.0,
            "rank_reason": "qc+tier"
        },
        {
            "intent_id": "C",
            "rank_score": 100.0,
            "rank_reason": "qc+tier"
        }
    ],
    "skipped": [
         { "intent_id": "B", "reason": "SKIPPED_OVERFLOW" }
    ]
}
```

## 5. Sonuç
Pool motoru artık "ne kadar" işlem alacağını ve "hangilerini" seçeceğini biliyor. Sıradaki fazda bu seçilen niyetleri **Order Executor** ile borsaya (veya simülasyona) iletmek kalıyor.
