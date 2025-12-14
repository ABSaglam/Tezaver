# Tezaver Matrix V2 – Karar Defteri v1 (Anayasa)

## 0. Amaç ve Tanım

**Matrix**, Tezaver ekosisteminde **canlı trade motorudur**.

- Coin Lab tarafında üretilen zekâyı alır
- Bu zekâyı **profil** halinde paketler (CoinPage V2)
- Önce **War Game** (geri test / laboratuvar savaşı) ortamında dener
- Gerekli koşulları sağlayan profilleri **LIVE** (gerçek zamanlı) ortama taşır
- Tüm süreci **guardrail** ve **risk kontratı** ile güvence altına alır

Hedef:  
> “Dünyanın en sade, ama en disiplinli trade motoru” olmak.  
Karmaşıklık Coin Lab’de kalır, Matrix’te **sadelik ve tutarlılık** şarttır.

---

## 1. Trinity – Çekirdek Motor

Matrix’in kalbi **Trinity Core**’dur:

1. **Analyzer (Gözcü)**
   - Piyasa verisini okur
   - Rally, trend, pattern vb. sinyaller üretir
   - Çıktısı: `MarketSignal` listesi

2. **Strategist (Koç)**
   - Sinyalleri ve hesap durumunu (equity, pozisyonlar) okur
   - “Trade aç / kapat / dokunma” kararı verir
   - Çıktısı: `TradeDecision`

3. **Executor (Oyuncu)**
   - Kararı uygular: pozisyon açma/kapama, TP/SL
   - War Game’de simülasyon, Live’da gerçek emir gönderir
   - Çıktısı: `ExecutionReport`

Bu üçlü, **tek bir UnifiedEngine** içinde bağlanır.  
Motorun içine strateji gömülmez; strateji **profiller** ve **config** ile dışarıdan gelir.

---

## 2. Coin Lab → Matrix Akışı

Matrix hiçbir şeyi kafasına göre icat etmez.  
**Tek bilgi kaynağı Coin Lab tarafındaki analizlerdir.**

Standart akış:

1. **Coin Lab – Coin Lab Pattern & Strategy**
   - Rally tarama, Silver/Gold/Bronze grade hesaplama
   - Story Card: rally öncesi hikâye (RSI, hacim, ATR, MTF durumları)
   - Strategy Card: giriş filtreleri + TP/SL/Horizon + ML filtreleri
   - ML dataset’ler: `rally_patterns_v1.parquet` vb.

2. **War Game – Matrix Wargame**
   - Pattern dataset üzerinden War Game senaryosu çalıştırılır
   - PnL, trade sayısı, max drawdown, risk sweep hesaplanır
   - Sonuçlar `ai_insights` altına yazılır

3. **CoinPage V2 – Matrix Coin Strategy Page**
   - Her coin için `matrix_coin_page_v2.json` oluşturulur
   - İçerik:
     - Timeframe bazında profiller
     - Her profil için:
       - `status` (APPROVED / EXPERIMENTAL / DISABLED)
       - `strategy_config_v1` (entry/ML/exit parametreleri)
       - `benchmark_v1` (War Game sonucu: pnl, trades)
       - `risk_contract_v1` (max_risk_per_trade + kaynak)

4. **Matrix Strategy Board**
   - Bütün CoinPage V2 dosyalarını okuyup tek tabloda gösterir
   - Hangi profil ne durumda, hangi risk ile LIVE olabilir, raporlar

5. **Matrix Live Autowire**
   - Strategy Board’dan **LIVE eligible** profilleri seçer
   - Her profile karşılık bir **Live Strategy Cell** oluşturur
   - Live Cluster, bu cell’lerden otomatik kurulur

Sonuç:  
Coin bazlı strateji → profil → war game → board → live zinciri **standarttır**.  
Yeni strateji eklemek için motoru değiştirmeye gerek yoktur.

---

## 3. Profil ve CoinPage V2 Standartları

Her coin için tek bir **CoinPage V2** vardır:

- Dosya: `data/coin_profiles/<SYMBOL>/matrix_coin_page_v2.json`
- Ana alanlar:
  - `version`: `"matrix_coin_page_v2"`
  - `symbol`: `"BTCUSDT"` vb.
  - `timeframes`: `"15m"`, `"1h"`, `"4h"` vb.
    - Her timeframe altında `profiles`:
      - `profile_id` (ör: `BTC_SILVER_15M_CORE_V1`)
      - `status`: `APPROVED` / `EXPERIMENTAL` / `DISABLED`
      - `strategy_config_v1`: giriş/çıkış ayarları
      - `benchmark_v1`: War Game sonuç özeti
      - `risk_contract_v1`: max_risk_per_trade ve notlar

**Tek gerçek kaynak**: CoinPage V2.  
Guardrail, War Game, Live, Live Autowire hepsi buradan okur.

---

## 4. War Game (Matrix Wargame)

War Game, Matrix’in **laboratuvar modu**dur.

- Veri kaynağı: ReplayDataFeed
  - Örneğin `rally_patterns_v1.parquet` dosyaları
- Hesap: In-memory WargameAccountStore
  - initial_capital = 100 gibi
- Motor: UnifiedEngine (Analyzer + Strategist + Executor)

War Game özellikleri:

- Risk sweep: farklı risk düzeylerinde 100 → X senaryoları
- Equity curve ve max drawdown hesaplaması
- Telemetry eventleri ve Matrix Diary kaydı
- Multiple coin + multi-profile deneyler (ör: Silver 15m BTC/ETH/SOL)

War Game’in amacı:

1. Stratejinin **temel karakterini** anlamak
2. PnL, trade sayısı, max DD, win rate gibi metrikleri ölçmek
3. CoinPage V2’deki `benchmark_v1` ve `risk_contract_v1` alanlarına veri sağlamak

War Game her zaman **Live’dan önce** gelir.

---

## 5. Risk Contract v1

Her profil için **Risk Kontratı** zorunludur:

- Kaynak: War Game sonuçları ve multi-coin özetleri
- Format (`risk_contract_v1`):
  - `profile_kind` (ör: `"silver_15m"`)
  - `status` (APPROVED / TODO / REVIEW)
  - `max_risk_per_trade` (ör: `0.01` = %1)
  - `source` (hangi özet dosyasından geldi)
  - `reference` (referans PnL, trade sayısı vb.)

**Kural:**

- LIVE ortamında,
  - Strategist’in istediği risk (`risk_per_trade_requested`)
  - Guardrail/Contract tarafından **max_risk_per_trade** ile **clamp** edilir.

Örnek:

- Strategist 100% risk istese bile
- Risk Contract `%1` diyorsa
- Etkili risk → `%1`

War Game’de iki mod vardır:

- `mode="contract"` → Risk Contract uygulanır
- `mode="experiment"` → Cap bypass edilir (deney için)

Live ortamında **her zaman** `contract` modu kullanılır.

---

## 6. Guardrail v2 – Profil ve Risk Bilincine Sahip Koruma

Guardrail v2, üç şeyi aynı anda kontrol eder:

1. **Profil Statüsü**
   - LIVE ortamında:
     - `APPROVED` → izin ver
     - `EXPERIMENTAL` → block
     - `DISABLED` → block
   - WARGAME ortamında:
     - Hepsi serbest (APPROVED/EXPERIMENTAL/DISABLED) → test serbestliği

2. **Risk Kontratı**
   - `risk_contract_v1.max_risk_per_trade` okunur
   - Trade kararı üzerindeki risk clamp edilir
   - Guardrail kararı içine `risk_contract_max` olarak eklenir

3. **Klasik Sınırlar (Guardrail v1)**
   - max_open_positions
   - max_loss_per_day vb. limitler
   - Bunlar profil-dışı, global güvenlik sınırlarıdır

Guardrail kararları, telemetry ve diary içinde net olarak log’lanır.

---

## 7. Live Matrix – Live Cluster ve Autowire

Live tarafı, **MatrixLiveCluster** ile temsil edilir:

- Her profil için bir **Live Strategy Cell**:
  - symbol + timeframe + profile_id
  - risk_mode (`contract` / `experiment`)
  - initial_capital
- LiveDataFeed: gerçek zamanlı veri
- LiveAccountStore: gerçek hesap veya paper-trade defteri
- UnifiedEngine: aynı Trinity motoru (Analyzer/Strategist/Executor)

**Autowire v1**:

- Strategy Board, CoinPage V2’lerden LIVE eligible profilleri listeler
- Autowire:
  - `status = APPROVED`
  - `risk_contract_v1.max_risk_per_trade` mevcut
- Bu profillerden otomatik Live cell listesi oluşturulur

Operator tek bakışta şunu görebilmelidir:

- Hangi coin, hangi timeframe, hangi profil LIVE’da
- Her profilde max risk kaç (%1, %2 vs.)

---

## 8. Telemetry & Matrix Diary

Her tick’te Matrix aşağıdaki event tiplerini üretir:

- `TICK_START` / `TICK_END`
- `SIGNAL`
- `DECISION`
- `GUARDRAIL_V2` / `GUARDRAIL_V1`
- `EXECUTION`
- `INFO`

Event’ler iki yerde kullanılır:

1. **WargameReport.events**
   - Analiz/delil için
2. **Matrix Diary v1**
   - İnsan gözüyle okunabilir “günlük” formatı
   - Örnek satır:
     - `TICK   7 | DECISION     | BTCUSDT 15m | action=OPEN_LONG, qty=1.0, tp=0.07, sl=0.02`

Prensip:  
> “Matrix ne yaptığını her zaman yazılı şekilde anlatmak zorunda.”

---

## 9. Matrix Operator Rolü

Matrix, bir “kara kutu” değildir.  
Operator (sen) için net görevler vardır:

1. Strategy Board’a bak:
   - Hangi profiller APPROVED / EXPERIMENTAL?
   - PnL, trade sayısı, max risk nedir?

2. Live Autowire çalıştır:
   - Board’dan LIVE eligible profilleri Live Cluster’a bağla

3. War Game’leri düzenli çalıştır:
   - Yeni verilerle silver/gold/bronze stratejileri tekrar test et
   - Benchmark ve risk kontratlarını güncelle

4. Matrix Diary’yi oku:
   - Garip hareket varsa (şüpheli trade, beklenmeyen davranış), önce diary’e bak

5. Değişiklik Disiplini:
   - Strateji parametresi değiştirmek = CoinPage V2 güncellemek
   - Direkt motor kodunda “hotfix” yapma, önce profil tarafını güncelle

---

## 10. Yol Haritası – Matrix V2 Sonrası

Matrix V2 ile çekirdek şu an **tamamlanmış** sayılır.  
İleride yapılacaklar:

- Silver dışı stratejiler (Gold/Bronze, başka pattern’ler)
- 1h / 4h Silver stratejilerinin Matrix tarafına genişlemesi
- Exchange entegrasyonu (gerçek emir)
- Sağlık kontrolleri ve alarm sistemi (latency, error rate, drop-out tespiti)

Ancak bu Anayasa şunu söyler:

> “Her şey CoinPage V2’den akar, War Game ile test edilir, Risk Contract ile sınırlandırılır ve Guardrail + Telemetry ile korunur.”

Bu disiplin bozulmadığı sürece Matrix büyüyebilir.
