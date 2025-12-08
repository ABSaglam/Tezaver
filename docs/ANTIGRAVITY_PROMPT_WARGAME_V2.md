# ANTIGRAVITY_PROMPT_WAR_GAME_V2_GUARDRAILS_ON

**Amaç:**
- Tezaver Matrix M25 motoru halihazırda çalışıyor (Analyzer + Strategist + Executor + UnifiedEngine + MultiSymbolEngine).
- Offline Lab (Offline Maintenance v1.0) zaten `rally_radar.json`, `sim_affinity.json` ve `sim_promotion.json` üretebiliyor.
- M25.4 “Guardrail Fusion” unit test seviyesinde çalışıyor (HOT+APPROVED -> allow, COLD/REJECTED -> block).
- Hedef: War Game v2 script’i koşturup, her potansiyel trade girişi için **Guardrail Decision Code** loglamak ve toplam PnL/Behavior sonucunu görmek.

Genel İlke:
- Analyzer sinyal üretir → **Guardrail Filtresi** (Offline Intelligence) → (ALLOW ise) Strategist → (BUY ise) Executor.
- Guardrail kararı, `GuardrailDecision` objesi ve `reason_code` ile loglanmalı.

---

## 1. Kod Organizasyonu

### 1.1. Guardrail Modülü Refactor (`src/tezaver/matrix/guardrail.py`)
Mevcut `GuardrailController`'ı War Game v2 için güçlendir.

- **`GuardrailProfile`'ı Genişlet:**
  Mevcut: env_status, promotion_status, affinity_score.
  Eklenecek:
  - `grade: Optional[str]`
  - `has_profiles: bool`

- **`GuardrailDecision` Dataclass'ı Oluştur:**
    ```python
    @dataclass
    class GuardrailDecision:
        allow: bool
        reason_code: str  # ALLOW / BLOCK_RADAR_COLD / ...
        details: dict     # extra info (env_state, status vs.)
    ```

- **`evaluate_open_long` Metodunu Güncelle:**
  Şu an sadece `bool` dönüyor. Bunu `GuardrailDecision` dönecek şekilde refactor et (veya yeni bir metod ekle `check_open_long_detailed`).
  Mevcut `can_open_new_long` bu yeni metodu çağırıp `.allow`'ı dönebilir (geriye uyumluluk için).

  **Karar Matrisi:**
    - `COLD` / `CHAOTIC` → `BLOCK_RADAR_COLD` / `BLOCK_RADAR_CHAOTIC`
    - `REJECTED` → `BLOCK_STRATEGY_REJECTED`
    - `CANDIDATE` → `BLOCK_STRATEGY_LOW_SCORE` (Strict Mod)
    - `APPROVED` + `HOT` → `ALLOW`
    - Profil Yok → `BLOCK_NO_PROFILE`

### 1.2. Entegrasyon (Logging)
`verify_wargame_v2.py` scriptinde, `GuardrailController`'ın döndürdüğü bu `reason_code`'u logla.
Bunun için:
- `MultiSymbolEngine.tick` içinde guardrail kontrolünü yaparken reason code'u **slot state'ine** kaydet.
- `SymbolSlot`'a `last_guardrail_decision: Optional[GuardrailDecision]` ekle.
- `verify_wargame_v2.py` tick loop'unda bu slotu okuyup logdosyasına yazsın.

---

## 2. War Game v2 Script (`verify_wargame_v2.py`)

- **Hedef:** Tek Sembol (BTCUSDT) veya Filo (BTC, ETH).
- **Süre:** 3000 Bar.
- **Intelligence:** Gerçek `data/` profilleri (yoksa MOCK oluştur ama logla).
- **Çıktı:** Konsol + `wargame_v2_log.txt`.

**Rapor Formatı:**
```text
Total Signals: 50
Blocked Signals: 35
  - BLOCK_RADAR_COLD: 20
  - BLOCK_STRATEGY_REJECTED: 10
  - BLOCK_NO_PROFILE: 5
Trades Opened: 15
Net PnL: +$1,200 (+12%)
Max Drawdown: -5%
```
**Analiz:**
Bu script sonunda, Guardrail'lerin "Ne kadar sıkı" olduğunu göreceğiz. Eğer PnL, War Game v1'e göre iyileşirse (veya DD düşerse), Guardrail Fusion başarılıdır.

---

## 3. Testler
- `tests/matrix/test_guardrail_logic.py`:
  - `COLD` -> Blocked
  - `REJECTED` -> Blocked
  - `HOT + APPROVED` -> Allowed
  - `NO FILE` -> Blocked

**Kısıtlar:**
- Mevcut `cloud_page.py` bozulmamalı (Controller API değişirse orayı da güncelle).
- `verify_fleet.py` bozulmamalı.
