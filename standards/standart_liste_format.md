# STANDART LİSTE FORMATI (V1.0)

Bu doküman, Tezaver raporlamalarında kullanılacak "STANDART LİSTE" formatının teknik özelliklerini ve sütun tanımlarını içerir.

## 1. Genel Yapı

Her rapor bloğu şu hiyerarşi ile başlar:

```markdown
## 📅 [Gün] [Ay] [Yıl] (Sayaç: [Günlük Sinyal Sayısı])

### STANDART LİSTE
**Strateji:** [Uygulanan Strateji İsmi]

[TABLO BURAYA GELECEK]
```

## 2. Tablo Şablonu

Tablo, aşağıdaki 28 sütundan oluşur. Veri hücreleri, görsel zenginlik (renk kodları, ikonlar, tooltip) içermelidir.

| NO | SYM | CLASS | CONFIRM | MAX | CLOSE | TIME | SIG | CVT | TREND | POS | ANG | R-Ang | VAL | P | TIER | P-49 | BAR | V-4 | MDD | CGS | ADX | ATR% | Vrsi | VBoy | V100 | V21 | V-Mom |
|----|-----|-------|---------|-----|-------|------|-----|-----|-------|-----|-----|-------|-----|---|------|------|-----|-----|-----|-----|-----|------|------|------|------|-----|-------|

## 3. Sütun Lejantı (Detaylı Açıklama)

Aşağıda her bir sütunun ne anlama geldiği açıklanmıştır:

| Sütun | Açıklama | Örnek Veri |
|-------|----------|------------|
| **NO** | Sıra Numarası. Günün kaçıncı sinyali olduğunu belirtir. | `1`, `2` |
| **SYM** | **Sembol**. İşlem gören paritenin adı. | `BTCUSDT` |
| **CLASS** | **Sinyal Kalitesi**. Yapay zeka veya algoritma tarafından belirlenen kalite sınıfı. (C++, B, A, A++ vb.) | `**C++**` |
| **CONFIRM** | **Onay Durumu**. Sinyalin teyit edilip edilmediği. | `<font color='green'>**CONFIRMED**</font>` |
| **MAX** | **Maksimum Kâr**. Sinyalden sonra görülen en yüksek kâr oranı. | `<font color='green'>+11.2%</font>` |
| **CLOSE** | **Kapanış Kârı**. Mevcut durumdaki veya işlem kapanışındaki kâr oranı. | `+9.0%` |
| **TIME** | **Sinyal Saati**. Sinyalin üretildiği mum kapanış saati. | `13:00` |
| **SIG** | **Sinyal Tipi**. Sinyali üreten algoritma kodu. | `F100` |
| **CVT** | **Critical Value Trend**. Kritik değer trendi veya anlık değişim göstergesi. | `<font color='green'>+0.8%</font>` |
| **TREND** | **Trend Yönü**. Kısa ve orta vadeli trend durumunu gösteren ikonlar. | `🟢🟢` |
| **POS** | **Pozisyon**. Mevcut mumun trende göre konumu. | `🟢` |
| **ANG** | **Açı (Angle)**. Fiyat hareketinin eğim açısı. | `<font color='green'>+4.0</font>` |
| **R-Ang** | **Ribbon Angle**. Hareketli ortalama şeridinin açısı. Görsel açı. | `**+40°**` |
| **VAL** | **Value Icon**. Sinyalin değerini simgeleyen ikon (Kalp vs.). | `💚` / `❤️` |
| **P** | **Pivot/Potansiyel**. Hedeflenen veya hesaplanan potansiyel hareket. | `+4.9%` |
| **TIER** | **Seviye/Madalya**. Performans başarısına göre verilen madalya (Gümüş, Altın, Elmas). | `🥈` |
| **P-49** | **49 Bar Performansı**. Sinyalden sonraki 49 bar içindeki performans. | `+11.4%` |
| **BAR** | **Geçen Süre**. Sinyalden bu yana geçen bar (mum) sayısı. | `3` |
| **V-4** | **Volume (4 Bar)**. Son 4 barın hacim ortalamasının normalin kaç katı olduğu. | `13.2x` |
| **MDD** | **Max Drawdown**. Sinyalden sonra görülen en büyük terste kalma oranı. | `-4.5%` |
| **CGS** | **Core Green Score**. Temel yeşil skor/güven endeksi. | `**100%**` |
| **ADX** | **ADX**. Trend gücü göstergesi. | `48` |
| **ATR%** | **ATR Yüzdesi**. Ortalama Gerçek Aralık yüzdesi (Volatilite). Tooltip ile tetik ve günlük ATR detayları verilir. | `0.9%` |
| **Vrsi** | **Volume RSI**. Hacim tabanlı RSI değeri. | `79.3` |
| **VBoy** | **Volume Buoyancy**. Hacim kaldırma kuvveti çarpanı. | `18.0x` |
| **V100** | **Volume 100**. Son 100 barın hacim performansı yüzdesi. | `100%` |
| **V21** | **Volume 21**. Son 21 barın hacim performansı yüzdesi. | `100%` |
| **V-Mom** | **Volume Momentum**. Hacim momentumu çarpanı. | `18.0x` |
