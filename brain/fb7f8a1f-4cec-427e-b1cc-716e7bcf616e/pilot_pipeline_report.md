# Pilot Strategy Pipeline Report (Mac → Matrix)

Bu rapor, Mac ortamında üretilen strateji adaylarının Matrix ekosistemine entegrasyonu ve ilk "Pilot" Sniper koşusunun sonuçlarını dokümante eder.

## A) MAC ÇIKTISI ENVANTERİ
- **Target Path**: `out/matrix_candidates/BTCUSDT/15m/bundle_v1`
- **Pilot Bundle Detayları**:
    - **ID**: `BTCUSDT_15m_bundle_20251221_074154`
    - **Version**: `1.1.1`
    - **Engine Min Version**: `0.1.0`
    - **Metrics**: 
        - Trigger Resolve Rate: `%80.0`
        - Join Coverage: `%60.0`
- **Seçim Nedeni**: %80 başarılı tetikleyici çözünürlüğü ve güncel build zaman damgası nedeniyle en güvenilir aday olarak seçilmiştir.

## B) MATRIX IMPORT DOĞRULAMA
- **Import Sonucu**: 1 bundle bulundu ve başarıyla import edildi.
- **CandidateRegistry Durumu**: `BTCUSDT_15m_1.1.1_2025_12_21T07_41_54_363377` adıyla kaydedildi.
- **İlk Statü**: `NEW` (Import anındaki ham durum).
- **UI Görünürlüğü**: Evet (Registry'ye `data/matrix/candidates_registry.jsonl` üzerinden işlendi).

## C) SNIPER PILOT RUN (Backtest)
- **Run ID**: `run_sniper_BTCUSDT__1766320238`
- **Bars Count**: `500`
- **Trades Count**: `1`
- **Net PnL**: `0.00`
- **Verdict**: `IMPROVE` (Strateji karlılık hedefini tam karşılamadı, revizyon gerekiyor).

### Artifacts Path
- `runs/run_sniper_BTCUSDT__1766320238/report.json`
- `runs/run_sniper_BTCUSDT__1766320238/scorecard.json`
- `runs/run_sniper_BTCUSDT__1766320238/telemetry.ndjson`

### Telemetry Kanıtı (Son 5 Event)
```json
{"ts": 1765368000000, "event_type": "CYCLE_STEP", "payload": {"decision": "HOLD"}}
{"ts": 1765368900000, "event_type": "CYCLE_STEP", "payload": {"decision": "HOLD"}}
{"ts": 1766320247351, "event_type": "RUN_END", "payload": {"end_ts": 1766320247}}
{"ts": "2025-12-21T15:30:48.228889", "event_type": "CANDIDATE_STATUS_UPDATED", "payload": {"old_status": "NEEDS_PATCH", "new_status": "NEEDS_PATCH", "verdict": "IMPROVE"}}
```

## D) LIFECYCLE KANITI
- **Status Geçişi**: `NEW` → `NEEDS_PATCH`
- **Kanıt**: `data/matrix/candidates_registry.jsonl` dosyasında adayın `status` alanı `IMPROVE` kararına istinaden otomatik olarak `NEEDS_PATCH` olarak güncellenmiştir.
- **Audit**: Matrix UI aday detay ekranında "Last Verdict: IMPROVE" olarak yansımıştır.

## E) SONRAKİ ADIM KARARI
- **Karar**: `NEEDS_PATCH` / **WAR/LIVE Koşusu Engellendi**.
- **Sebep**: Sniper testi "PASS" (Geçer) notu alamadığı için strateji WAR (War Game) veya LIVE (Canlı) safhalarına geçirilmemiş, geliştirme döngüsüne geri iade edilmiştir.

---
**Determinizm Notları**: 
- **Seed**: `42`
- **Data Fingerprint**: Parquet bazlı (`7566d4cc...`)
- **Config Signature**: Master v4 spec (`2cddf44a...`)
- **Bar İhlali**: Bulunmadı (Closed-bar only uyumlu).
