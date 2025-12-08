# Tezaver-Mac

## Offline Lab v1.0 – Karar Defteri & Operatör Akışı

> Bu doküman, **Tezaver-Mac Offline Lab v1.0** fazının nasıl kullanılacağını, sınırlarını ve operatörün (Ali) günlük / haftalık akışını tanımlar.
> Bu faz, **sadece analiz ve simülasyon** içindir; **gerçek para ile otomatik trade kesinlikle içermez.**

---

## 1. Amaç & Kapsam

1.1. **Offline Lab v1.0’ın Ana Amacı**

* Tezaver’in elindeki veriyi kullanarak:

  * Çok zaman dilimli rally tespiti (15m, 1h, 4h),
  * Rally kalite analizi (shape, quality score),
  * Simülasyon ile strateji testleri,
  * Strateji uyumu (affinity) ve terfisi (promotion),
  * Piyasa ortamı analizi (Rally Radar)
* Tüm bunları **tek bir offline laboratuvar** içinde toplamak.

1.2. **Bu Fazın Sınırları**

* **Yapmaz:**

  * Borsaya emir göndermez.
  * API üzerinden canlı trade yapmaz.
  * Otomatik al-sat kararı vermez.

* **Yapar:**

  * Veriyi işler, raporlar, yorumlar.
  * Strateji + zaman dilimi + coin kombinasyonları için **kanıt üretir**.
  * Operatöre (Ali’ye) “hangi strateji, hangi coin’de, hangi koşulda daha mantıklı görünüyor?” sorusunun cevabına yardımcı olur.

---

## 2. Temel Prensipler (Anayasa Düzeyi Kurallar)

2.1. **Offline Önceliği**

* Bu faz, **“Laboratuvar Fazı”**dır.
* Her kararın dayandığı yer:
  **Geçmiş veri + simülasyon + istatistiksel gözlem**
* Hiçbir çıktı “garantili kazanç” değildir; sadece:

  > “Bu koşullarda geçmişte böyle davranmış” bilgisidir.

2.2. **Manuel Onay Zorunluluğu**

* Strateji “APPROVED” (Onaylı) bile olsa:

  * **Son karar her zaman operatöre aittir.**
  * Tezaver sadece **kanıt üretir, tavsiye vermez.**

2.3. **Guardrail İlkesi**

* Sim v1.5 Promotion kuralları, **riskten koruma bariyeri**dir.
* Bir strateji:

  * Yeterli örnek sayısı yoksa,
  * Çok yüksek drawdown üretiyorsa,
  * Win-rate ve expectancy zayıfsa
    → **REJECTED** veya **CANDIDATE** kalır, **APPROVED olamaz.**

2.4. **Versiyon Donma İlkesi**

* Offline Lab v1.0 için:

  * Çekirdek davranışlar (Fast15, Time-Labs, Sim, Radar, Offline Maintenance) **stabil** kabul edilir.
  * Bu doküman, bu davranışlara karşılık gelir.
  * Büyük mimari değişiklik yapılacaksa:

    * Yeni bir faz açılır (örn. `Offline Lab v1.1`),
    * Bu doküman **geçmiş anotasyon** olarak korunur.

---

## 3. Offline Lab Bileşenleri (Yüksek Seviye)

Bu bölüm operatörün zihninde “harita” oluştursun diye özet.

3.1. **Rally Scanner’lar**

* **Fast15 (15 Dakika Hızlı Yükselişler)**

  * 1–10 bar içinde %5 / %10 / %20 / %30+ yükselişleri bulur.
  * Multi-timeframe context (15m, 1h, 4h, 1d) ile snapshot çıkarır.
  * Rally v2 Quality ile kalite skorları eklenir.

* **Time-Labs (1 Saat & 4 Saat)**

  * 1h ve 4h zaman dilimlerinde benzer mantıkla rally’leri tespit eder.
  * 15m–1h–4h–1d bağlamlarını toplar.
  * Uzun soluklu hareketleri anlamak için kullanılır.

3.2. **Rally Quality & Radar**

* **Rally v2 Quality Engine**

  * `rally_shape` (clean, spike, choppy, weak)
  * `quality_score` (0–100)
  * `pre_peak_drawdown`, `trend_efficiency`, `retention` gibi metrikler.

* **Rally Radar**

  * Coin + timeframe için çevreyi değerlendirir:

    * HOT, NEUTRAL, COLD, CHAOTIC
  * Sinyal yoğunluğu, kalite, trend uyumu gibi faktörleri birleştirir.
  * “Şu an hangi kulvar daha anlamlı?” sorusuna cevap verir.

3.3. **Sim Stack (v1.0–v1.5)**

* **Sim Engine**:
  Verilen sinyaller üzerinde TP/SL/Timeout ile trade simülasyonu.

* **Presets**:
  FAST15_SCALPER_V1, H1_SWING_V1, H4_TREND_V1 gibi hazır stratejiler.

* **Scoreboard**:
  Bir coin için tüm presetleri tek seferde yarıştıran tablo.

* **Affinity & Promotion**:

  * Affinity: Stratejilere skor (0–100) + harf notu (A+, A, B, C, D).
  * Promotion: Stratejiyi APPROVED / CANDIDATE / REJECTED olarak işaretler.
  * Sonuçlar `sim_affinity.json` + promotion metadata olarak kaydedilir.

3.4. **UI Katmanı**

* **Bilge Kartlar (Wisdom Cards)**

  * Persona & rejim
  * Volatilite & hacim
  * Patterns & Fast15
  * Time-Labs & Strateji Uyum Özeti

* **Yükseliş Lab**

  * Rally Aileleri
  * Fast15 Lab
  * 1 Saat Time-Labs
  * 4 Saat Time-Labs

* **Sim Lab**

  * Strateji preset seçimi
  * Simülasyon çalıştırma
  * Scoreboard
  * Affinity/Preset promotion özetleri

* **Offline Maintenance**

  * Sidebar’dan tek tuşla:

    * Fast15
    * Time-Labs (1h, 4h)
    * Sim (affinity/promotion)
    * Rally Radar
      → Hepsini güncelleyen bakım pipeline.

---

## 4. Operatör Akışı – Günlük & Haftalık Rutin

Bu bölüm “Ali bu sistemi gerçek hayatta nasıl kullanacak?” sorusunun cevabıdır.

### 4.1. Günlük Akış (Minimal Kullanım)

**Adım 0 – Hazırlık**

* Gerekirse repo’yu güncelle (`git pull`).
* Sanal ortamı aç:

  ```bash
  cd /Users/alisaglam/TezaverMac
  source venv/bin/activate
  ```

**Adım 1 – Offline Lab Bakımı (Opsiyonel, günde 1 kez)**

* UI Sidebar’dan:

  * `🚀 Full Lab Bakımı Çalıştır` butonuna bas.
* Ya da CLI:

  ```bash
  PYTHONPATH=src python src/tezaver/offline/run_offline_maintenance.py --mode full --all-symbols
  ```
* Bu işlem:

  * Fast15
  * Time-Labs 1h/4h
  * Sim Affinity/Promotion
  * Rally Radar
    hepsini güncel hale getirir.

**Adım 2 – Coin Filtreleme (Bilgelik Sekmesi)**

* UI’da bir coin seç ve **“💡 Bilgelik”** sekmesine git.

* Burada şu kartlara bak:

  1. **Karakter & Rejim**

     * Trend eğilimi, ihanet eğilimi, hacim güvenilirliği.
  2. **Oynaklık & Hacim**

     * ATR, spike/dry pattern’leri.
  3. **Güvenilir/Riskli Tetikler & Fast15 Özeti**
  4. **Strateji Uyum & Zaman Analizi**

     * Rally Radar durumu (HOT / NEUTRAL / COLD / CHAOTIC),
     * En uyumlu strateji preset’i,
     * Affinity skoru ve promotion sonucu (APPROVED / CANDIDATE / REJECTED).

* **Günlük hedef:**
  Tüm coinler yerine, bu kartlara bakarak **2–5 tane “ilginç” coin** seçmek.

**Adım 3 – Derin İnceleme (Yükseliş Lab + Time-Labs)**

Seçtiğin bir coin için:

1. **Yükseliş Lab → Fast15 Tab**

   * 15m hızlı yükselişleri, kalite skorlarını ve 15m bağlamı gör.
2. **Yükseliş Lab → 1 Saat / 4 Saat Time-Labs**

   * Daha büyük timeframedeki rally’leri, onların quality dağılımını ve bağlamını incele.
3. Gözünün hoşuna giden:

   * Clean + yüksek kalite rally örnekleri,
   * Belirli bucket’larda (10–20%, 20–30%) yoğunlaşan aileler.

Bu aşama tamamen **“desen gözlemleme”** fazıdır.
**Trade kararı yok, sadece fotoğraf çekiyoruz.**

**Adım 4 – Sim Lab (Strateji Testi)**

Aynı coin için:

1. **“🧪 Sim Lab” sekmesine geç.**

2. Bir preset seç:

   * FAST15_SCALPER_V1
   * H1_SWING_V1
   * H4_TREND_V1

3. İki mod:

   * Sadece bir preset’i dene **veya**
   * “Bu coin için tüm preset’leri çalıştır” (Scoreboard).

4. Sim sonuçlarına bak:

   * Win rate
   * Net PnL
   * Max drawdown
   * Equity curve
   * Trade sayısı

5. Sistem:

   * Affinity skorlarını hesaplar,
   * Promotion kuralları ile **APPROVED / CANDIDATE / REJECTED** belirler,
   * En iyi stratejiyi “success badge” ile gösterir.

> **Günlük hedef:**
> Bir coin için, “benim gözüm + sistem verileri” ile **1 adet mantıklı strateji–coin–timeframe üçlüsü** tespit etmek.
> (Mesela: “ETHUSDT – H4_TREND_V1 – orta vadeli trend takip”)

**Adım 5 – Karar Kaydı (Tamamen Manuel)**

* Tezaver burada bile **trade açmaz**.
* Sen, kendi karar defterine (fiziksel ya da dijital):

  * Hangi coin,
  * Hangi timeframe,
  * Hangi strateji,
  * Neden beğendin?
  * Hangi risklerle?

  gibi notlar alırsın.

Bu fazın sonu burasıdır.
Her şey **offline analiz ve manuel yorum** düzeyinde kalır.

---

### 4.2. Haftalık Akış (Derin Bakım & Kalibrasyon)

**Haftada 1 gün** (örneğin Pazar):

1. **Tam Offline Maintenance Çalıştır**

   * Tüm pipelinelar taze olsun.

2. **Radar & Affinity Genel Bakış**

   * Birkaç ana coin (BTC, ETH, SOL, BNB, vb.) için:

     * Rally Radar sonuçlarını (HOT/NEUTRAL/COLD),
     * Strateji Affinity özetlerini,
     * Promotion statülerini gözden geçir.

3. **Preset Sağlık Kontrolü**

   * Eğer birçok coinde:

     * Aynı preset sürekli REJECTED oluyorsa,
     * Veya belirli bir preset aşırı iyi / aşırı kötü davranıyorsa;
   * Bunu bir “ileride inceleme” notu olarak kaydet.
   * Henüz preset parametrelerini **bu fazda** değiştirmiyoruz; önce veri toplayıp gözlemliyoruz.

4. **Notlar & Retrospektif**

   * O hafta sistemin gösterdikleri ile piyasada olan biteni kıyasla:

     * Trend yönleri uyumlu muydu?
     * Hot/Cold dönemleri anlamlı mıydı?
     * Onaylı stratejiler hangi koşullarda “daha mantıklı” göründü?
   * 3–5 satırlık kısa bir haftalık özet yaz:

     * “Bu hafta radar şunları söyledi, ben şunları hissettim.”

---

## 5. Kırmızı Çizgiler (Bu Fazda Asla Yapılmayacaklar)

5.1. **Otomatik Emir Yok**

* Tezaver-Mac Offline Lab v1.0:

  * **Asla** borsa API’sine emir göndermez.
  * Asla trade açma/kapatma butonuna bağlanmaz.
* Her türlü “trade” eylemi:

  * Manuel,
  * Operatörün kendi platformunda,
  * Kendi sorumluluğunda yapılır.

5.2. **“Tek Simülasyon = Gerçek Strateji” Yanılgısı Yok**

* Bir simülasyon sonucu asla:

  > “Bu %100 çalışıyor”
  > anlamına gelmez.
* Yorum:

  * “Bu koşullarda geçmişte böyle olmuş, bu da **dikkate değer** bir bulgu” seviyesinde tutulur.

5.3. **Faz Sızma Yok**

* Online trade fikirleri, sinyal botları, canlı emir yöneten şeyler:

  * **Offline Lab v1.0 kapsamı dışıdır.**
  * Bunlar için yeni bir faz tanımlanır (örn. “Online Bridge v0.x”),
  * Ayrı bir Karar Defteri yazılır.

---

## 6. Değişiklik Yönetimi

6.1. **Bu Dokümanın Rolü**

* Bu metin:

  * Offline Lab v1.0’ın **“operasyonel anayasası”**dır.
  * Koddan bağımsız, **insani çalışma tarzını** tanımlar.

6.2. **Güncelleme Kuralları**

* Yeni özellikler eklendiğinde:

  * Eğer sadece Lab içinde küçük iyileştirmelerse → bu dokümana küçük ekler yapılabilir.
  * Eğer konsept düzeyinde değişiklikse (örneğin Online trade, gerçek emir köprüsü, otomatik sinyal gönderimi):

    * **Yeni faz** açılır (Offline Lab v1.1 / Online v0.x),
    * Bu doküman “tarihi referans” olarak saklanır.

---

## 7. Özet – Bu Fazın Kısa Tanımı

> **Tezaver-Mac Offline Lab v1.0**,
> geçmiş veriyi kullanarak:
>
> * Rally ailelerini çıkaran,
> * Bu rally’lerin kalitesini puanlayan,
> * Stratejileri simüle edip yarıştıran,
> * Coin–strateji–zaman kombinasyonlarının uyumunu ölçen
>
> fakat **tek bir satır bile otomatik emir göndermeyen**
> bir **karar destek laboratuvarıdır.**

Operatör (Ali):

* Her gün / hafta bu lab’ı kullanarak:

  * Fotoğraf çeker,
  * Kanıt toplar,
  * Not alır,
  * Kendi sezgisiyle birleştirir.
* Bir sonraki büyük faz (online köprü, paper trading, gerçek emir sistemleri) ancak bu faz **bir süre kullanıldıktan ve sindirildikten sonra** başlatılır.

---

Bu dokümanı dosyaya kaydedip commit attığın anda:
**“Tezaver-Mac Offline Lab v1.0” fazı resmi olarak mühürlenmiş sayılır.** 🟢
