# ⚔️ ANTIGRAVITY PROMPT – WAR GAME v1 (Tek Cephe Tatbikatı)

**Context:**
* **Proje:** Tezaver-Mac / M25 Matrix.
* **Durum:** M25.4 (Guardrail Fusion) tamamlandı. Sistem teknik olarak çalışıyor.
* **Hedef:** Matrix'in "davranışsal" testini yapmak. Yazılım hatası değil, "Stratejik Tutarlılık" arıyoruz.

---

### Görev 1 – War Game Scripti (`verify_wargame_v1.py`)

Bir python scripti oluştur. Bu script `verify_fleet.py`ye benzer ama şunları yapar:

1.  **Hedef:** Tek bir sembol (Örn: `BTCUSDT` veya parametrik).
2.  **Zaman:** Son 3000 Bar (yaklaşık 4 ay h1) veya geniş bir dilim.
3.  **Intelligence:**
    *   Gerçek `data/coin_profiles/{SYMBOL}/` verilerini kullanmalı.
    *   Eğer yoksa, script başında **otomatik mock** oluşturmalı (ama kullanıcıya "MOCK KULLANIYORUM" diye bağırmalı).
4.  **Raporlama:**
    *   Konsola sadece basit print yetmez.
    *   **Detaylı Savaş Günlüğü (Log) Dosyası** oluşturmalı: `wargame_btc_log.txt`.
    *   Her işlem için:
        *   `[SIGNAL] RALLY_START Score:85 Status:HOT Promo:APPROVED -> DECISION: BUY`
        *   `[GUARDRAIL] REJECTED (Reason: COLD Env)`
    *   Sonuçta:
        *   Toplam Trade Sayısı
        *   Guardrail Tarafından Engellenen Fırsat Sayısı
        *   Net PnL

### Görev 2 – Analiz Modu (Optional UI)

Eğer mümkünse, bu scriptin çıkardığı `wargame_btc_log.txt` veya benzeri bir özet veriyi ekrana bas.

### Beklenen Çıktı

Script çalıştırıldığında şu soruları cevaplamalıyım:
1.  Matrix, Lab'ın "Aferin" dediği yerlerde işleme girdi mi?
2.  Matrix, Lab'ın "Uzak dur" dediği (COLD) yerlerde gerçekten durdu mu?

---

### Teknik Detaylar

*   `MultiSymbolEngine` kullan (tek slotlu olsa bile, production motoru bu).
*   `Analyzer`: `RallyAnalyzer` (Threshold ayarlanabilir olsun, default 0.01 / %1).
*   `Strategist`: `RallyStrategist`.
*   `Guardrail`: `GuardrailController` (Intelligence yüklü).

**Komutan Notu:**
Bu bir "Unit Test" değildir. Assertion ("hata ver") içermez. Bu bir "Gözlem" aracıdır. Sonucunda "Evet, motor akıllı davranıyor" demeliyiz.
