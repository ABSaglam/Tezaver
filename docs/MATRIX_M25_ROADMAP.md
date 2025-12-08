# Tezaver Matrix M25 Roadmap (Yol Haritası)

Bu yol haritası, mevcut Tezaver yapısını **M25 Üçlü Güç Doktrini**'ne tam uyumlu hale getirmeyi hedefler.

## Faz 1: Temel Arayüzler ve Protokoller (Foundation)
*   [ ] **Interface Standardizasyonu:** Mevcut `interfaces.py` dosyasını `ANTIGRAVITY_PROMPT_M25.md` içinde belirtilen TypedDict ve Protocol yapısına göre güncelle/rewrite et.
    *   `MarketSignal` (TypedDict)
    *   `AccountState` (TypedDict)
    *   `TradeDecision` (TypedDict)
    *   `ExecutionReport` (TypedDict)
    *   `IAnalyzer`, `IStrategist`, `IExecutor` (Protocols)

## Faz 2: Gözcü (The Scout) Entegrasyonu
*   [ ] **RallyAnalyzer Refactor:**
    *   Mevcut `RallyAnalyzer` sınıfını yeni `IAnalyzer` protokolüne uydur.
    *   `Fast15` ve `TimeLabs` verilerini kullanarak `MarketSignal` üretecek şekilde güncelle.
    *   `RallyQuality` ve `Radar` filtrelerini buraya entegre et (veya Analyzer içinde alt modül olarak çağır).

## Faz 3: Koç (The Coach) ve Strateji Zekası
*   [ ] **RallyStrategist Refactor:**
    *   Mevcut `RallyStrategist` sınıfını yeni `IStrategist` protokolüne uydur.
    *   `decision` mantığını `sim_affinity.json` ve `sim_promotion.json` dosyalarını okuyacak şekilde geliştir.
    *   Radar durumu (COLD/CHAOTIC) kontrolü ekle (Guardrails).
    *   Risk yönetimi (TP/SL) mantığını `TradeDecision` yapısına uygun hale getir.

## Faz 4: Oyuncu (The Player) ve İcra
*   [ ] **MatrixExecutor Refactor:**
    *   Mevcut `MatrixExecutor` sınıfını yeni `IExecutor` protokolüne uydur.
    *   Emir tiplerini (`OPEN_LONG`, `CLOSE_LONG` vb.) `TradeDecision` içindeki enum yapısına göre işle.
    *   İşlem loglarını `matrix_trades.parquet` formatında saklama yeteneği ekle.

## Faz 5: Orkestra (UnifiedEngine) ve Test
*   [ ] **UnifiedEngine Finalizasyonu:**
    *   `tick()` döngüsünü yeni protokollere göre güncelle.
    *   "Sessiz An" (Idle Tick) kontrolünü (TP/SL check) yeni `IStrategist` yapısıyla test et.
*   [ ] **Unit Testler:**
    *   `tests/matrix/test_trinity.py` oluşturarak Analyzer -> Strategist -> Executor akışını mock nesnelerle test et.

## Faz 6: UI Entegrasyonu
*   [ ] **Matrix Dashboard Güncellemesi:**
    *   `cloud_page.py` arayüzünü yeni `UnifiedEngine` ve veri yapılarına göre (ExecutionReport formatı değişeceği için) güncelle.
    *   Log ekranını yeni formata uygun hale getir.

---
**Önemli Not:** Bu geçiş aşamalı olacaktır. Önce Interface'ler tanımlanacak, sonra modüller tek tek yeni yapıya taşınacaktır.
