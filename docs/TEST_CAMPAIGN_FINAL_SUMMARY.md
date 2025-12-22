# TEST CAMPAIGN FINAL SUMMARY — Pilot-2 Stabilization

**Tarih:** 2025-12-22  
**Branch:** matrix_rebuild_v4  
**HEAD:** b9bcd79e821c58e0a642ccd24289c6e344c41dc8

## Gate Komutları (Kilit)
- Core Gate: `pytest -q tests/matrix -m core`
- Golden E2E: `pytest -q tests/matrix/test_golden_e2e.py -k golden_e2e_core`

## Son Durum
- Core: ✅ 7/7 PASS
- Golden E2E: ✅ PASS
- Repo: ✅ clean

## Kilitlenen Kontratlar
### 1) Artifacts / Judge / Report Path
- report.json yazılmadan önce parent dir otomatik oluşturulur (PATH_MISSING kapandı).
- Judge kontratı run-scoped reports bekler.

### 2) Telemetry Contract
- `event_type` anahtarı ana sözleşme.
- Backward-compat: `kind == event_type` (WAR timeline dahil).
- Validator: `validate_event_dict(event) -> bool`

### 3) Registry Contract
- Registry key = `bundle_id`
- Import sonrası `registry.get(bundle_id)` None dönmez.
- FAILED_IMPORT kayıtları registry'de tutulur.

### 4) LIVE State + Runner Contract
- State path: `runs/<run_id>/live_state.json`
- `last_bar_ts` bar processing ile güncellenir.
- GAP_DETECTED/RECONNECT event'leri emit edilir.
- Cursor her step'te persist edilir.

### 5) Cloud Runtime Contract
- paused/kill-switch modunda config'ler initialize edilir.
- `events_written` dönüşü her zaman return dict'te bulunur.
- CLOUD_TICK event payload'da strategy_id bulunur.

### 6) WAR Timeline Contract
- WAR_START/WAR_END event'leri emit edilir ve timeline okuyucuları ile uyumludur (`kind`).

### 7) Jury / Scorecard Contract
- BAR event'leri bars_count'a sayılır.
- DECISION/BLOCK event'leri ilgili sayaçlara eklenir.
- decisions_count, incidents_count return edilir.

### 8) Order Lifecycle Safety Contract
- Terminal state'ten invalid transition => `ValueError("INVALID_TRANSITION:...")`

### 9) Release Gate + Migration Allowlist Contract
- activate=True => status ACTIVE
- release gate evaluation: safety registry + proof runs (sniper/war/live) ile doğrulanır.

### 10) Golden E2E Contract
- Sniper check: "DONE şartı" yerine "error var mı?" üzerinden değerlendirilir.
- Live run meta.json oluşturulur (required fields).
- Promote validation: `candidates_stage/{cid}.json` mevcut olmalıdır.

## MX Paketleri (Kısa Kronoloji)
| MX ID | Özet |
|-------|------|
| MX-9300 | Judge/report dir auto-create (PATH_MISSING düşürüldü) |
| MX-9301 | test_judge_pass fixture kontrat uyumu |
| MX-9310 | Registry get key (bundle_id) düzeltmeleri |
| MX-9320 | Live runner/orchestrator compat shims (API imza uyumu) |
| MX-9321/9322 | run_id + cursor persist kontratı |
| MX-9323 | bar processing + last_bar_ts + gap detection + state path fix |
| MX-9330 | Cloud runtime paused/tick contract fix |
| MX-9340 | Telemetry backward-compat `kind` (WAR timeline) |
| MX-9350 | Migration allowlist ACTIVE + release gate proof chain fix |
| MX-9360 | Jury scorecard event sayımı |
| MX-9370 | Invalid transition MUST raise |
| MX-9380 | Golden E2E contract fixes (sniper/meta/promote) |

## Notlar / Gelecek
- Yeni işler eklendikçe Core Gate kırılmamalı.
- Integration smoke suite (subprocess CLI) ayrı marker ile opsiyonel eklenebilir.
