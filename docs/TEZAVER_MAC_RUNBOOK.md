# Tezaver Mac Runbook

Tezaver Mac, kripto varlıklar için çok katmanlı bir analiz laboratuvarıdır. Veri toplama, özellik çıkarma, snapshot alma, etiketleme ve bilgelik üretme aşamalarından oluşan bir pipeline'a sahiptir. Sonuçlar, Tezaver Bulut'a aktarılmak üzere hazırlanır ve yerel bir panel üzerinden izlenir.

## Ortam Kurulumu

Gerekli bağımlılıkları yüklemek için:

```bash
# Virtual environment (varsa) aktif edilir
source venv/bin/activate

# Bağımlılıklar yüklenir
pip install -r requirements.txt
```

## Tam Pipeline (Adım Adım)

Sistemi sıfırdan veya güncel verilerle çalıştırmak için aşağıdaki adımları sırasıyla izleyin.

### 1. Veri & Tarihçe (M2)
Borsa verilerini günceller ve eksikleri tamamlar.

```bash
python src/tezaver/data/run_history_update.py
```

### 2. Özellikler / İndikatörler (M3)
Ham veriden teknik indikatörleri (RSI, MACD, ATR vb.) hesaplar.

```bash
python src/tezaver/features/run_feature_build.py
```

### 3. Snapshotlar (M4)
Her mum çubuğu için o anki piyasa durumunu (snapshot) oluşturur.

```bash
python src/tezaver/snapshots/run_snapshot_build.py
```

### 4. Sonuç & Rally Etiketleme (M5)
Geleceğe bakarak her snapshot'ın sonucunu (kâr/zarar) ve rally durumunu etiketler.

```bash
python src/tezaver/outcomes/run_rally_labeler.py
```

### 5. Çoklu Timeframe Snapshotlar (M8)
Farklı zaman dilimlerini (1h, 4h, 1d) birleştirerek zenginleştirilmiş snapshotlar oluşturur.

```bash
python src/tezaver/snapshots/run_multi_tf_snapshot_build.py
```

### 6. Bilgelik (Pattern & Volatilite) (M6)
Pattern istatistiklerini ve volatilite imzalarını çıkarır.

```bash
python src/tezaver/wisdom/run_pattern_stats.py
```

### 7. Rejim & Şok Beyinleri (M15)
Piyasa rejimini (trending, chaotic vb.) ve şok riskini analiz eder.

```bash
python src/tezaver/brains/run_regime_shock_build.py
```

### 8. Rally Aileleri (M14)
Benzer rally'leri kümeleyerek "rally aileleri" oluşturur.

```bash
python src/tezaver/rally/run_rally_families.py
```

### 9. Seviyeler (M11-M12)
Destek ve direnç seviyelerini belirler.

```bash
python src/tezaver/levels/run_trend_levels_build.py
```

### 10. Bulut Export (M16)
Tüm analizleri Tezaver Bulut formatında tek bir JSON dosyasında birleştirir.

```bash
python src/tezaver/export/run_bulut_export.py
```

### 11. Global Bilgelik (M18)
Tüm coinlerden elde edilen pattern istatistiklerini birleştirerek genel piyasa bilgeliği üretir.

```bash
python src/tezaver/wisdom/run_global_wisdom.py
```

### 12. Beyin Senkronizasyonu (M7)
Tüm analiz sonuçlarını ana `CoinState` veritabanına işler.

```bash
python src/tezaver/core/run_brain_sync.py
```

### 13. Fast15 Rally Scanner (M23) - Opsiyonel
15 dakikalık timeframe'de hızlı yükselişleri (5%+/10%+/20%+/30+%) tespit eder ve multi-TF indikatör fotoğraflarıyla kaydeder.

**Tek coin için:**
```bash
python src/tezaver/rally/run_fast15_rally_scan.py --symbol BTCUSDT
```

**Tüm coinler için:**
```bash
python src/tezaver/rally/run_fast15_rally_scan.py --all-symbols
```

**Çıktılar:**
- `library/fast15_rallies/{SYMBOL}/fast15_rallies.parquet`: Olay logu (event log)
- `data/coin_profiles/{SYMBOL}/fast15_rallies_summary.json`: Bucket istatistikleri + Türkçe özet

**Not:** Bu lab aracıdır, gerçek zamanlı trading sinyali değildir.

### 14. Kullanıcı Arayüzü (UI)
Analiz panelini başlatır.

```bash
streamlit run src/tezaver/ui/main_panel.py
```

---

## Backup & Restore (Yedekleme ve Geri Yükleme)

Veri güvenliği için M13 modülü kullanılır.

### Yedekleme (Backup)

**Günlük Mini Yedek (Sadece mantıksal durum):**
```bash
python src/tezaver/backup/run_backup.py
```

**Haftalık Tam Yedek (Tüm veriler):**
```bash
python src/tezaver/backup/run_backup.py full
```

### Geri Yükleme (Restore)

**Önizleme (Dry-Run):**
Yedek dosyasını bozmadan ne yapılacağını gösterir.
```bash
python src/tezaver/backup/run_restore_backup.py
```

**Uygulama (Apply):**
Yedeği gerçekten geri yükler (Mevcut verilerin üzerine yazar!).
```bash
python src/tezaver/backup/run_restore_backup.py apply
```

---

> **Not:** Tezaver Mac felsefesi ve prensipleri için `docs/philosophy_stub.md` dosyasına bakabilirsiniz.
