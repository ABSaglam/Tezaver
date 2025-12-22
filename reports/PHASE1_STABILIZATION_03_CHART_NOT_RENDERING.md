# FAZ 1 — Stabilizasyon Raporu #3 (PHASE1_STABILIZATION_03_CHART_NOT_RENDERING)

**Tarih:** 2025-12-22  
**Durum:** ✅ FIXED (Code-level)

---

## Sorun Tanımı
**Bug:** Merge fix'leri yapılmasına rağmen Coin Detail → Rally → 15m sekmesinde grafik hâlâ görünmüyor olabilirdi (blank space).
**Root Cause:** `render_rally_event_chart` fonksiyonu içinde `st.plotly_chart` çağrısının koşullu bloklar arasında kaybolması veya exception yutulması ihtimali vardı. Ayrıca render path'in doğrulanması gerekiyordu.

---

## Çözüm Özeti

### 1. Render Path Tespiti
15m Rally tab'ının `src/tezaver/ui/fast15_lab_tab.py:render_fast15_lab_tab` fonksiyonunu kullandığı ve buradan `chart_area.py:render_rally_event_chart`'ı çağırdığı doğrulandı.

### 2. Debug Modu ve UI Eklentisi
`src/tezaver/ui/fast15_lab_tab.py` dosyasına **"Debug (Rally 15m)"** kutucuğu eklendi.
- Bu kutu işaretlendiğinde ekranda render path bilgisi görünür: `Path: fast15_lab_tab:render_fast15_lab_tab -> chart_area:render_rally_event_chart`
- Ayrıca `debug=True` bayrağı `chart_area` fonksiyonuna iletilir.

### 3. Force Render Logic
`src/tezaver/ui/chart_area.py` güncellendi:
- Fonksiyon imzasına `debug: bool = False` parametresi eklendi.
- `df_history` (bar verisi) var olduğu sürece `st.plotly_chart(fig)` çağrısının çalışması garanti altına alındı.
- Merge hataları olsa bile (fallback mekanizması sayesinde) kod akışı `st.plotly_chart` satırına ulaşır.
- Debug modunda çalışma anında bar sayısı ve event time bilgileri ekrana basılır.

---

## Nasıl Doğrulanır?

1. Streamlit uygulamasını başlatın (`streamlit run src/tezaver/ui/main_panel.py`).
2. **Coin Detail** sayfasına gidin (bir coin seçin).
3. **Rally** sekmesine tıklayın.
4. Alt sekme **15 Dakika**'yı seçin.
5. Bir olay seçin.
6. Eğer grafik görünmüyorsa, **"Debug (Rally 15m)"** kutucuğunu işaretleyin.
7. Ekranda kırmızı hata mesajı varsa "df_history is None" gibi, veri eksiktir. Mavi/Siyah debug bilgileri varsa kod çalışıyordur.

---

## Değişen Dosyalar

| Aksiyon | Dosya |
|---------|-------|
| **MODIFY** | `src/tezaver/ui/fast15_lab_tab.py` (Debug toggle eklendi) |
| **MODIFY** | `src/tezaver/ui/chart_area.py` (`debug` param, force render logic) |

---

## Komut Çıktısı

```bash
# Signature Verification
(symbol: str, timeframe: str, ... debug: bool = False) -> None
```
Doğrulama başarılı.
