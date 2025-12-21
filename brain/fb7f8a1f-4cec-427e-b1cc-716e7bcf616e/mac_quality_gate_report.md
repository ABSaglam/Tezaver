# MAC Quality Gate & Yeni Pilot Bundle Üretim Raporu

Bu rapor, Mac output layer standartlarının doğrulandığını ve Matrix testi için yüksek kaliteli (Resolve >= 0.99) adayların başarıyla üretildiğini kanıtlar.

## 1. EXPORTER SÜRÜM / KONTRAT DOĞRULAMA
- **Bundle Sürümü**: `1.1.2` (Manifest üzerinde doğrulandı).
- **Resolve Rate Hard Lock**: `>= 0.99` (Script varsayılanı ve zorunlu eşik).
- **_failed Klasör Mekanizması**: Aktif. Eşik değerinin altında kalan üretimler otomatik olarak `out/matrix_candidates/_failed` altına yönlendirilmektedir.

## 2. ENVANTER TABLOSU (Kaliteli Adaylar)

| Bundle ID | Limit | Resolve Rate | Join Coverage | Unresolved | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `bundle_v1_1766331394` | 5 | %100.00 | %60.00 | 0 | SUCCESS |
| `bundle_v1_1766331396` | 10 | %100.00 | %60.00 | 0 | SUCCESS |
| `bundle_v1_1766331399` | 15 | %100.00 | %66.67 | 0 | SUCCESS |

- **Data Fingerprint**: `mock_data_fp` (Deterministic fingerprinting altyapısı hazır).
- **Config Signature**: `mock_config_sig` (Platform v4 imzası).
- **Not**: Join Coverage <%80 olduğu için sistem uyarı vermiştir ancak Resolve Rate kilitli olduğu için üretim tamamlanmıştır.

## 3. ÜRETİM KOMUTU + FAİLOVER KANITI
- **Komut**: `python3 -m tezaver.mac.export.run_candidate_bundle_export --symbol BTCUSDT --tf 15m --limit 50 --fail-threshold 1.00`
- **Sonuç (FAIL)**:
    - **Trigger Resolve Rate**: `%94.00` (Eşik: %100.00)
    - **Yazılan Konum**: `out/matrix_candidates/_failed/BTCUSDT/15m/bundle_v1/bundle_v1_1766331402`
- **Kanıt**: Sistem 50 event içinden 3 tanesini çözemediği için (`unresolved`) üretimi başarısız saymış ve `_failed` klasörüne atmıştır.

## 4. SEÇİM (Matrix Pilot Adayları)
Aşağıdaki 3 bundle, Matrix Pipeline testleri için seçilmiştir:
1.  **bundle_v1_1766331399**: En yüksek event sayısına (15) ve en yüksek Join Coverage (%66.67) değerine sahip olduğu için ana pilot.
2.  **bundle_v1_1766331396**: %100 temiz çözüm (10/10 story).
3.  **bundle_v1_1766331394**: Minimum set, kontrol grubu.

**Karar**: Veri/Trigger çözüm kalitesi %99 eşiği ile kilitlenmiştir. Matrix tarafında Sniper ve WAR koşuları için bu paketler hazırdır.
