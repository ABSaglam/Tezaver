# ANTIGRAVITY | DNA MINING PROTOCOL V1 (DNA Madencilik Protokolü)

**Yürürlük Tarihi:** 28 Ocak 2026
**Statü:** TASLAK / ONAY BEKLİYOR
**Koruma Seviyesi:** KRİTİK (Golden Key bütünlüğü için esastır)

## 1. TEMEL İLKE: "KAPALI DEVRE DNA"
Mevcut `_key.json` dosyaları, sistemin "Bağışıklık Sistemi"dir. Rastgele veya otomatik süreçlerle bu dosyalara dışarıdan DNA eklenmesi **KESİNLİKLE YASAKTIR**.

Bir coin, ancak mevcut Golden DNA listesindeki bir anahtarla eşleşirse tünelden geçebilir. Eşleşmiyorsa, o günkü fırsatı kaçırmış sayılırız. Bu "False Negative" (fırsat kaybı), sistemi çöp veriye (False Positive) boğmaktan çok daha kabul edilebilirdir.

## 2. İSTİSNA: AYLIK DNA HASADI (MONTHLY HARVEST)
Sistemin evrimleşmesi için yeni DNA'ların eklenmesi gereklidir, ancak bu **kontrollü, periyodik ve insan denetimli** bir süreç olacaktır.

### Döngü:
*   **Periyot:** Ayda 1 Kez (Her ayın ilk haftası).
*   **Kapsam:** Geçtiğimiz ayın "Kaçan Balıkları" (Missed Opportunities).

### Süreç Adımları:
1.  **Tarama (Scan):** Geçtiğimiz ay boyunca `%10+` ani yükseliş yapmış ancak `DENIED` yemiş coinler listelenir.
2.  **Ön Eleme (Filter):** Bu coinlerin o günkü DNA'ları analiz edilir. "Sleeping", "Loose", "Depleting Energy" gibi zayıf nitelikler içerenler otomatik elenir. Sadece "Tight Squeeze", "Ignited", "Building Energy" gibi **kaliteli** DNA'lar aday havuzuna alınır.
3.  **İnsan Onayı (Approval):** Aday DNA listesi, kaçırdığı fırsatın grafiğiyle birlikte Ali Bey'in onayına sunulur.
4.  **Entegrasyon (Merge):** Sadece onaylanan DNA'lar ilgili `_key.json` dosyalarına `.append()` edilir.

## 3. TEKNİK KISITLAMALAR
*   `repair_golden_keys.py` vb. scriptler **TEK SEFERLİK (ON-OFF)** çalıştırılacak ve asla crontab/otomasyon parçası olmayacaktır.
*   Hiçbir script, `check_permission` fonksiyonunu bypass ederek "force write" yapamaz.
*   DNA ekleme işlemi öncesinde `_key.json` dosyalarının yedeği (`/backup/keys/YYYY_MM`) alın zorunluluğu vardır.

## 4. OCAK 2026 DURUMU (GÜNCEL)
Şu anki (Jan 17-27) eksik veri sorunu, bu protokol çerçevesinde bir "Ocak Ayı Erken Hasadı" (Early Harvest) olarak ele alınabilir. Ancak bu kez **filtreler maksimum seviyede** tutulacaktır.
