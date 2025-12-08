# Tezaver-Mac Offline Lab v1.0 – Release Notes
**Tarih:** 2025-12-07
**Statü:** Savaş Öncesi Genel Prova (Offline Lab)

## 🎯 Vizyon
Bu sürüm, Tezaver-Mac sisteminin "Laboratuvar" fazının tamamlandığını işaret eder. Sistem, gerçek dünya verileriyle (Binance) çalışır ancak **asla** otomatik işlem yapmaz. Tüm kararlar operatör (insan) denetimindedir.

## 🚀 Eklenen Özellikler (Completed Features)

### 1. Rally Stack (Yükseliş Motoru)
- **Fast15 Scanner:** 15 dakikalık grafikte ani yükselişleri (%5, %10, %20+) yakalar.
- **Time-Labs (1h / 4h):** Orta vadeli trend yapılarını ve "Family" (aile) ilişkilerini analiz eder.
- **MTC v1 (Multi-Timeframe Context):** Her sinyali 15m/1h/4h/1d indikatörleriyle (RSI, MACD, TrendSoul) zenginleştirir.
- **Rally v2 Quality:** Sinyalleri "Shape" (Şekil), "Pre-Peak Drawdown" ve "Retention" (Kalıcılık) metrikleriyle puanlar.

### 2. Simülasyon Stack (v1.5)
- **Sim Engine:** Geçmiş olaylar üzerinde strateji backtest'i yapar.
- **Presets (Şablonlar):** `FAST15_SCALPER_V1`, `H1_SWING_V1`, `H4_TREND_V1` gibi hazır stratejilerle tek tıkla test imkanı.
- **Scoreboard & Affinity:** Bir coin için en iyi çalışan stratejiyi bulur ve "Strateji Uyumu" (Affinity) puanı verir.
- **Promotion (Terfi):** Başarılı stratejileri "APPROVED" olarak işaretler.

### 3. Rally Radar
- Coin'in genel durumunu (HOT, COLD, NEUTRAL, CHAOTIC) sınıflandırır.
- Hangi "Şerit"te (Lane) aktığını belirler (örn. "FAST_LANE" veya "SLOW_LANE").

### 4. UI & Bilge Kartlar
- **Yükseliş Lab:** Tüm zaman dilimlerindeki fırsatları tek ekranda gösterir.
- **Bilge Kartlar:** Coin'in karakterini, simülasyon uyumunu ve radar durumunu Türkçe anlatımla sunar.
- **Bulut Export:** Tüm analiz verilerini `data/coin_profiles` altına JSON olarak yedekler.

### 5. Offline Maintenance (Bakım Modu)
- Tek komutla (`run_offline_maintenance.py --mode full`) tüm analiz boru hattını (Pipeline) çalıştırır.
- Veri indirme -> Tarama -> Simülasyon -> Raporlama zincirini otomatik yönetir.

## 🚫 Kapsam Dışı (Out of Scope for v1.0)
- **Canlı Emir Gönderimi (Order Execution):** `ccxt` private API kullanımı kapalıdır.
- **Otomatik Trade Botu:** Sistem kendi başına pozisyon açamaz.
- **Gerçek Para Riski:** Sadece analiz ve simülasyon amaçlıdır.

## 🛠️ Teknik Altyapı
- **Dil:** Python 3.10+
- **UI:** Streamlit
- **Veri:** `ccxt` (Binance Public Data), Parquet (Depolama)
- **Test:** `pytest` (Unit & Integration)

---
*Tezaver-Mac Ekibi - 2025*
