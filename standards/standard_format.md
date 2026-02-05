# TEZAVER REPORT STANDARD v17 (FAZ100)

Bu doküman, Tezaver projesindeki tüm listeleme ve raporlama işlemleri için **TEK VE GEÇERLİ STANDART** olan **FAZ100 v17** formatını tanımlar.

Tüm analiz scriptleri, "listeleme" komutları ve durum raporları bu sütun yapısına sadık kalmalıdır.

## 📋 TABLO YAPISI VE SÜTUNLAR

| SÜTUN | AÇIKLAMA | MANTIK / HESAPLAMA |
| :--- | :--- | :--- |
| **NO** | Sıra Numarası | Listenin satır indexi. |
| **SYM** | Sembol | Coin Simgesi (örn. BTCUSDT). |
| **MAX** | Günlük Zirve (%) | `(High - Open) / Open`. Gün içi görülen maksimum potansiyel. |
| **CLOSE** | Anlık/Kapanış (%) | `(Close - Open) / Open`. Mevcut fiyatın açılışa göre değişimi. |
| **TIME** | Sinyal Saati | Sinyalin oluştuğu mumun kapanış saati (örn. 14:15). |
| **SIG** | Sinyal Tipi | Strateji Kodu (örn. F100). |
| **CVT** | Kritik Eşik (CVT) | +0.8% (Güvenli) veya -0.4% (Retest) değerlerini alan eşik kontrolü. |
| **TREND** | Trend (4H + 1H) | Çift Top İkonu. Sol=4H, Sağ=1H. <br>Yeşil (🟢): Fiyat EMA21 üzerinde.<br>Kırmızı (🔴): Fiyat EMA21 altında. |
| **POS** | Ribbon Durumu | RSI Ribbon Pozisyonu (21 & 55 EMA of RSI). <br>🟢: 21 > 55 (Boğa)<br>🔴: 21 < 55 (Ayı)<br>Siyah/Sarı: Aşırı satım bölgeleri. |
| **ANG** | Açı Puanı | Ribbonların açılma derecesinin skorlanmış hali. |
| **R-Ang** | RSI Eğim Açısı | RSI EMA'sının anlık eğimi (Derece). <br>+10° üstü yeşil, negatif ise kırmızı. |
| **VAL** | Kalite (Kalp) | Hacim ve Trend onayı. <br>❤️: Standart onay.<br>💚: Güçlü onay (Ribbon pozitif + Açı iyi). |
| **P** | Tetik Mumu (%) | Sinyal mumunun gövde büyüklüğü. |
| **TIER** | Madalya | Sinyal sonrası performansa göre rozet.<br>💎 >= %30<br>🥇 >= %20<br>🥈 >= %10<br>🥉 >= %5 |
| **P-49** | Max Kazanç | Sinyalden sonra 49 bar içinde görülen en yüksek % kazanç. |
| **BAR** | Tepe Süresi | Zirveye ulaşmak için geçen bar sayısı (Süre maliyeti). |
| **NEXT** | +1 Mum | Sinyalden hemen sonraki mumun kapanış yüzdesi. |
| **N-1** | +2 Mum | Sinyalden iki sonraki mumun kapanış yüzdesi. |
| **CGS** | Güven Skoru | **Core Green Score**. Sistemin coine verdiği toplam güvenilirlik notu (0-100%). |
| **ADX** | Trend Gücü | Günlük ADX(14). 25+ Trend var, 40+ Güçlü Trend. |
| **ATR%** | Volatilite | `(ATR14 / Close) * 100`. Günlük ortalama hareket marjı. |
| **Vrsi** | V-RSI Hibrit | Hacim x RSI Gücü. Yakıt kalitesi skoru. |
| **VBoy** | Doluluk Oranı | `(Body / Range)`. Mumların ne kadar "dolu" olduğunu gösterir. |
| **V100** | V-Index (Uzun) | Son 100 barın volatilitesine göre mevcut hareketin büyüklüğü. |
| **V21** | V-Index (Kısa) | Son 21 barın volatilitesine göre mevcut hareketin büyüklüğü. |
| **V-Mom** | V-Momentum | `V-Index / Avg(Past V-Index)`. Volatilitenin artış ivmesi. |

---

## 🎨 RENKLENDİRME KURALLARI

- **Pozitif Değerler**: Yeşil (`<font color='green'>`)
- **Negatif Değerler**: Kırmızı (`<font color='red'>`)
- **Sıfır/Nötr**: Gri veya Standart
- **Vurgular**: `**Bold**` (Örn: %10 üzeri kazançlar, yüksek açılar)
- **Tooltips**: ATR sütununda mouse-over ile detaylı "Tetik vs Günlük ATR" bilgisi.

Bu format, Tezaver projesinin "Ortak Dili"dir.
