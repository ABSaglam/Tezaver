# TEST CAMPAIGN REPORT — v1.0

Bu rapor, Tezaver sisteminin mevcut durumunu, test kapsamını ve "Pilot-2" refaktörü sonrası ortaya çıkan regresyonları/eksikleri belgeler.

## 1) Repo Snapshot
- **Commit**: `c4a4a58...` (Mac/Matrix Integration Phase)
- **Branch**: `master`
- **Entrypoints**:
  - `tezaver-mac-agent`, `tezaver-matrix-agent`
  - `tezaver-smoke`, `tezaver-bus-backup`
- **Status**: Modified (Experimental scripts `pilot_import.py`, `pilot2_import.py` added).

## 2) Test Envanteri
- **Suite Locations**: `tests/matrix`, `tests/platform`, `tests/conformance`
- **Fixtures**: `tests/fixtures`, `out/matrix_candidates/_fixtures`
- **Total Files**: 100+ test dosyası tespit edildi.

## 3) Pytest Sonuçları
- **Komut**: `pytest -q tests/matrix`
- **Sonuç**: **FAIL** (Exit Code: 1)
- **Teşhis**: Matrix CLI refaktörleri sonrası `tests/matrix/test_run_sniper_cli.py` ve `test_run_war_cli.py` dosyaları, yeni stil bundle yapısını (Directory based) ve `ParquetDataPort` ihtiyacını karşılayamadığı için kırılmış durumdadır.

## 4) Smoke Runs

### 4.1 Import/Registry
- **Komut**: `python3 scripts/pilot2_import.py`
- **Sonuç**: **PASS**
- **Artifact**: `data/matrix/candidates_registry.jsonl`
- **Gözlem**: 3 yeni bundle (Limit 5/10/15) başarıyla Matrix havuzuna alındı.

### 4.2 Sniper Smoke
- **Komut**: `tezaver-matrix-agent --candidate-id ...` (veya `run_sniper.py`)
- **Sonuç**: **PASS (ENGINE) / IMPROVE (VERDICT)**
- **Evidence**: `runs/run_sniper_bundle_v_1766323269/report.json`
- **Log**: `{"ts": 20000, "event_type": "RUN_END", "payload": {"verdict": "IMPROVE"}}`

### 4.3 WAR Smoke
- **Komut**: `python3 -m tezaver.matrix.apps.run_war ...`
- **Sonuç**: **FAIL (Triage: RED)**
- **Hata**: `Invalid bundle: ['Missing required field: story']`
- **Teşhis**: WAR motoru hala "Legacy Single-JSON" bundle bekliyor; v1.1.2 Directory yapısını desteklemiyor.

### 4.4 LIVE Smoke
- **Komut**: `python3 -m tezaver.matrix.apps.run_live ...`
- **Sonuç**: **FAIL (Triage: RED)**
- **Hata**: `ImportError: cannot import name 'start_live_run' from 'tezaver.matrix.core.live_engine'`
- **Teşhis**: Entrypoint ve Engine arasındaki API sözleşmesi kopmuş durumda.

## 5) Determinism Check
- **Senaryo**: `bundle_v1_1766331399` (100 bars) x 2 runs.
- **Sonuç**: **PASS**
- **Bulgular**: `report.json` karşılaştırmasında sadece `run_id` ve `timestamp` alanları değişti. Financial (PnL/Trades) ve Logic (Verdict) %100 aynı kaldı.

## 6) Triage Listesi

### 🔴 KIRMIZI (Acil Aksiyon Gerekenler)
- **MX-TEST-001**: Pytest suite'lerinin v1.1.2 bundle yapısına göre güncellenmesi.
- **MX-CLI-001**: `run_war.py` ve `run_live.py` entrypoint'lerinin Directory-bundle yükleyicisine geçirilmesi.
- **MX-ENGINE-001**: `live_engine.py` içindeki `LiveEngine` sınıfının CLI ile (start_live_run) senkronize edilmesi.

### 🟡 SARI (İyileştirme)
- **MX-UI-001**: WAR duman testi sonuçlarının UI'da "Legacy Error" yerine net bir hata mesajıyla gösterilmesi.
- **MX-DATA-001**: `DATA_OK` gate'inin test ortamında bypass edilebilmesi için bir `MOCK_DATA_REPORT` flag'i eklenmesi.

### 🟢 YEŞİL (Başarılı Noktalar)
- **Sniper Core**: Deterministik ve stabil.
- **Import/Registry**: v1.1.2 Directory bundle'ları başarıyla tanıyor ve meta-data mapping yapıyor.

---
**Önerilen MX İşleri**:
1. [MX-9001] "Standardizing WAR CLI for Directory-based Bundles"
2. [MX-9002] "Fixing LIVE Entrypoint Import Error"
3. [MX-9003] "Refactoring Pytest Matrix to use Parquet Mocking"

**Kanıt Paketi**: [brain/fb7f8a1f-4cec-427e-b1cc-716e7bcf616e/](../../brain/fb7f8a1f-4cec-427e-b1cc-716e7bcf616e/) dizinindeki tüm json/ndjson dosyaları.
