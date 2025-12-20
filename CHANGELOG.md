# Changelog

Tüm önemli değişiklikler bu dosyada belgelenir.
Format: [Keep a Changelog](https://keepachangelog.com/tr/1.0.0/)

## [0.1.0] - 2024-12-20

### Eklenenler (Added)
- **Platform v1**: Mac/Matrix/Cloud agent mimarisi
- **Real Pipeline**: Gerçek 7 adımlı golden flow (Build → Sniper → War → Live → Approve → Deploy → Tick)
- **Wizards**: One-click golden, Sniper, Deploy sihirbazları
- **S3 Bus**: S3/MinIO destekli merkezi bus (event shards + tail_events)
- **Ops Dashboard**: Tek ekran kontrol merkezi (health cards, unified timeline, SLO metrics)
- **Production Hardening**: Token safety, request timeouts, version gate
- **Backup CLI**: tezaver-bus-backup (FS zip / S3 manifest)
- **Release Gate**: MATRIX_RELEASE_CHECK ve MATRIX_REHEARSAL_CHECK job'ları
- **Version Module**: tezaver.version ile sürüm ve commit bilgisi

### Değiştirilenler (Changed)
- Agent health response'a api_version ve platform_version eklendi
- Connectors sayfasında token maskeleme ve detaylı test bağlantısı

### Düzeltilenler (Fixed)
- Job idempotency için outbox kontrolü
- Event tail sıralaması (newest first)

---

## [Unreleased]
- Sniper Arena v5
- Cloud Binance Futures entegrasyonu
- Multi-coin parallel execution
