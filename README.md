# Tezaver-Mac 🧬

**Kripto Para Teknik Analiz ve Pattern Recognition Sistemi**

Tezaver-Mac, kripto para piyasalarında teknik analiz, pattern tanıma ve rally tahminleme için geliştirilmiş kapsamlı bir offline analiz sistemidir.

## 🎯 Proje Amacı

Bu sistem, kripto paralardaki yükseliş (rally) hareketlerini analiz eder, pattern'leri öğrenir ve gelecekteki fırsatları değerlendirir. Tüm analiz ve veri işleme offline olarak yapılır, sonuçlar Tezaver Bulut'a export edilir.

## 🏗️ Mimari

Sistem 4 ana modülle organize edilmiştir:

### 1. Data Module (Veri Katmanı)
- **Veri Kaynağı**: Binance CCXT üzerinden
- **Timeframe'ler**: 15m, 1h, 4h, 1d, 1w
- **Coin'ler**: Top 20 kripto para (BTC, ETH, SOL, XRP, vb.)
- **Depolama**: Parquet format (coin_cells/)

### 2. Features Module (Özellik Çıkarımı)
- **İndikatörler**: EMA, Bollinger Bands, MACD, RSI, ATR
- **Multi-timeframe analiz**: Her coin için 5 farklı timeframe
- **Output**: Zenginleştirilmiş OHLCV + indikatör verileri

### 3. Analysis Module (Analiz Katmanı)
- **Snapshot Engine**: Pattern yakalama ve snapshot oluşturma
- **Rally Labeling**: Gelecekteki kazançları etiketleme
- **Pattern Stats**: Güvenilir/ihanetkâr pattern tespiti
- **Rally Families**: Benzer rally'leri kümeleme (KMeans)
- **Regime & Shock**: Piyasa rejimi ve şok analizi

### 4. Panel Module (UI Katmanı)
- **Streamlit UI**: İnteraktif web arayüzü
- **Coin Detail**: Her coin için detaylı analiz sayfası
- **Market Summary**: Tüm coinlerin özet tablosu
- **System Health**: Pipeline durumu ve kontrol merkezi

## 📦 Kurulum

### Gereksinimler
- **Python 3.11** (önerilir), 3.9-3.13 arası desteklenir
- Virtual environment (zorunlu)
- Git

### Adımlar

```bash
# 1. Projeyi klonlayın
git clone <repo-url>
cd TezaverMac

# 2. Virtual environment oluşturun  
python3.11 -m venv venv
source venv/bin/activate  # macOS/Linux
# veya
venv\\Scripts\\activate  # Windows

# 3. Bağımlılıkları yükleyin
pip install --upgrade pip
pip install -r requirements.txt

# 4. Environment variables konfigürasyonu
cp .env.example .env
# .env dosyasını düzenleyip API key'lerinizi ekleyin
nano .env  # veya favori editörünüzle açın

# 5. İlk veri toplama (Pipeline çalıştırma)
make pipeline-full
# Alternatif: PYTHONPATH=src python src/tezaver/run_pipeline.py --mode full
```

## 🚀 Kullanım

### Pipeline Çalıştırma

```bash
# Makefile ile (önerilen)
make pipeline-full  # Full pipeline (tüm adımlar)
make pipeline-fast  # Fast pipeline (brain sync + export)

# Alternatif: Manuel
PYTHONPATH=src python src/tezaver/run_pipeline.py --mode full
PYTHONPATH=src python src/tezaver/run_pipeline.py --mode fast
```

### Streamlit Panel

```bash
# Makefile ile (önerilen)
make ui

# Alternatif: Manuel
PYTHONPATH=src streamlit run src/tezaver/ui/main_panel.py
```

Tarayıcınızda `http://localhost:8501` adresine gidin.

### Testleri Çalıştırma

```bash
# Tüm testleri çalıştır
make test

# Coverage raporu
make coverage
# Rapor: htmlcov/index.html

# Manuel alternatif
PYTHONPATH=src python -m pytest tests -v
```

### Development Komutları

```bash
# Yardım menüsü
make help

# Code formatting
make format

# Linting
make lint

# Lint + Test (commit öncesi)
make check

# Temizlik
make clean
```

## 📊 Pipeline Adımları

Full pipeline şu adımları içerir:

| Adım | Modül | Açıklama |
|------|-------|----------|
| M2 | History Update | Binance'ten son verileri çeker |
| M3 | Feature Build | İndikatörleri hesaplar |
| M4 | Snapshot Build | Pattern snapshot'ları oluşturur |
| M8 | Multi-TF Snapshot | Çoklu timeframe snapshot'ları |
| M5 | Rally Labeling | Yükseliş hareketlerini etiketler |
| M14 | Rally Families | Rally kümeleme (KMeans) |
| M6 | Pattern Wisdom | Güvenilir/ihanetkâr pattern'ler |
| M15 | Regime & Shock | Piyasa rejimi analizi |
| M18 | Global Wisdom | Tüm coinlerden öğrenme |
| M11-M12 | Levels Build | Destek/direnç seviyeleri |
| M7 | Brain Sync | CoinState'leri senkronize eder |
| M16 | Bulut Export | Export JSON'ları hazırlar |
| M13 | Mini Backup | Yedekleme yapar |

## 📁 Dizin Yapısı

```
TezaverMac/
├── src/tezaver/          # Ana kaynak kodları
│   ├── core/             # Temel yapılar (models, config, state)
│   ├── data/             # Veri toplama modülleri
│   ├── features/         # İndikatör hesaplama
│   ├── snapshots/        # Pattern snapshot engine
│   ├── outcomes/         # Rally etiketleme
│   ├── rally/            # Rally analiz ve kümeleme
│   ├── wisdom/           # Pattern bilgeliği
│   ├── brains/           # Regime & shock analizi
│   ├── levels/           # Seviye tespiti
│   ├── export/           # Bulut export
│   ├── backup/           # Yedekleme
│   └── ui/               # Streamlit panel
├── tests/                # Test dosyaları
├── coin_cells/           # Coin veri hücreleri
├── data/                 # İşlenmiş veriler
│   ├── coin_profiles/    # Coin profilleri
│   ├── wisdom/           # Global bilgelik
│   └── coin_states/      # CoinState JSON'ları
├── library/              # Snapshot kütüphanesi
├── backups/              # Yedekler
└── requirements.txt      # Python bağımlılıkları
```

## 🔧 Yapılandırma

Tüm konfigürasyon ayarları `src/tezaver/core/config.py` dosyasında bulunur:

- **DEFAULT_COINS**: Takip edilen coinler
- **DEFAULT_HISTORY_TIMEFRAMES**: Veri toplama zaman dilimleri
- **RALLY_THRESHOLDS**: Rally eşikleri (%5, %10, %20)
- **MIN_PATTERN_SAMPLES**: Minimum pattern örnek sayısı
- **TRUST_THRESHOLD**: Güven skoru eşiği

## 📈 UI Özellikleri

### Ana Sayfa
- Günlük rapor özeti
- Top coinler
- Sistem metrikleri

### Piyasa Özeti
- Tüm coinlerin tablo görünümü
- Sıralama ve filtreleme
- Coin seçimi

### Coin Detay Sayfası
- **Genel Bakış**: Temel metrikler, risk seviyesi
- **Bilgelik**: Volatilite imzası, güvenilir/ihanetkâr pattern'ler
- **Rally Aileleri**: Kümeleme sonuçları, performans
- **Yükseliş Lab**: Rally detayları, Fast15 analizi
- **Seviyeler**: Destek/direnç seviyeleri
- **Risk & Kurallar**: Risk metrikleri, kurallar
- **Bulut Paketi**: Export JSON görüntüleme

### Sidebar Kontrolleri
- **Pipeline**: Full/Fast pipeline çalıştırma
- **Testler**: Unit testleri çalıştırma
- **Yedekleme**: Mini/Full backup
- **Sistem Taramaları**: Fast15, Pattern Stats, vb.

## 🧪 Test Coverage

Sistem kapsamlı test coverage'a sahiptir:

- **Unit Tests**: İndikatör hesaplamaları, rally tespiti
- **Integration Tests**: Pipeline akışı, veri kalitesi
- **UI Tests**: Streamlit komponentleri, i18n

Son test sonuçları: **34/35 test geçti** ✅

## 🌐 Türkçe Dil Desteği

Tüm UI elementleri Türkçe dilinde sunulmaktadır:
- Metrikler ve etiketler
- Açıklamalar ve tooltips
- Hata mesajları
- Zaman formatları (UTC+3)

## 📝 Geliştirme Notları

### Kod Standartları
- Type hints kullanımı
- Docstring'ler (Google style)
- Modüler yapı
- DRY prensibi

### Performans
- Parquet formatında verimli depolama
- Pandas vectorized operasyonlar
- Streamlit caching (@st.cache_data)

### Loglama
- Merkezi logging sistemi (core/logging_utils.py)
- Dosya ve console output
- Detaylı hata mesajları

## 🤝 Katkıda Bulunma

1. Fork edin
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add amazing feature'`)
4. Branch'inizi push edin (`git push origin feature/amazing-feature`)
5. Pull Request açın

## 📄 Lisans

Bu proje proprietary/closed-source olarak geliştirilmektedir.

## 📞 İletişim

Sorular ve öneriler için: [email veya iletişim bilgisi]

---

**Tezaver-Mac** - Kripto piyasalarında pattern tanıma ve bilgelik sistemi 🧬
