# Tezaver-Mac REV.01 – Offline Lab & UI Re-Alignment Raporu

## 1. Özet

- **Tarih:** 08 Aralık 2025
- **Uygulayan:** Antigravity / AI IDE
- **Amaç:** Mac (Offline Lab) mimarisini dokümantasyonda anlatıldığı hale getirmek, eksik UI bileşenlerini (Sim Lab, Risk, vb.) geri getirmek ve sistem bütünlüğünü sağlamak.

## 2. Başlangıç Durumu (Ne Bulundu?)

### 2.1. Eksik / Bozuk Modüller

- **Sim Lab Sekmesi (UI):** `sim_lab_tab.py` dosyası mevcut olmasına rağmen `main_panel.py` naviasyonundan çıkarılmıştı. Kullanıcı erişemiyordu.
- **Yükseliş Lab (UI):** Sadece tek bir görünüm vardı. Fast15, 1h ve 4h Time-Labs sekmeleri ayrıştırılmamıştı.
- **Risk Sekmesi (UI):** Eksik veya eski versiyonda kalmıştı. Yeni Volatilite/Fakeout/Strateji kart yapısı yoktu.
- **Offline Maintenance (Sidebar):** Sidebar'da manuel bakım komutları (Full Maintenance, Fast15 Scan vb.) eksikti.

### 2.2. Mevcut Olanlar (FAZ A Onayı)
- Core config, logging ve system state modülleri sağlıklı.
- Rally motorları (`fast15_rally_scanner`, `time_labs_scanner`) ve `rally_radar_engine` dosya sisteminde mevcuttu.
- `sim_engine`, `sim_presets` gibi simülasyon mantık dosyaları mevcuttu.

## 3. Yapılan Değişiklikler

### 3.1. Dosya Bazlı Değişiklik Listesi

- `src/tezaver/ui/main_panel.py`:
  - **Sim Lab** sekmesi tekrar eklendi.
  - **Bilgelik** sekmesine `explanation_cards` entegrasyonu doğrulandı.
  - **Yükseliş Lab** sekmesi alt sekmelere (Fast15, 1h, 4h) bölündü.
  - **Risk** sekmesi `risk_cards.py` kullanacak şekilde bağlandı.
  - **Bulut Export** sekmesine "Sözlü Özet" eklendi.
  - **Sidebar**: "Offline Lab Bakımı" bölümü eklendi (Full Bakım, Fast15, 1H/4H Lab, Radar Update butonları).

- `src/tezaver/ui/time_labs_tab.py`:
  - 15m, 1h ve 4h zaman dilimlerini destekleyecek şekilde güncellendi.
  - Rally Radar / Özeti gösterecek fonksiyonlar eklendi.

- `src/tezaver/ui/fast15_lab_tab.py`:
  - Fast15'e özel "Hızlı Yükseliş" metriklerini gösterecek şekilde UI düzenlendi.

- `src/tezaver/ui/sim_lab_tab.py`:
  - Preset seçimi,scoreboard entegrasyonu ve manuel test ekranı doğrulandı.

## 4. Yeni / Geri Kazanılan Özellikler

- **Sim Lab:**
  - Artık kullanıcılar `FAST15`, `H1_SWING` gibi preset'leri seçip geçmiş veriler üzerinde test edebiliyor.
  - "Tüm Presetleri Çalıştır" butonu ile en uyumlu stratejiyi (Affinity) bulabiliyor.

- **Yükseliş Lab:**
  - Fast15 (15dk), 1 Saat ve 4 Saat rallileri ayrı ayrı incelenebiliyor.
  - Her bir ralli için "Kalite Puanı", "Şekil" (Clean/Spike) ve "Multi-TF Context" detayları görülebiliyor.

- **Bilgelik (Explanation Cards):**
  - Coin karakteri, oynaklık, tetikler ve strateji uyumu artık **Türkçe paragraflar** halinde okunabiliyor.

- **Risk Yönetimi:**
  - Fiyat/Oynaklık (ATR), Şok/Fakeout (Betrayal) ve Strateji Riski (Drawdown) üç ayrı kartta sunuluyor.

- **Operasyonel Kontrol:**
  - Sidebar üzerinden terminale gitmeden "Full Bakım" veya "Fast15 Tara" komutları verilebiliyor.

## 5. Test Sonuçları

- **Manuel Smoke Test:**
  - `streamlit` arayüzü başarıyla açıldı.
  - Sekmeler arası geçiş sorunsuz.
  - Sim Lab backtest butonu yanıt veriyor.
  - Veri olmayan sekmelerde "Veri yok" uyarıları düzgün çıkıyor.

## 6. Bilinen Kısıtlar / Sonraki Adımlar

- **Veri Gereksinimi:** Bazı sekmeler (özellikle Rally Radar ve Sim Affinity) tam dolu görünmek için `run_offline_maintenance.py` komutunun en az bir kez **full** modda çalıştırılmasını ve yeterli geçmiş verinin indirilmiş olmasını gerektirir.
- **Öneri:** Kullanıcıya sistemi ilk açtığında Sidebar'dan "🚀 Full Lab Bakımı" butonuna basması önerilir.

---
**REV.01 Tamamlandı.**
