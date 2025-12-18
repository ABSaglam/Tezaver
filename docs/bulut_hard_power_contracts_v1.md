# Bulut Hard Power Contracts v1

Bu doküman, Tezaver Bulut sisteminin **asla bozulmayacak** (hard-power) çalışma ve güvenlik kurallarını tanımlar. Bu kontratlar, sistemin deterministik, güvenli ve doğrulanabilir çalışmasının temel taşıdır.

Her kontrat için `src/tezaver/bulut/tests/test_contracts_v1.py` dosyasında kanıt testleri (proof tests) bulunmaktadır.

## Execution & State Contracts

### C1) Closed-Bar Only Execution
*   **Amaç:** Backtest ve Live paritesini korumak. Sinyaller sadece bar kapandıktan sonra üretilmeli.
*   **Kural:** `ON_CLOSED_BAR` dışı bir policy tespit edilirse veya bar henüz kapanmamışsa, execution planı üretilmesi **BLOKE** edilir.
*   **İhlal Davranışı:** `Executor` sessizce `SKIP` döner veya `BLOCK` loglar.
*   **Telemetry:** `EXECUTION_SKIPPED` (Reason: `POLICY_MISMATCH` or `BAR_NOT_CLOSED`)
*   **Test:** `test_c1_closed_bar_only_enforcement`

### C2) Exactly-Once Execution
*   **Amaç:** Aynı sinyalin veya planın mükerrer (double-spend) çalışmasını önlemek.
*   **Kural:** Bir `plan_id` veya `signal_id` için `EXECUTED` durumu bir kez kaydedildikten sonra, tekrar eden istekler reddedilir.
*   **İhlal Davranışı:** `IdempotencyCheck` başarısız olur, işlem reddedilir.
*   **Telemetry:** `DUPLICATE_EXECUTION_ATTEMPT`
*   **Test:** `test_c2_exactly_once_lock`

### C3) State Reducer Deduplication
*   **Amaç:** Event sourcing yapısında aynı event'in state'i bozmasını önlemek.
*   **Kural:** `StateReducer`, `applied_event_ids` setinde olan bir `event_id` gelirse değişikliği uygulamaz.
*   **İhlal Davranışı:** Event yutulur (ignored), state değişmez.
*   **Telemetry:** `EVENT_DUPLICATE_IGNORED`
*   **Test:** `test_c3_state_reducer_dedup`

### C4) Out-of-Order Protection
*   **Amaç:** Geç gelen eventlerin, güncel state'i (örn. pozisyon bilgisi) ezmesini engellemek.
*   **Kural:** Event timestamp'i, state'in `last_updated_ts` değerinden eskiyse reddedilir.
*   **İhlal Davranışı:** Event yutulur (ignored).
*   **Telemetry:** `EVENT_OUT_OF_ORDER`
*   **Test:** `test_c4_out_of_order_protection`

## Safety & Governance Contracts

### C5) Time Sync Unlock
*   **Amaç:** Sunucu saatinin borsa ile senkronize olduğundan emin olmak (timestamp hatalarını önlemek).
*   **Kural:** `TimeSync` servisi `healthy=True` (offset < threshold) vermiyorsa **HİÇBİR** execution yapılamaz.
*   **İhlal Davranışı:** `Executor` veya `Scheduler` seviyesinde `ABORT` / `BLOCK`.
*   **Telemetry:** `EXECUTION_BLOCKED_TIMESYNC`
*   **Test:** `test_c5_time_sync_unhealthy_blocks_execution`

### C6) Exchange Info Filters Check
*   **Amaç:** Borsanın LOT_SIZE, PRICE_FILTER gibi kurallarına uymayan emir göndermemek.
*   **Kural:** `ExchangeInfoCache` verisi bayat veya eksikse, emir hesaplama/gönderme işlemi yapılamaz.
*   **İhlal Davranışı:** `QtyCalc` veya `Executor` hata fırlatır (`FILTERS_MISSING`).
*   **Telemetry:** `EXECUTION_ERROR_MISSING_FILTERS`
*   **Test:** `test_c6_exchange_info_missing_blocks`

### C7) Mainnet Launch Gate (Fail-Closed)
*   **Amaç:** Gerçek para (REAL_MAINNET) ile işlem yaparken maksimum güvenlik.
*   **Kural:**
    1.  Mode `REAL_MAINNET` ve `ARMED` ise.
    2.  `Allowlist` boş veya symbol listede yoksa -> **BLOCK**.
    3.  `LaunchChecklist` (pre-flight checks) FAIL ise -> **BLOCK**.
    4.  Sistem `Constitution` (Anayasa) veya `Config` drift tespit ederse -> **BLOCK**.
*   **İhlal Davranışı:** Emir gönderilmez, `SAFETY_BLOCK` fırlatılır.
*   **Telemetry:** `MAINNET_GATE_BLOCK`
*   **Test:** `test_c7_mainnet_launch_gate_fail_closed`

### C8) Portfolio Risk Hard Stops
*   **Amaç:** Batış riskini (Ruin) önlemek.
*   **Kural:**
    1.  **Daily Loss Guard:** Günlük kümülatif PnL <= `-limit` ise yeni girişler **HALT**.
    2.  **Cooldown:** Stop-loss sonrası `N` dakika trade yasak.
    3.  **Group Caps:** Aynı gruptaki (örn. 'Layer1') açık pozisyon sayısı >= `Cap` ise yeni giriş yasak.
*   **İhlal Davranışı:** `RiskManager` -> `DENY`.
*   **Telemetry:** `RISK_RULE_DENY`
*   **Test:** `test_c8_portfolio_risk_hard_stops`

### C9) Rate Limit Governor
*   **Amaç:** Borsa API limitlerini aşarak banlanmayı önlemek.
*   **Kural:** Dakikalık veya saniyelik emir bütçesi (budget) yoksa işlem kuyrukta bekler veya reddedilir. Piyasa oynaklığı (market pressure) bu limiti aşamaz.
*   **İhlal Davranışı:** `Governor` -> `DENY` / `DELAY`.
*   **Telemetry:** `RATE_LIMIT_THROTTLED`
*   **Test:** `test_c9_rate_limit_governor_basic`
