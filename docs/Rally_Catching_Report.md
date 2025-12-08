# Rally Yakalama ve Coin Detay Raporu
**Tarih:** 08 Aralık 2025
**Analiz:** Antigravity / AI IDE

Bu rapor, Tezaver-Mac sistemindeki "Rally" (Yükseliş) yakalama mekanizmasının teknik detaylarını ve Coin Detay sayfasındaki sunumunu açıklar.

## 1. Rally Yakalama Mekanizması (The Engine)

Sistem, **"Oracle Mode"** adı verilen bir geçmiş tarama algoritması kullanır. Bu yöntem, grafik üzerinde dip ve tepeleri tespit ederek "gerçekleşmiş" yükselişleri veritabanına kaydeder.

### 1.1. Algoritma: Oracle Mode
`src/tezaver/rally/fast15_rally_scanner.py` ve `time_labs_scanner.py` içinde çalışır.

1.  **Lokal Dip ve Tepe Bulma:**
    -   Her mum için `±10 bar` (toplam 21 bar) genişliğindeki pencerede en düşük (Lokal Dip) ve en yüksek (Lokal Tepe) noktalar bulunur.
2.  **Eşleştirme:**
    -   Her Lokal Dip için, kendisinden sonra gelen en yakın Lokal Tepe bulunur.
3.  **Kazanç Hesabı:**
    -   `(Tepe Fiyatı - Dip Fiyatı) / Dip Fiyatı` formülü ile yüzdesel kazanç hesaplanır.
    -   Eğer kazanç belirlenen eşiğin (Fast15 için %5) üstündeyse "Rally Adayı" olarak işaretlenir.
4.  **Deduplication (Tekilleştirme):**
    -   Aynı tepeye işaret eden birden fazla dip varsa (ikili dip veya "ragged bottom"), **en düşük fiyata sahip olan dip** "başlangıç noktası" (Event Time) olarak seçilir.

### 1.2. Zaman Dilimleri ve Eşikler

| Modül | Zaman Dilimi | Min. Kazanç | Pencere (Lookahead) | Amaç |
| :--- | :--- | :--- | :--- | :--- |
| **Fast15** | 15 Dakika (15m) | %5 | 10 Bar | Hızlı "vur-kaç" hareketlerini yakalamak. |
| **Time-Labs** | 1 Saat (1H) | %10 | 12 Bar | Orta vade "swing" hareketlerini analiz etmek. |
| **Time-Labs** | 4 Saat (4H) | %15 | 8 Bar | Ana trend dönüşlerini ve büyük rallileri yakalamak. |

### 1.3. Çoklu Zaman Dilimi (MTC) Zenginleştirme
Her tespit edilen rally olayı için, o andaki **tüm** zaman dilimlerinin teknik durumu ("Snapshot") kaydedilir:
-   **15m:** RSI, MACD Fazı, Hacim.
-   **1H / 4H / 1D:** Trend Soul (Trend Gücü), RSI, Rejim (Boğa/Ayı).
*Bu sayede "Rally başladığında 4 saatlik grafik nasıldı?" sorusuna cevap verilebilir.*

---

## 2. Coin Detaylarında Sunum (The UI)

Kullanıcı arayüzünde (`src/tezaver/ui`), bu veriler **"Yükseliş Lab"** sekmesi altında, üç alt sekmede sunulur.

### 2.1. Fast15 Sekmesi (`fast15_lab_tab.py`)
-   **Filtreleme (Kovalar):** Yükselişler büyüklüklerine göre ayrılır: `%5-10`, `%10-20`, `%20-30`, `%30+`.
-   **Grafik:** Tespit edilen rally'nin "Dip" ve "Tepe" noktası grafik üzerinde oklarla işaretlenir.
-   **Multi-TF Analiz:** Seçilen rally anındaki 15m, 1h, 4h ve 1d teknik göstergeleri (RSI, Trend Soul) sekmeler halinde gösterilir.
-   **Özet Cümleler:** "Bu coindeki %10+ yükselişlerin %70'inde RSI > 60 idi" gibi istatistiksel çıkarımlar (Türkçe) sunulur.

### 2.2. Time-Labs Sekmesi (`time_labs_tab.py`)
-   **Kalite Puanı:** 1H ve 4H rallilerde, rally'nin şekli (Clean/Spike) ve trend uyumu baz alınarak hesaplanan **Kalite Puanı (0-100)** filtresi mevcuttur.
-   **Detaylı Liste:** Tablo görünümünde "Drawdown" (Tepe öncesi geri çekilme) ve "Süre" (Tepeye kaç bar sürdüğü) gösterilir.

### 2.3. Rally Kalite Sistemi (Rally v2)
Sistem ayrıca her rally için şu özellikleri hesaplar (`rally_quality_engine.py`):
-   **Rally Shape:** `Clean` (Temiz yükseliş) veya `Spike` (Ani iğne atıp düşme).
-   **Retention:** Zirve sonrası fiyatın ne kadar korunduğu.
-   **Trend Efficiency:** Yükselişin ne kadar "doğrusal" olduğu.

---

## 3. Veri Akışı Özet
1.  **Tarama:** `run_offline_maintenance.py` veya Sidebar'daki "Hızlı Tara" butonları çalıştırılır.
2.  **Kayıt:** Sonuçlar `data/coin_cells/{SYMBOL}/rallies/` altına `.parquet` formatında kaydedilir.
3.  **Görüntüleme:** UI açıldığında bu dosyalardan okuma yapılır ve interaktif grafiklere dönüştürülür.

## 4. Sonuç ve Durum
-   **Durum:** ✅ **Aktif ve Çalışır Durumda.**
-   **Veri:** Sistemin sağlıklı çalışması için en az 1000 barlık geçmiş veriye ihtiyaç vardır.
-   **Eksik:** Şu an için "Canlı Sinyal" (henüz tepe yapmamış, yeni başlayan) modülü aktif değildir; sistem sadece "bitmiş/oluşmuş" rallileri analiz eder (Laboratuvar Modu).
