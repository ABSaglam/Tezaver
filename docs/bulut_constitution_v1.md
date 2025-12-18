# Bulut Anayasası (System Constitution v1)

## 1. Amaç ve Kapsam
Bu doküman, **Tezaver Bulut** sisteminin teknik sözleşmesi ve operasyonel rehberidir. Sistem, Binance Futures üzerinde çalışan, kendi kendine yeten, durum bilgili (stateful) ve olay güdümlü (event-driven) bir algoritmik ticaret motorudur.

**Temel Prensip:** "Safety First". Sistem, belirsizlik durumunda işlem yapmaz, hata durumunda durur (Fail Fast/Safe) ve doğrulanmamış hiçbir veriye güvenmez.

## 2. Çalışma Modları
Sistem `MODE` çevresel değişkeni ile yönetilir:

*   **REAL_TESTNET**: Binance Futures Testnet üzerinde çalışır.
    *   `EXECUTION_ENABLED`: Varsayılan True.
    *   Hata toleransı: Yüksek.
*   **PAPER**: Canlı veri (Mainnet) ile sanal bakiye (Paper) üzerinde çalışır.
    *   `EXECUTION_ENABLED`: False (Sanal simülasyon).
*   **REAL_MAINNET**: Canlı Binance Futures Mainnet.
    *   `EXECUTION_ENABLED`: Varsayılan False (Explicit enable gerekir).
    *   **Zorunluluklar**:
        *   `ARM_TOKEN`: Opsiyonel, kritik işlemler için.
        *   **Allowlist**: `data/bulut_rules/mainnet_allowlist.txt` dolu olmalıdır.
        *   **Launch Checklist**: Pre-flight kontrolleri (Time, Config Drift, Env) PASS dönmelidir.

## 3. Data Pipeline
Kesintisiz ve kaliteli veri akışı:
1.  **UniverseSource**: Sembol evrenini (örn. TOP 40) tanımlar.
2.  **Poller**: REST API üzerinden periyodik (örn. 5s) mum verisi çeker.
3.  **Bars15mStore**: 15 dakikalık mumları bellekte tutar ve validasyon yapar (%90+ doluluk).
4.  **ExchangeInfoCache**: Sembol kurallarını (hassasiyet, min/max lot) önbellekler (TTL: 1h).

## 4. Intelligence Pipeline
Ham veriden sinyal üretimi:
1.  **PatternPack v2**: Teknik analiz desenlerini (örn. BullFlag, DoubleBottom) tanır.
2.  **Scanner**: Bars15mStore üzerindeki her mum güncellemesinde desen tarar.
3.  **RankingSnapshot**: Tespit edilen geçerli desenleri ve skorlarını anlık olarak yayınlar.

## 5. Decision + Execution
Karar mekanizması ve emir yönetimi:
1.  **Decider**: Ranking + Risk kurallarına göre `TradeDecision` (ENTRY/EXIT/WAIT) üretir.
2.  **TradePlan**: Kararı somut bir plana (Lot size, SL/TP fiyatları) dönüştürür.
    *   Plan, `idempotency_key` ile tekilleştirilir.
3.  **Executor**: `TradePlan`'ı borsaya iletir.
    *   **Exactly-Once**: Her plan sadece bir kez denenir.
    *   **Protective Orders**: Pozisyon açıldıktan sonra SL ve TP emirleri (veya alarm bazlı kapatma) zorunludur.

## 6. Risk
Risk Yönetimi (Safety Guard) her işlemin önündeki son bariyerdir:
1.  **PortfolioRisk**:
    *   `max_total_notional_usdt`: Toplam açık pozisyon büyüklüğü.
    *   `daily_loss_limit`: Günlük maksimum zarar (Breaker Trip).
    *   `cooldown_minutes`: Zıt yönlü işlem arası bekleme süresi.
    *   `group_caps`: Aynı gruptaki (örn. L1, DeFi) maksimum eşzamanlı pozisyon sayısı.

## 7. Accounting
Finansal tutarlılık ve raporlama:
1.  **UserTrades**: WebSocket üzerinden gelen işlem (Fill) bildirimleri.
2.  **TradeAudit**: Kapanan pozisyonların Net PnL, Komisyon ve süre hesabını tutar.
3.  **Income Events**: Funding Fee ve diğer gelir/gider kalemlerini senkronize eder.
4.  **FX Conversion**: Komisyonlar (BNB) veya PnL (USDT dışı) için anlık kur dönüşümü yapar.
5.  **Total Daily PnL**: `SUM(TradeNetPnL) + SUM(IncomeEvents)`.

## 8. Event-driven State
Sistem durumu anlık olaylarla güncellenir:
1.  **USER_DATA Stream**: Borsa ile sürekli açık WebSocket bağlantısı.
    *   `ORDER_TRADE_UPDATE`: Emir durumu değişimleri.
    *   `ACCOUNT_UPDATE`: Bakiye ve pozisyon güncellemeleri.
2.  **StateReducer**: Gelen olayları işleyerek `BulutState`'i (Bellek içi pozisyonlar) günceller.
    *   **Dedup**: Tekrar eden olayları filtreler.
    *   **OOO (Out-of-Order)**: Sırasız gelen olayları (ts kontrolü) yönetir.

## 9. Ops (Operasyon)
Sistemin sağlığı ve sürekliliği:
1.  **Task Supervisor**: Kritik servisleri (Daemon, WS) sarmalar, izler ve çökme durumunda yeniden başlatır.
2.  **Env Doctor**: Başlangıçta ve periyodik olarak ortam sağlığını (DB, API, Time) kontrol eder.
3.  **Heartbeats**: Servislerin "yaşıyorum" sinyalleri.
4.  **Incident Bundle**: Hata anında tüm log, config ve DB durumunu paketleyip dışa aktarır.
5.  **Migrations**: DB şema değişikliklerini versiyonlar ve sıralı olarak uygular (v001 -> vXXX).
6.  **Config Snapshot**: Konfigürasyon değişikliklerini (Drift) takip eder ve hash'ler.

## 10. Nereden Ne Değişir
Konfigürasyon yönetimi:
*   **Env Vars (`.env`)**: Kritik altyapı ayarları (MODE, API_KEY, DB_PATH).
    *   `MAINNET_PILOT_MAX_TOTAL_NOTIONAL_USDT`: Pilot limiti (Varsayılan 50).
    *   `MAINNET_PILOT_HOURS`: Pilot süresi (Varsayılan 24).
*   **`data/bulut_rules/`**: İş mantığı kuralları.
    *   `mainnet_allowlist.txt`: Mainnet için izinli semboller.
    *   `groups.json`: Sembol grupları ve limitleri.
    *   `exit_profiles.json`: Çıkış senaryoları.

## 11. Mainnet Runbook
Canlı sisteme geçiş (Launch) prosedürü:

1.  **Clean State**: `data/bulut.db` yedeğini al ve (gerekirse) temizle.
2.  **Config Review**: `.env` dosyasında `MODE=REAL_MAINNET` ve `EXECUTION_ENABLED=True` ayarla.
3.  **Allowlist**: `data/bulut_rules/mainnet_allowlist.txt` içine sadece işlem yapılacak sembolleri (örn. BTCUSDT) ekle.
4.  **Limits**: `MAX_TOTAL_NOTIONAL` değerini güvenli bir başlangıç seviyesine (örn. 100 USDT) çek.
5.  **Migrations**: Sistemi başlat, loglardan `[Migrations] Executed` veya `Up to date` onayı gör.
6.  **Launch Checklist**: Dashboard üzerinden "Launch Checklist" panelini aç ve "Run Checklist" yap.
    *   Config Drift: Stable.
    *   Exchange Info: OK.
    *   User Data Stream: Connected.
    *   Allowlist: Found.
7.  **Pass**: Checklist sonucu yeşil (PASS) ise sistem hazırdır.
8.  **Arm**: (Opsiyonel) UI üzerinden veya API ile sistemi "ARMED" durumuna getir.
9.  **Pilot Phase**: İlk 24 saat boyunca `MAINNET_PILOT_MAX_TOTAL_NOTIONAL_USDT` (50 USDT) limitini aşma. Alarm veya beklenmeyen davranış varsa durdur. Ancak 24 saatlik temiz (clean) çalışma sonrası limiti artır.
10. **Monitoring**: Dashboard üzerinden Heartbeats, PnL ve Logs panellerini sürekli izle.

## 12. Intel Contract (v1)
Tezaver Mac -> Bulut zeka aktarımı sıkı kurallara tabidir:
1.  **Intel Bundle**: PatternPack (v2) + Metadata (Hash, Timestamp, Producer). deterministic ve imzalı olmalıdır.
2.  **Lifecycle**:
    *   **Incoming**: Mac'ten gelen ham paket. `validate` edilerek bütünlüğü doğrulanır.
    *   **Published**: Doğrulanmış ve `published` klasörüne alınmış paket. **Immutable** (değiştirilemez).
    *   **Active**: `active_pointer.json` ile işaret edilen, o an çalışan paket.
3.  **Mainnet Safety**: `REAL_MAINNET` modunda ve `ARMED` iken Intel değişikliği (Publish, Activate, Rollback) **BLOKLANIR**.
    *   Değişiklik için önce sistem `DISARM` edilmelidir.
    *   Bu kural `intel_edit_block_on_mainnet_armed` config ile yönetilir (Varsayılan: True).
