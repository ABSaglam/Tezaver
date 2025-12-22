# Legacy Test Backlog — MX-9201

> **Tarih:** 2025-12-22  
> **Core Gate:** ✅ 7/7 PASS  
> **Legacy Fail:** 20 test  
> **Toplam:** 220 test (7 core + 193 passed legacy + 20 failed legacy)

---

## Kategori: Migration

| Test | Dosya | Sebep |
|------|-------|-------|
| `test_migration_allowlist_activate` | `test_migration_allowlist_activate.py` | API değişikliği: status artık PAUSED dönüyor, ACTIVE bekleniyordu |

---

## Kategori: Orchestrator

| Test | Dosya | Sebep |
|------|-------|-------|
| `test_orchestrator_live_plus_sniper` | `test_orchestrator_live_plus_sniper.py` | API imza değişikliği: `save_live_state()` argüman sayısı uyumsuz |
| `test_cloud_runtime_tick` | `test_cloud_runtime_tick.py` | KeyError: Cloud runtime state yapısı değişti |
| `test_cloud_kill_switch_pauses_runtime` | `test_cloud_kill_switch_pauses_runtime.py` | State dosya yapısı değişikliği |

---

## Kategori: Flow/Sprint

| Test | Dosya | Sebep |
|------|-------|-------|
| `test_sprint3_full_flow` | `test_sprint3_flow.py` | Registry'de candidate bulunamıyor (ValueError: Candidate not found) |
| `test_golden_e2e_core` | `test_golden_e2e.py` | Judge output path oluşturulmuyor (FileNotFoundError) |

---

## Kategori: War Full Pipeline

| Test | Dosya | Sebep |
|------|-------|-------|
| `test_war_full_pipeline_non_empty` | `test_war_full_pipeline.py` | Timeline event yapısı değişti (WAR_START event yok) |

---

## Kategori: CLI Integration

| Test | Dosya | Sebep |
|------|-------|-------|
| `test_live_runner_resume_and_gap` | `test_live_runner_resume_and_gap.py` | `start_live_run()` argüman uyumsuzluğu: `symbol` parametresi artık yok |

---

## Kategori: Cycle Engine / Judge (Path Mismatch)

| Test | Dosya | Sebep |
|------|-------|-------|
| `test_cycle_writes_artifacts` | `test_cycle_engine_writes_judge.py` | Judge output dizini oluşturulmuyor |
| `test_cycle_with_ports` | `test_cycle_with_ports.py` | Judge output dizini oluşturulmuyor |
| `test_cycle_determinism` | `test_cycle_determinism.py` | Judge output dizini oluşturulmuyor |
| `test_cycle_saves_profile` | `test_cycle_engine_profile.py` | Judge output dizini oluşturulmuyor |
| `test_judge_pass` | `test_judge.py` | Report.json yazılamıyor (parent dir yok) |
| `test_judge_fail_blocks` | `test_judge.py` | Report.json yazılamıyor (parent dir yok) |

---

## Kategori: Registry / Candidate Handling

| Test | Dosya | Sebep |
|------|-------|-------|
| `test_importer_and_registry_flow` | `test_importer_integration.py` | Registry.get() None dönüyor (candidate kaydedilmiyor) |
| `test_legacy_bundle_no_crash` | `test_legacy_bundle_handling.py` | FAILED_IMPORT kaydı None dönüyor |
| `test_registry_upsert` | `test_canonical_manifest.py` | TypeError: Registry API imza değişikliği |
| `test_cycle_block_incident` | `test_block_creates_incident.py` | Cycle engine incident path uyumsuz |

---

## Kategori: Other

| Test | Dosya | Sebep |
|------|-------|-------|
| `test_jury_scorecard_counts` | `test_jury_scorecard.py` | bars_count beklenenden farklı (0 vs 3) |
| `test_invalid_transition` | `test_order_lifecycle.py` | ValueError raise edilmiyor (state machine değişikliği) |

---

## Özet: Root Cause Grupları

| Root Cause | Test Sayısı |
|------------|-------------|
| `PATH_MISSING` (Judge/Report output dir) | 6 |
| `API_SIGNATURE_MISMATCH` | 5 |
| `REGISTRY_NULL_RETURN` | 3 |
| `STATE_STRUCTURE_CHANGE` | 3 |
| `ASSERTION_MISMATCH` | 2 |
| `FIXTURE_MISMATCH` | 1 |

---

## Aksiyon Planı

1. **Öncelik 1 (PATH_MISSING):** `judge.py`'de report yazılmadan önce parent dizin oluşturulmalı
2. **Öncelik 2 (API_SIGNATURE_MISMATCH):** Test dosyaları yeni API imzalarına göre güncellenmeli
3. **Öncelik 3 (REGISTRY_NULL_RETURN):** Registry upsert/get mantığı doğrulanmalı
