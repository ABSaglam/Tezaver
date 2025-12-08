# TEZAVER MATRIX MİMARİSİ (M25) VE "ÜÇLÜ GÜÇ" DOKTRİNİ

## 1. Temel Felsefe: "Futbol Takımı" Metaforu

Matrix Motoru (Unified Engine), piyasayı tek bir bütün olarak ele almaz. Karar verme sürecini, sorumlulukları net bir şekilde ayrılmış üç ana role böler. Bu yapıya **"ÜÇLÜ GÜÇ" (The Trinity)** diyoruz.

Bu yapının amacı; sinyal tespiti, risk yönetimi ve işlem icrasını birbirinden izole ederek sistemi modüler, test edilebilir ve güvenli hale getirmektir.

---

## 2. Mimari Bileşenler

### 🔭 1. Gözcü (The Scout) — `IAnalyzer`
**Görevi:** Sahayı (Piyasayı) dürbünle izlemek ve fırsatları raporlamak.
*   **Ne Yapar:** Sadece veriye bakar. "Şurada bir hareket var" der.
*   **Ne Yapmaz:** Parayı bilmez. Risk hesabı yapmaz. Alın veya satın demez. Sadece "Sinyal Var" der.
*   **Çıktı:** `MarketSignal` (Örn: "BTCUSDT, 1h, RALLY_START, Score: 85")
*   **Mevcut Uygulama:** `RallyAnalyzer` (Mevcut Ralli algoritmasını kullanır).

### 🧠 2. Koç (The Coach) — `IStrategist`
**Görevi:** Gözcüden gelen raporu değerlendirmek, kasanın durumuna bakmak ve taktiksel kararı vermek.
*   **Ne Yapar:**
    *   Sinyalin kalitesine bakar.
    *   Kasada ne kadar para olduğuna bakar (`account_state`).
    *   Risk yönetimi yapar (Kasanın %10'u ile gir, Stop Loss %5 olsun).
    *   Pozisyon takibi yapar (Kar hedefine ulaştık mı? Satmalı mıyız?).
*   **Çıktı:** `TradeDecision` (Örn: "BUY BTCUSDT, Miktar: 0.05, Stop: 89000")
*   **Mevcut Uygulama:** `RallyStrategist` (Sabit %10 risk, %15 TP, %5 SL).

### ⚡ 3. Oyuncu (The Player) — `IExecutor`
**Görevi:** Koçun verdiği kararı saniye sektirmeden, en iyi fiyattan uygulamak.
*   **Ne Yapar:** Emri borsaya iletir (veya simülasyonda deftere yazar).
*   **Özelliği:** Duygusuzdur. Sorgulamaz. "Sat" dendiğinde satar.
*   **Çıktı:** `ExecutionReport` (Örn: "✅ İşlem Başarılı: 0.05 BTC @ 91000$ alındı").
*   **Mevcut Uygulamalar:**
    *   `MatrixExecutor`: Simülasyon ve kağıt üstünde işlem için (Sanal Borsa).
    *   `BinanceExecutor`: (*Planlanan*) Gerçek borsa bağlantısı.

---

## 3. Çalışma Akışı (The Loop)

`UnifiedEngine` (Orkestra Şefi), bu üçlüyü her "Tick" (yeni veri geldiğinde) şöyle yönetir:

1.  **Veri Gelir:** Motor, `Analyzer`'a "Buna bak" der.
2.  **Sinyal Kontrolü:** `Analyzer` bir `MarketSignal` üretir (veya Stratejist uyanabilsin diye Motor `MONITOR` sinyali üretir).
3.  **Karar Anı:** Motor, `Executor`'dan güncel kasayı/pozisyonları öğrenir ve Sinyal ile birlikte `Strategist`'e sunar.
4.  **Emir:** `Strategist` bir `TradeDecision` (Karar) döndürürse (Al/Sat), Motor bunu `Executor`'a iletir.
5.  **İcra:** `Executor` işlemi yapar ve raporu (`ExecutionReport`) döner.

---

## 4. Avantajlar

1.  **Güvenlik:** Koç çökse bile Gözcü çalışmaya devam eder. Para yönetimi (Koç) ile Alım-Satım (Oyuncu) ayrıldığı için "yanlışlıkla tüm parayı basma" riski kod seviyesinde izole edilir.
2.  **Esneklik:**
    *   Yarın "Rally" yerine "RSI" stratejisi denemek isterseniz sadece **Gözcü**yü değiştirirsiniz. Koç ve Oyuncu aynı kalır.
    *   Gerçek parayla oynamak isterseniz sadece **Oyuncu**yu (`MatrixExecutor` -> `BinanceExecutor`) değiştirirsiniz. Stratejiniz bozulmaz.
3.  **Simülasyon Gerçekliği:** Matrix modunda kullandığımız `MatrixExecutor`, gerçek borsanın birebir taklididir (Komisyon, bakiye kontrolü vb.). Bu sayede test sonuçları hayal ürünü değil, gerçeğe en yakın veri olur.

## 5. Mevcut Durum (v1.0)

*   [x] **Analyzer:** `RallyAnalyzer` aktif. 15dk ve 1h rallileri yakalıyor.
*   [x] **Strategist:** `RallyStrategist` aktif. TP/SL mekanizması eklendi.
*   [x] **Executor:** `MatrixExecutor` aktif. Sanal bakiye ve pozisyon maliyeti takibi yapıyor.
*   [x] **Orkestra:** `UnifiedEngine` aktif. "Sessiz anlarda" bile pozisyon kontrolü yapabiliyor.

---

## 6. SAKLI YAPI: Matrix, Bulutun Dijital İkizidir (The Digital Twin)

Tezaver Mac uygulamasının içine gizlenmiş bu motor, aslında **Bulut Sisteminin (Tezaver Cloud)** tam bir simülasyonudur.

**Neden Mac İçinde?**
Bulut (Canlı Borsa) masraflıdır, hata affetmez ve gerçek para gerektirir. Biz ise Mac içindeki bu "Laboratuvar" ortamında, bulutun **tüm fonksiyonlarını** birebir taklit ederiz.

| Mac Bileşeni (Matrix) | Bulut Karşılığı (Cloud) | Amaç |
| :--- | :--- | :--- |
| **Unified Engine** | **Cloud Core Service** | 7/24 çalışan ana döngüyü simüle eder. |
| `RallyAnalyzer` | **Signal Microservice** | Algoritmaları geçmiş veride dener, doğruluğunu kanıtlar. |
| `RallyStrategist` | **Risk Manager Bot** | Para yönetim kurallarını (TP/SL) risksiz ortamda optimize eder. |
| `MatrixExecutor` | **Binance API Gateway** | Emri borsaya göndermeden, "göndermiş gibi" yapar ve sonuçları hesaplar (Slippage, Komisyon dahil). |

**Felsefe:**
> *"Barışta ter dökmeyen, savaşta kan döker."*

Tezaver Mac, stratejistlerin **Uçuş Simülatörüdür**. Burada `1970`'ten günümüze kadar tüm piyasa koşullarında ("Dünya Savaşı" modu) test edilmemiş hiçbir strateji, buluta (Canlı Savaşa) aktarılmaz.

**Mac İçindeki Gizli Güç:**
Kullanıcı arayüzde sadece basit bir "Başlat" butonu görür; ancak arkada **Milyonlarca dolarlık bulut altyapısının birebir kopyası** (Offline Mode olarak) çalışır. Bu sayede evdeki Mac'iniz, aslında devasa bir Hedge Fund sunucusu gibi davranır.

---

**Özet:** Matrix, bir "Al-Sat Botu" değil; modüler bir **Varlık Yönetim İşletim Sistemi**dir.

