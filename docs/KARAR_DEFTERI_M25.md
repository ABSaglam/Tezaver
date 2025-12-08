# 1️⃣ Karar Defteri – M25: Tezaver Matrix ve Üçlü Güç Doktrini

## M25.0 – Tezaver Matrix’in Rolü

* **Tezaver Matrix**, Tezaver Bulut’un **Mac içinde çalışan dijital ikizidir**.
* Görevi:
  * Offline Lab’te öğrenilmiş aklı (Rally, Sim, Radar, Risk, Promotion, Affinity) alıp,
  * Bunu **gerçek zamana yakın** bir ortamda (canlı/pseudo-canlı veriyle) çalıştırmak,
  * Ama **şimdilik sadece simülasyon / paper-trade** modunda kalmak.
* Matrix; bir “Al-Sat Botu” değil, **modüler bir Varlık Yönetim İşletim Sistemi**’dir.

---

## M25.1 – Üçlü Güç Doktrini (The Trinity)

Matrix Motoru’nun kalbinde **Üçlü Güç (The Trinity)** vardır:

1. **Gözcü (The Scout) – IAnalyzer**
2. **Koç (The Coach) – IStrategist**
3. **Oyuncu (The Player) – IExecutor**

Bu ayrımın amacı:
* Sinyal tespiti (algoritma),
* Risk & kasa yönetimi (taktik),
* İşlem icrasını (teknik uygulama)

gibi üç kritik alanı **kod seviyesinde birbirinden izole etmek**, böylece:
* Modülerlik,
* Test edilebilirlik,
* Güvenlik
  sağlamaktır.

---

## M25.2 – Gözcü (The Scout) – IAnalyzer

**Görevi:** Sahayı (piyasayı) dürbünle izlemek ve **fırsatları raporlamak**.

* **Yaptığı:**
  * Veriye bakar (fiyat, hacim, indikatörler, rally event’leri).
  * “Burada ilginç bir hareket var” der.
* **Yapmadığı:**
  * Parayı bilmez.
  * Risk hesabı yapmaz.
  * “Al” ya da “Sat” demez.
* **Çıktısı:** `MarketSignal`
  * Örnek: `{"symbol": "BTCUSDT", "tf": "1h", "kind": "RALLY_START", "score": 85, "meta": {...}}`

**M25.2.1 – Mevcut / Hedef Uygulama**
* **RallyAnalyzer** (hedef / mevcut):
  * Fast15 & Time-Labs çıktılarını, Rally Quality v2 skorlarını,
  * Rally Radar & MTC v1 ile birleştirerek `MarketSignal` üretir.

---

## M25.3 – Koç (The Coach) – IStrategist

**Görevi:** Gözcü’den gelen sinyali, kasanın durumu ve risk kuralları ile birlikte değerlendirip **taktiksel karar** vermektir.

* **Yaptığı:**
  * Sinyal kalitesine bakar (quality_score, rally_shape, radar, sim_affinity).
  * Hesap durumuna bakar (equity, mevcut pozisyonlar).
  * Risk yönetimi uygular:
    * Pozisyon boyutu (kasanın X’i ile gir),
    * TP/SL oranları,
    * Maksimum eş zamanlı pozisyon sayısı.
  * Aktif pozisyonları takip eder (TP geldi mi, SL geldi mi, zaman doldu mu).

* **Çıktısı:** `TradeDecision`
  * Örnek: `{"action": "OPEN_LONG", "symbol": "BTCUSDT", "size": 0.05, "entry": "MARKET", "tp_pct": 0.15, "sl_pct": 0.05}`

* **Stratejinin Kaynağı:**
  * Sim Affinity & Promotion:
    * Sadece **APPROVED + reliable** etiketi taşıyan stratejiler otomatik kullanılabilir.

**M25.3.1 – Mevcut / Hedef Uygulama**
* **RallyStrategist** (v1 hedef):
  * Sim Presets + Sim Affinity + Sim Promotion kurallarına göre:
    * Hangi stratejinin (FAST15_SCALPER / H1_SWING / H4_TREND) devrede olacağına karar verir.
    * Bu strateji için TP/SL, max hold, risk yüzdelerini uygular.
    * Radar & Risk panelini guardrail olarak kullanır.

---

## M25.4 – Oyuncu (The Player) – IExecutor

**Görevi:** Koç’un verdiği kararı **sorgulamadan ve en iyi şekilde icra etmek**.

* **Yaptığı:**
  * TradeDecision’ı alır.
  * “Emir”i uygular:
    * Matrix modunda: Paper-trade defterine yazar, pseudo-fill simüle eder, komisyon & slippage uygular.
    * İleride Bulut modunda: Binance vb. API üzerinden Borsa’ya iletir.
  * Güncel hesap durumunu ve açık pozisyonları UnifiedEngine’e raporlar.
* **Çıktısı:** `ExecutionReport`
  * Örnek: `{"status": "FILLED", "symbol": "BTCUSDT", "avg_price": 91000, "qty": 0.05, "fee": 3.1, "ts": ...}`

**M25.4.1 – Mevcut / Hedef Uygulamalar**
* **MatrixExecutor** (v0.x / v1.0):
  * Simülasyon ve kağıt üstünde işlem için.
  * Sanal bakiye, pozisyon maliyeti, realized/unrealized PnL hesaplar.
* **BinanceExecutor** (gelecek):
  * Gerçek borsa bağlantısı.
  * Aynı IExecutor sözleşmesi ile çalışır; sadece backend değişir.

---

## M25.5 – UnifiedEngine (Orkestra Şefi)

Her yeni “tick”/bar geldiğinde, **UnifiedEngine** bu üçlüyü şu sırayla koordine eder:

1. **Veri Akışı:** Fiyat / bar / event geldiğinde, Engine bunu IAnalyzer’a iletir.
2. **Sinyal:** Analyzer 0..N adet `MarketSignal` üretir.
3. **Karar:** Engine, Executor’dan güncel `AccountState` / `Positions` bilgisini alır. Sinyalleri ve hesabı birlikte IStrategist’e gönderir. IStrategist, 0..N adet `TradeDecision` üretir.
4. **İcra:** Engine, `TradeDecision`’ları IExecutor’a yollar. IExecutor, `ExecutionReport` üretir ve Engine’e döner.
5. **Sürekli Kontrol:** Sinyal yokken dahi, Engine periyodik olarak açık pozisyonları ve TP/SL/timed-exit koşullarını kontrol ettirir.

---

## M25.6 – Güvenlik ve Esneklik Faydaları

* **Kod Güvenliği:** “Yanlışlıkla tüm parayı tek işleme basma” türü hatalar, IStrategist ve IExecutor ayrımı sayesinde azaltılır.
* **Strateji Esnekliği:** Yeni sinyal algoritması denemek için sadece IAnalyzer’ı değiştirirsin; IStrategist ve IExecutor yerinde kalır.
* **Gerçek / Sim Ayrımı:** Matrix’te test ettiğin tüm stratejiler, **aynı UnifiedEngine + IStrategist + IAnalyzer** ile Cloud’a taşınır; sadece executor değişir.

---

## M25.7 – Matrix = Bulutun Dijital İkizi

| Mac / Matrix Bileşeni | Bulut Karşılığı     | Amaç                                                   |
| --------------------- | ------------------- | ------------------------------------------------------ |
| UnifiedEngine         | Cloud Core Service  | 7/24 ana döngünün simülasyonu                          |
| RallyAnalyzer         | Signal Microservice | Strateji sinyallerini geçmişte kanıtlar                |
| RallyStrategist       | Risk Manager Bot    | Para yönetimini risksiz ortamda optimize eder          |
| MatrixExecutor        | Exchange Gateway    | Gerçek borsaya emir göndermeden “göndermiş gibi” yapar |

**Felsefe:**
> “Barışta ter dökmeyen, savaşta kan döker.”
> Tezaver Matrix, stratejistlerin **Uçuş Simülatörü**dür. Burada test edilmemiş hiçbir strateji, Bulut savaş alanına çıkmaz.

---

## M25.8 – M25 v1 Trinity Döngüsü Doğrulama (Karar)

**M25.v1 – Trinity Döngüsü Canlı Doğrulama (verify_m25.py)**

**Amaç:**
Tezaver Matrix’in Üçlü Güç (Gözcü–Koç–Oyuncu) mimarisinin, uçtan uca tek bir senaryoda **gerçek para akışı gibi** çalıştığını kanıtlamaktır.

**Test Sonuçları:**
1. **RALLY_START Tespiti:** Gözcü (Analyzer) %1'lik ralliyi yakalamış ve `MarketSignal` (Score 50) üretmiştir.
2. **BUY Kararı:** Koç (Strategist) sinyali ve hesap durumunu inceleyip `TradeDecision(BUY)` vermiştir.
3. **İcra:** Oyuncu (Executor) emri `FILLED` statüsünde işlemiş ve pozisyon açmıştır.
4. **MONITOR:** UnifiedEngine, sinyal olmayan barlarda bile `MONITOR` döngüsü ile pozisyonu izlemeye devam etmiştir.
5. **SELL Kararı:** Fiyat hedefi yakalandığında (~%15), Koç `TradeDecision(SELL)` vermiş ve kâr realize edilmiştir.
6. **Sonuç:** 10,000 USDT -> 10,155 USDT (+%1.55 Net Kâr).

**Karar:**
* M25 Trinity mimarisi **operasyonel olarak sağlamdır**.
* Matrix, Bulut tarafı için **kullanılabilir dijital ikiz** statüsüne yükseltilmiştir.
* **Onaylandı:** 03.01.2024 (Simüle Tarih) / 07.12.2025 (Gerçek Tarih)

---

## M25.9 – M25.4 Guardrail Fusion & Offline Intelligence

**Hedef:**
Matrix'i "Labda kırbaç gibi koşturan ama canlıda kafasına göre işlem açmayan" disiplinli bir hedge-fund motoruna dönüştürmek.

**Politika (Policy):**
1.  **Promotion Status (Sim):**
    *   `REJECTED`: Kesinlikle yeni `LONG` pozisyon açma.
    *   `CANDIDATE`: Dikkatli ol (veya izin ver).
    *   `APPROVED`: Normal işlem prosedürü.
2.  **Radar State (Rally):**
    *   `COLD`: Piyasa soğuk, ralli beklenmiyor -> `LONG` açma.
    *   `CHAOTIC`: Volatilite çok yüksek -> `LONG` açma.
    *   `HOT / NEUTRAL`: İşleme izin ver.

**Uygulama Alanı:**
*   `GuardrailController` sınıfı, `data/` altındaki JSON (Sim/Radar) dosyalarını okuyarak bu kararları `MultiSymbolEngine` içinde uygular.

---

## M25.10 – War Game v1: Göz Kalibrasyonu

**Amaç:**
Matrix'in (Filo Komutanı) kağıt üzerindeki teorik yeteneğini, uzun süreli ve tek bir cephede (Tek Coin) test ederek insan gözüyle doğrulamak. "Savaş Oyunu", yazılımın değil, stratejinin test edildiği yerdir.

**Prosedür:**
1.  **Tek Coin Seç:** (Trendli ve olaylı bir geçmişi olan).
2.  **Lab Verisiyle Kıyasla:** Offline Simülasyon ne sonuç vermiş?
3.  **Matrix'i Koştur:** Aynı zaman aralığında, birebir aynı Intelligence (Radar/Promotion) ile Matrix motorunu çalıştır.
4.  **İncele:**
    *   Matrix nerede girdi? Lab ile aynı yerde mi?
    *   Girmemesi gereken yerde Guardrail devreye girdi mi?
    *   Lüzumsuz işlem var mı?

**Hedef:**
"Matrix'in kararları benim (Operatör) mantığımla örtüşüyor." diyebilmek.
Kapsam: Tek Coin, Uzun Dönem. Filo testinden önce gelir.

## M25.11 – War Game v2: Guardrails On

**Amaç:**
M25 Motorunu (Gözcü+Koç+Oyuncu) ve M25.9 Intelligence Bridge (Guardrail) mekanizmasını **bütünleşik olarak** test etmek.

**Yöntem:**
1.  **Gerçek Intelligence:** `data/coin_profiles` verileri kullanılır.
2.  **Strict Mode:** Guardrail kuralları "Tavsiye" değil "Kanun" olarak uygulanır.
    *   COLD env -> Kesinlikle Blok.
    *   REJECTED strategy -> Kesinlikle Blok.
3.  **Ölçüm:**
    *   Bloklanan Sinyal / Toplam Sinyal Oranı.
    *   Guardrail Sebebi Dağılımı (`BLOCK_RADAR_COLD` vs).
    *   Korunan Sermaye (Bloklanan zararlı trade'lerin potansiyel kaybı).

**Hedef:**
Matrix'in "Körü körüne saldıran" bir askerden, "Emirlere uyan" disiplini bir birliğe dönüştüğünü kanıtlamak.
PnL'den ziyade **Davranışsal Tutarlılık** (Behavioral Consistency) esastır.
**Beklenen Çıktı:** Düşük DD, Düşük İşlem Sayısı, "Temiz" Trade Geçmişi.
