# Phase 0.2: Pool Evidence Contract - Drift Checker & UI Integration (NON-BREAKING)

**Tarih:** 2025-12-23
**Durum:** ✅ COMPLETED

---

## 1. Özet
**Pool Evidence Contract (v1)**, Matrix'in Safety/Evidence sistemine "Non-Breaking" (mevcut yapıyı bozmayan) bir şekilde entegre edildi. 
Artık sistem, bir koşuda **Pool Modu** aktif ise (`pool_enabled=True`), kontratta belirtilen 9 adet artefaktın varlığını ve içerik bütünlüğünü otomatik olarak denetler.

Eğer Pool Modu aktif değilse (mevcut Snipe/War koşuları gibi), bu kontrol **SKIPPED** durumuna geçer ve sistemin onay mekanizmasını (Seal) etkilemez.

---

## 2. Değişiklikler

### 🛡️ Safety Registry & Sweep
- **[NEW] `pool_evidence_contract_v1.json`:** WAR/LIVE aşamaları için gerekli kanıt dosyalarının listesi (Universe, Ticks, Portfolio, Risk vb.).
- **[MOD] `safety_registry.py`:** `check_pool_evidence_contract` metodu eklendi.
  - Kontrat dosyasını okur.
  - Aşamaya (WAR/LIVE) göre filtreleme yapar.
  - Dosya varlığını ve JSON field bütünlüğünü doğrular.
- **[MOD] `safety_sweep.py`:** Sweep işlemine "Pool Evidence" adımı eklendi.
  - `pool_enabled` sinyali (Config veya Rapor varlığı) kontrol edilir.
  - Eksik varsa Warning üretir (şimdilik Red Blocker değil).

### 🖥️ UI (Matrix V4)
- **[MOD] `matrix_v4_tab.py`:** Release Gate ve Safety Certificate görünümüne "Pool Evidence" satırı eklendi.
  - ✅ **OK**
  - ⏭️ **SKIPPED** (Pool kapalıysa)
  - ⚠️ **MISSING** (Eksik dosya varsa, detaylı liste ile)

### 📄 Raporlama (Certificate)
- **[MOD] `safety_certificate.py`:** Markdown ve JSON sertifikalara Pool Evidence bölümü eklendi.

---

## 3. Doğrulama (Verification)

### Otomatik Testler
Yeni eklenen `test_pool_evidence_contract.py` ile aşağıdaki senaryolar doğrulandı:

1.  **Pool Disabled -> SKIPPED:**
    - `pool_enabled=False` olduğunda sistem SKIPPED döner.
2.  **Pool Enabled + Missing Files -> MISSING:**
    - Dosyalar yoksa MISSING statüsü ve eksik dosya listesi döner.
3.  **Missing Fields -> MISSING:**
    - Dosya var ama içi boşsa veya field eksikse hata yakalanır.
4.  **Stage Filter:**
    - WAR koşusunda LIVE artefaktları (örn. `live_arm_state`) aranmaz.

**Test Çıktısı:**
```bash
tests/matrix/protocols/test_pool_evidence_contract.py .... [100%]
4 passed in 0.09s
```

**Regresyon Testi (Core Gate):**
Mevcut core testler kırılmadan çalışmaya devam ediyor.
```bash
tests/matrix/test_live_v1.py . 
...
tests/matrix/test_telemetry_schema.py . 
7 passed, 257 deselected
```

---

## 4. Güvenlik Notu (Non-Breaking Guarantee)
Bu entegrasyon **Sealed** (Mühürlü) olan Safety yapısını bozmaz çünkü:
*   Mevcut protokollerin (`MX-5100` vb.) içi değiştirilmedi.
*   Pool kontrolü ayrı bir katman (Auxiliary Check) olarak eklendi.
*   `pool_enabled` varsayılan olarak `False` kabul edildiği için, eski tip koşular (Legacy WAR/SNIPER) "SKIPPED" alarak yeşil kalmaya devam eder.

---

## 5. Sonraki Adımlar
Bu altyapı hazır olduğuna göre, artık **Pool Motorunun** (`pool_engine`) bu kontratta belirtilen 9 adet raporu üretmesi gerekmektedir.
