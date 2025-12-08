# Matrix Operator Flow v1 (M25 Kullanım Kılavuzu)

Bu belge, Tezaver Matrix operatörünün günlük rutini, açılış/kapanış ritüelleri ve müdahale prosedürlerini tanımlar.

---

## 📅 Günlük Rutin (Daily Routine)

### 1. Sabah: Lab Bakımı (Offline Lab Maintenance)
Makineyi çalıştırmadan önce yağını suyunu kontrol et.

*   **Adım 1:** Terminali aç ve proje dizinine git.
*   **Adım 2:** `streamlit run src/tezaver/ui/main_panel.py` ile paneli başlat.
*   **Adım 3:** **"Sistem Sağlığı & Bakım"** sekmesine git.
    *   `Veri Güncelleme Servisi` > **"Tüm Coinleri Güncelle (1h)"** butonuna bas.
    *   *Neden?* Matrix'in Gözcüsü (Analyzer) en taze veriye ihtiyaç duyar.
*   **Adım 4:** **"Radar & Sinyal Tarama"** sekmesine git.
    *   **"Hızlı Tarama (Fast15)"** çalıştır.
    *   Hangi coinler "Rally" modunda? Not al.

### 2. Öğle: Matrix'i Başlat (Matrix Operations)
Motoru ateşle ve simülasyonu başlat.

*   **Adım 1:** **"Tezaver Matrix (M25)"** sayfasına (Bulut/Cloud ikonu) git.
*   **Adım 2:** Modu Seç: **"🌍 Matrix (Global General)"**.
*   **Adım 3:** Coin Sepetini Seç:
    *   Sabah taramasında dikkatini çeken veya sabit listen (BTC, ETH, SOL) seç.
*   **Adım 4:** Parametreleri Ayarla:
    *   Global Kasa: `$50,000` (Önerilen)
    *   Global Tetikleme Eşiği: `%2.0` (Düşük volatilite için %1.5, Yüksek için %3.0)
*   **Adım 5:** **"Dünya Savaşı'nı Başlat"** butonuna bas.
*   **Adım 6:** **İzleme:**
    *   Log ekranını takip et.
    *   Yeşil `ALIM` ve Kırmızı `SATIM` emojilerini gözle.
    *   Paneldeki "Global Kasa" değerindeki yeşil/kırmızı değişimi izle.

### 3. Akşam: Kapanış & Rapor (Closing & Reporting)
Günü değerlendir ve sistemi kapat.

*   **Adım 1:** Simülasyon bittiğinde çıkan **"Savaş Raporu"**nu incele.
    *   Kar/Zarar durumu ne?
    *   Kaç işlem yapıldı?
*   **Adım 2:** Kritik olay varsa (beklenmedik büyük zarar/kar), logları kopyala ve analiz et.
*   **Adım 3:** Sistemi kapat (Ctrl+C).

---

## 🚨 Acil Durum Müdahalesi (Red Alert)

Eğer Matrix simülasyonu sırasında mantıksız işlemler (arka arkaya 10 zarar, tüm kasanın bir kerede erimesi vb.) görürsen:

1.  **DURDUR:** Tarayıcı sekmesini kapat veya terminalden `Ctrl+C` yap.
2.  **KAYIT:** `verify_m25_matrix.py` dosyasını çalıştırarak çekirdek motorun sağlamlığını doğrula.
3.  **HATA RAPORU:** Eğer doğrulama betiği de hata veriyorsa, sorunu `docs/M25_INCIDENT_LOG.md` dosyasına işle.

---

## 📜 Yetki Matrisi (Role Matrix)

| Rol | Görev | Yetki |
| :--- | :--- | :--- |
| **Operatör (Siz)** | Sistemi başlatır, izler, raporlar. | Parametre ayarı (Threshold, Kasa). |
| **Gözcü (Analyzer)** | Sinyal üretir. | Sadece öneri sunar. |
| **Koç (Strategist)** | Karar verir. | İşlem açma/kapama yetkisi tamdır. |
| **Oyuncu (Executor)** | İşlemi yapar. | Sorgulama yetkisi yoktur. |
