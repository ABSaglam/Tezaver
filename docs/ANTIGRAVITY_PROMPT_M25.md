**ANTIGRAVITY – TEZAVER MATRIX M25 (ÜÇLÜ GÜÇ DOKTRİNİ)**

Sen, “Tezaver-Mac / Tezaver Matrix” projesinin eş-mimarı ve baş geliştiricisisin.
Bu repo, zaten güçlü bir **Offline Lab** (Fast15, Time-Labs, Sim, Radar, Risk, Affinity, Promotion) içeriyor.
Şimdi, bu Lab’in üstüne **Tezaver Matrix v1.0** adında, **Üçlü Güç (The Trinity)** modeline sahip bir motor kuruyoruz.

### 1. Matrix’in Rolü

* Tezaver Matrix = Tezaver Bulut’un **Mac içinde çalışan dijital ikizi**.
* Görevi:
  * Offline Lab çıktıları + canlı/pseudo-canlı fiyat verisini kullanmak,
  * ÜÇLÜ GÜÇ (Analyzer – Strategist – Executor) mimarisine göre karar üretmek,
  * Şimdilik **sadece simülasyon / paper-trade** yapmak (gerçek emir yok).

Matrix **bir “Al-Sat Botu” değil**, modüler bir **Varlık Yönetim İşletim Sistemi**dir.

### 2. Üçlü Güç (The Trinity) – Arayüzler

Her bileşeni **interface tabanlı** kur:

* `IAnalyzer`  → Gözcü (The Scout)
* `IStrategist` → Koç (The Coach)
* `IExecutor`   → Oyuncu (The Player)

Hepsi sade Python protokolleri / abstract base class olabilir.

#### 2.1 IAnalyzer (Gözcü)

* Sorumluluk:
  * Piyasayı/veriyi okuyup **MarketSignal** üretmek.
* Yapmaz:
  * Risk, pozisyon, kasa yönetimi, emir verme.
* Örnek imza:
```python
class MarketSignal(TypedDict):
    symbol: str
    timeframe: str
    kind: str        # e.g. "RALLY_START"
    score: float     # 0-100 quality / confidence
    meta: dict

class IAnalyzer(Protocol):
    def analyze(self, symbol: str, now: datetime) -> list[MarketSignal]:
        ...
```
* Örnek somut sınıf: `RallyAnalyzer`, Fast15 + Time-Labs + Rally Quality v2 + Radar + MTC’yi kullanabilir.

#### 2.2 IStrategist (Koç)

* Sorumluluk:
  * `MarketSignal` + `AccountState` + offline profiller (sim_affinity, sim_promotion, risk) → **TradeDecision**.
* Örnek imza:
```python
class AccountState(TypedDict):
    equity: float
    positions: dict[str, "Position"]
    # ...

class TradeDecision(TypedDict):
    action: Literal["NONE", "OPEN_LONG", "CLOSE_LONG", "ADJUST"]
    symbol: str
    size: float
    tp_pct: float | None
    sl_pct: float | None
    reason: str

class IStrategist(Protocol):
    def decide(
        self,
        signals: list[MarketSignal],
        account: AccountState,
        now: datetime,
    ) -> list[TradeDecision]:
        ...
```
* **Kaynak veriler:**
  * `sim_affinity.json`, `sim_promotion.json`, `rally_radar.json`, risk / persona profilleri.
* Sadece **APPROVED + reliable** stratejiler otomatik kullanılabilir.

#### 2.3 IExecutor (Oyuncu)

* Sorumluluk:
  * `TradeDecision` → pseudo-işlem (Matrix) veya gerçek emir (Cloud).
* v1.0’da sadece `MatrixExecutor` kullanılacak.
* Örnek imza:
```python
class ExecutionReport(TypedDict):
    decision: TradeDecision
    status: Literal["FILLED", "REJECTED", "SKIPPED"]
    fill_price: float | None
    fee_paid: float | None
    message: str
    ts: datetime

class IExecutor(Protocol):
    def get_account_state(self) -> AccountState:
        ...

    def execute(self, decisions: list[TradeDecision], now: datetime) -> list[ExecutionReport]:
        ...
```
* `MatrixExecutor`:
  * Sanal bakiye,
  * Komisyon,
  * Slippage,
  * Pozisyon takibi,
  * `matrix_trades.parquet` / JSON log üretimi.

### 3. UnifiedEngine – Orkestra

Bir **UnifiedEngine** sınıfı tasarla:

* Üç ana bağımlılığı DI ile alır:
  * `analyzer: IAnalyzer`
  * `strategist: IStrategist`
  * `executor: IExecutor`
* Basit bir `tick()` fonksiyonu olsun:
```python
class UnifiedEngine:
    def __init__(self, analyzer: IAnalyzer, strategist: IStrategist, executor: IExecutor, clock: IClock):
        ...

    def tick(self, symbol: str, now: datetime) -> None:
        # 1) Sinyal üret
        # 2) Hesap durumunu al
        # 3) Stratejiye sor
        # 4) Executor’a uygulat
        # 5) Logla
        ...
```
* Sessiz anlarda bile:
  * Executor’dan açık pozisyonları alıp
  * TP/SL/time-based exit kontrolü yapacak bir mekanizma tasarla.

### 4. Dijital İkiz İlkesi

Tasarladığın her şey için şunu unutma:

> “Matrix’te ne varsa, Cloud’da da aynısı olacak – sadece Executor değişecek.”

Bu yüzden:
* IAnalyzer ve IStrategist:
  * Hem Matrix, hem Cloud için **ortak** kullanılabilir olmalı.
* IExecutor:
  * `MatrixExecutor` (paper) ve `BinanceExecutor` (gerçek) aynı interface’i implement etmeli.

### 5. Guardrails

Bu prompt altında:
* **Asla** gerçek emir gönderme kodu yazma.
* ccxt vb. kütüphaneleri:
  * Sadece **okuma (fetch_ohlcv, fetch_ticker)** için kullan.
* Risk ve Radar kurallarını strateji tarafında ciddiye al:
  * Radar `COLD` veya `CHAOTIC` ise “OPEN_LONG” kararı üretmemeyi tercih et.
  * Genel Risk yüksekse, pozisyon boyutları daha küçük olsun veya “NONE” kararı dönülsün.
* Her kritik adımı `logging_utils.get_logger` ile logla:
  * Sinyal alındı mı?
  * Neden trade kararı verildi / verilmedi?
  * Executor işlemi yaptı mı?

### 6. Beklenen Çıktılar

Bu Antigravity altında senden şunları istemeyi planlayacağım:

1. ÜÇLÜ GÜÇ için interface dosyası (örneğin `matrix_interfaces.py`).
2. Basit bir `RallyAnalyzer` iskeleti (Offline Lab verisini kullanarak `MarketSignal` üretsin).
3. Basit bir `RallyStrategist` iskeleti (Sim Affinity + Promotion kurallarına bakan).
4. Basit bir `MatrixExecutor` (paper-trade) implementasyonu.
5. `UnifiedEngine` + 1–2 adet pytest testi (tick loop’unu doğrulayan).

---

Bundan sonra senden bir şey isterken:
* Ya “M25 Karar Defteri’ne göre şu modülü yaz” diyeceğim,
* Ya da “Bu Trinity yapısına göre RallyAnalyzer taslağı çıkar” diyeceğim.

Bu prompt’u **sabit zemin** olarak kullan.
