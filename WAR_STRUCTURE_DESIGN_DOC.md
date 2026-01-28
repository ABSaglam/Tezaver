tek tek # ⚔️ SAHA SAVAŞ MİMARİSİ: "CENGAVER DOKTRİNİ" (ASM v6)
**Doktrin Adı:** Cengaver (The Warrior)
**Amaç:** Statik potansiyeli (Ayaş Tüneli), dinamik kâra ve güvenliğe (ASM v6) dönüştürmek.
**Motto:** "En iyi general bile fırtınada savaşa asker sürmez."

Bu doküman, Ayaş Tüneli'nden çıkan "Seçilmiş Sinyalleri" sahada yönetecek olan **Otonom Saha Komutanı** yapısının tasarımını içerir.

---

## 1. FELSEFE: ISTİHBARAT vs OPERASYON

Sistemi iki ana ve birbirinden bağımsız güce ayırıyoruz:

1.  **İSTİHBARAT BİRİMİ (Ayaş Tüneli - MİT):** 
    *   **Görevi:** Düşmanı değil, "Fırsatı" tespit etmek.
    *   **Çıktısı:** "Bugün şu 5 koinin DNA'sı saldırmaya müsait." (Potansiyel Listesi)
    *   **Karakteri:** Statik, Analitik, Geçmişe Bakan.
    *   **Durumu:** Mühürlendi ve Kilitlendi.

2.  **ÖZEL KUVVETLER (ASM v6 - Bordo Bereliler):**
    *   **Görevi:** İstihbaratın verdiği hedefe *ne zaman* ve *nasıl* gireceğine karar vermek.
    *   **Çıktısı:** BUY / SELL / WAIT emirleri.
    *   **Karakteri:** Dinamik, Refleksif, An'a Bakan.
    *   **Durumu:** İNŞA EDİLİYOR.

---

## 2. SAHA MİMARİSİ: ÜÇ KATMANLI KOMUTA

Sinyal Tünel'den çıktığı an, doğrudan "Alım" yapılmaz. Sinyal, 3 aşamalı bir güvenlik/onay zincirine (Chain of Command) girer.

### 🛡️ KATMAN 1: "MUHAFIZ" (MARKET GUARD)
**Görevi:** Kapıyı tutan nöbetçi. Dışarıdaki havayı (Piyasa Modu) koklar.

*   **Sorgusu:** "Şu an savaşmak için uygun bir hava var mı?"
*   **Sensörleri:**
    1.  **BTC Yerçekimi:** BTC anlık olarak çöküyor mu? (15m Mum > %1 Düşüş VARSA DUR).
    2.  **Trend Rüzgarı:** BTC 4 Saatlik EMA21'in altında mı? (Altındaysa DEFANSİF ol, sadece çok güçlüleri al).
    3.  **Hacim Oksijeni:** Piyasada genel hacim var mı? (Total Volume 24h > Ortalama).

*   **Karar:** Eğer hava "Toksik" ise, içerideki Cengaver (Sinyal) ne kadar güçlü olursa olsun **KAPI AÇILMAZ.**

---

### 🔭 KATMAN 2: "GÖZCÜ" (MICRO-CONFIRMATION)
**Görevi:** Hedef koinin kendisine bakar. Tünel "bu koin gitmeli" dedi ama koin gerçekten gidiyor mu?

*   **Sorgusu:** "Hareket başladı mı yoksa hala uyuyor mu?"
*   **Mekanizması (15 Dakikalık Keskin Nişancı):**
    1.  **Ignition (Ateşleme):** 15 dakikalık mumda aniden hacimli bir alım geldi mi? (Vol > 2x Avg).
    2.  **Breakout (Yarma):** Fiyat, sabahki açılış fiyatının ve EMA21'in üzerine attı mı?
    
*   **Karar:** Sadece "Ateşlemeyi" gördüğünde tetiği çeker. Ateşleme yoksa gün boyu o koini sadece izler, alım yapmaz.

---

### ⚔️ KATMAN 3: "KOMUTAN" (DYNAMIC EXECUTION)
**Görevi:** Pozisyona girdikten sonra savaşı yönetmek. (Trade Management).

*   **Stratejisi:** "Vur ve İlerle" (Hit & Run).
*   **Mekanizması:**
    1.  **Dinamik Stop:** Fiyat yükseldikçe stop seviyesini yukarı çeker (Trailing Stop). Asla kârı zarara döndürmez.
    2.  **Time-Based Exit (Zamanlı Çıkış):** Eğer 4 saat geçti ve koin hala %1 bile gitmediyse; "Bu asker yorgun" der ve pozisyonu kapatır. (Time Stop).
    3.  **Hedef:** İlk %5 kârda yarısını sat (Cebe at), gerisini "Ay'a kadar" (Moonbag) tut.

---

## 3. UYGULAMA PLANI (KODLAMA)

Bu yapıyı kurmak için şu modülleri yazacağız:

1.  **`MarketGuard.py`:** Binance'den BTC ve Global veriyi çekip "Hava Durumu Raporu" (0-100 Puan) üreten servis.
2.  **`SniperEntry.py`:** Tünel listesindeki koinleri 15 dakikalık periyotlarla tarayıp "Ateşleme Mumunu" arayan bot.
3.  **`WarRoom.py`:** Tüm bu trafiği yöneten ve simüle eden ana merkez.

### 🏁 HEDEF
Ayaş Tüneli'nin %100 dürüst listesini alıp, 18-21 Ocak'taki o "Kanlı Pazartesi"den **sıfır hasarla** veya **kârla** çıkmasını sağlamak.

Emrinizdeyim Komutanım! Başlayalım mı?
