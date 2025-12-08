# REV.01.B - Bulut Export Alignment
**Uygulanan Değişiklikler:**

1. **Güvenli Veri Yükleme:**
   - `explanation_cards.py` dosyasına `_load_json_safely` eklendi.
   - `load_coin_explanation_context` fonksiyonu, eksik dosyalarda çökmek yerine `None` veya boş obje dönecek şekilde güncellendi.

2. **Sözlü Özet Katmanı:**
   - `src/tezaver/ui/main_panel.py` dosyasında `render_bulut_export_tab` fonksiyonu yeniden yazıldı.
   - Sekme açıldığında en üstte şu 4 özeti içeren dinamik bir blok yer alıyor:
     - ⚡ Tetik ve Rally Özeti
     - 🚀 15 Dakika Hızlı Yükseliş Özeti
     - 🕒 Time-Labs (1h / 4h) Özeti
     - 🧠 Strateji Uyum Özeti

3. **Status:**
   - Eski özellikler (Export butonu, metrikler) korundu.
   - Yeni özellikler başarıyla üste eklendi.
