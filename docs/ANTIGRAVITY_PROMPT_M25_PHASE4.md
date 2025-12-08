# 🧲 ANTIGRAVITY PROMPT – M25.4 Guardrail Fusion

**Context:**
* **Proje:** Tezaver-Mac / M25 Matrix.
* **Durum:** M25.3 Multi-Symbol Loop başarıyla çalışıyor ("Filo Komutanı").
* **Eksik:** `GuardrailController` şu anda dummy/hardcoded veri ("APPROVED", "HOT") ile çalışıyor.
* **Hedef:** Offline Lab'ın ürettiği gerçek zekayı (Sim Promotion, Rally Radar) Matrix'e entegre etmek.

---

### Görev 1 – Guardrail Veri Yükleyicileri (Intelligence Bridge)

1.  `src/tezaver/matrix/guardrail.py` dosyasını güncelle.
2.  Yeni metodlar ekle:
    *   `load_radar_intelligence(symbol: str) -> str`:
        *   `data/coin_profiles/{symbol}/rally_radar.json` dosyasını oku.
        *   `state` alanını döndür (HOT, COLD, etc.). Dosya yoksa "UNKNOWN".
    *   `load_promotion_intelligence(symbol: str) -> str`:
        *   `data/coin_profiles/{symbol}/sim_promotion.json` (veya `sim_affinity.json`) dosyasını oku.
        *   `status` alanını döndür (APPROVED, REJECTED). Dosya yoksa "UNKNOWN".

### Görev 2 – GuardrailController Entegrasyonu

1.  `GuardrailController.__init__` metodunu güncelle.
    *   Artık `symbol_data` dict'ini dışarıdan almak yerine, `symbols` listesi alıp, içeride **otomatik yükleme** yapmalı.
    *   `self.reload_intelligence()` gibi bir metodla tüm semboller için dosya okuma işlemini yapabilmeli.

### Görev 3 – UI Entegrasyonu (Cloud Page)

1.  `run_global_simulation` fonksiyonunda:
    *   `GuardrailController` başlatılırken manuel `SymbolGuardrailData` oluşturmayı bırak.
    *   Bunun yerine Controller'ın kendi loader'larını kullanmasını sağla.
    *   UI'daki "Filo Tablosu"na (Fleet Table) yeni sütunlar ekle:
        *   `Radar` (HOT/COLD ikonlu)
        *   `Status` (APPROVED/REJECTED ikonlu)
        *   `Gate` (OPEN/BLOCKED) -> `can_open_new_long` sonucunu göster.

### Görev 4 – Doğrulama (War Game)

1.  `verify_guardrail_fusion.py` scripti oluştur.
2.  Senaryo:
    *   **BTC:** Radar=HOT, Status=APPROVED -> İşlem açmalı.
    *   **XRP:** Radar=COLD (manuel dosya oluştur force et), Status=APPROVED -> **BLOKLANMALI**.
    *   **DOGE:** Radar=HOT, Status=REJECTED (manuel dosya) -> **BLOKLANMALI**.
3.  Scriptin sonunda Hangi coinlerin bloklandığını raporla.

---

### Beklenen Sonuç
Matrix artık "Körü körüne" her şeye saldırmaz. Sadece Lab'dan **ONAYLI** ve Radarı **SICAK** olan coinlere işlem açar. Bu, sermaye koruması için kritik bir adımdır.
