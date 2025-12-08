# src/tezaver/ui/i18n_tr.py
"""
Tezaver Mac - Türkçe UI çevirileri ve tooltip açıklamaları
Tüm kullanıcıya görünen metinler bu dosyada merkezi olarak yönetilir.
"""

# ========== SEKME ETIKETLERI ==========
TAB_LABELS = {
    "main_chart": "📉 Grafik",
    "raw_state": "Ham Durum",
    "wisdom": "Bilgelik",
    "rally_families": "Rally Aileleri",
    "rally_lab": "🚀 Yükseliş Lab",
    "levels": "Seviyeler & Çıkış Bölgeleri",
    "risk_rules": "⚠️ Risk & Kurallar",
    "cloud_package": "☁️ Bulut Paketi",
}

# ========== SEKME AÇIKLAMALARI ==========
TAB_EXPLANATIONS = {
    "main_chart": """
**📉 Ana Grafik** sekmesi, coinin fiyat hareketlerini ve teknik indikatörlerini detaylı olarak incelemenizi sağlar.

Burada:
- Farklı zaman dilimlerinde (15dk, 1sa, 4sa, 1gn, 1hf) grafiği inceleyebilir,
- RSI, MACD, ATR gibi indikatörleri görebilir,
- Destek ve direnç seviyelerini takip edebilirsiniz.
""",
    "raw_state": """
**Ham Durum** sekmesi, bu coin'in **şu anki röntgenini** gösterir.

Buradaki sayılar:
- Anlık fiyat ve son X barlık değişim
- Hacmin normaline göre kaç kat olduğu
- Volatilite (ATR vb.) – dalganın büyüklüğü
- RSI / MACD gibi indikatörlerin anlık seviyesi
- Piyasa rejimi (trend / yatay / kaotik / düşük likidite) gibi bilgileri içerir.
""",
    "wisdom": """
**Bilgelik** sekmesi, geçmişte benzer durumlarda bu coin'in **nasıl davrandığını** özetler.

Buradaki sayılar:
- Belirli pattern'lerin kaç örneği olduğu
- %5 / %10 / %20 yükseliş yakalama oranları
- Ortalama / medyan max yükseliş ve max geri çekilme
- Samimiyet / ihanet skorları (bu davranış ne kadar güvenilir?) gibi bilgiler verir.
""",
    "rally_families": """
**Rally Aileleri**, büyük yükselişlerden önceki benzer parmak izlerini **aileler** halinde toplar.

Her satır:
- Bir rally ailesini
- O ailede kaç örnek olduğunu
- Tipik max yükseliş yüzdesini
- Zirveye kadar geçen ortalama bar sayısını
- Rally öncesi tipik geri çekilme büyüklüğünü gösterir.
""",
    "rally_lab": """
**🚀 Yükseliş Lab**, tek tek **gerçek yükseliş vakalarını** listeler.

Her satır:
- O anki tarih/zamanı
- O esnadaki indikatör durumunu
- Sonraki barlarda görülen max yükselişi
- Bağlı olduğu rally ailesini gösterir.

Satırın yanındaki 📈 butonuna basarak, o yükselişin grafikteki hikayesini görebilirsiniz.
""",
    "levels": """
**Seviyeler & Çıkış Bölgeleri**, bu coin'in fiyat tarihinde önemli rol oynamış
**destek / direnç / kar al** bölgelerini gösterir.

Her seviye için:
- Kaç kez test edildiği
- Çoğunlukla dönüp dönmediği
- Kırılınca hareketin devam etme olasılığı gösterilir.
""",
    "risk_rules": """
**⚠️ Risk & Kurallar** sekmesi, bu coin için geçerli **emniyet kemerlerini** gösterir.

Burada:
- Maksimum pozisyon büyüklüğü
- ATR bazlı tipik stop mesafeleri
- Günlük / haftalık kayıp limitleri
- Çeşitli risk kurallarının ne sıklıkla tetiklendiği gibi bilgiler bulunur.
""",
    "cloud_package": """
**☁️ Bulut Paketi**, Tezaver Bulut tarafına aktarılacak **oyun planını** içerir.

Hangi rally aileleri kullanılacak,
hangi risk kuralları zorunlu,
hangi seviyelerin ana hedef olduğu gibi bilgiler buradan beslenir.
""",
}

# ========== KOLON BAŞLIKLARI (Piyasa Özeti Tablosu) ==========
COLUMN_LABELS = {
    # CoinState table columns
    "symbol": "Sembol",
    "data_state": "Veri Durumu",
    "last_update": "Son Güncelleme",
    "trend_soul_score": "Trend Soul",
    "harmony_score": "Ahenk",
    "betrayal_score": "İhanet Risk",
    "volume_trust": "Hacim Güven",
    "risk_level": "Risk Seviyesi",
    "opportunity_score": "Fırsat Skoru",
    "self_trust_score": "Öz Güven",
    "export_ready": "Export Hazır",
    
    # Rally families columns
    "base_timeframe": "Zaman Dilimi",
    "rally_class": "Rally Sınıfı",
    "family_id": "Aile No",
    "sample_count": "Örnek Sayısı",
    "avg_future_max_gain_pct": "Ort. Maks. Kazanç %",
    "avg_future_max_loss_pct": "Ort. Maks. Kayıp %",
    "median_max_gain_pct": "Medyan Maks. Kazanç %",
    "median_max_drawdown_pct": "Medyan Maks. Geri Çekilme %",
    "hit_5p_rate": "≥ %5 Başarı Oranı",
    "hit_10p_rate": "≥ %10 Başarı Oranı",
    "hit_20p_rate": "≥ %20 Başarı Oranı",
    "success_rate_5p": "≥ %5 Başarı",
    "success_rate_10p": "≥ %10 Başarı",
    "success_rate_20p": "≥ %20 Başarı",
    "trust_score": "Güven Skoru",
    
    # Rally lab columns
    "timestamp": "Tarih",
    "trigger": "Tetikleyici",
    "rally_label": "Rally Etiketi",
    "future_max_gain_pct": "Maks. Kazanç %",
    "future_max_loss_pct": "Maks. Kayıp %",
    
    # Levels columns
    "type": "Tip",
    "level_price": "Seviye Fiyatı",
    "touch_count": "Dokunma Sayısı",
    "strength_score": "Güç Skoru",
    "strength_label": "Güç Seviyesi",
    
    # Pattern stats columns
    "timeframe": "Zaman Dilimi",
}

# ========== METRİK TOOLTIP'LERİ ==========
METRIC_TOOLTIPS = {
    # ===== CoinState / Ham Durum Metrikleri =====
    "TrendSoul": "TrendSoul, fiyatın son dönemde yukarı / aşağı / yatay ruh hâlini özetleyen skor. 100'e yakın = güçlü yükseliş trendi.",
    "trend_soul_score": "Fiyatın son dönemde yukarı / aşağı / yatay ruh hâlini özetleyen skor. 100'e yakın = güçlü yükseliş trendi.",
    
    "HarmonyScore": "Harmony, fiyat, hacim ve indikatörlerin birbirini destekleyip desteklemediğini ölçen uyum skoru. Yüksek = tutarlı piyasa.",
    "harmony_score": "Fiyat, hacim ve indikatörlerin birbirini destekleyip desteklemediğini ölçen uyum skoru. Yüksek = tutarlı piyasa.",
    
    "BetrayalScore": "Betrayal, sık sık fake hareket yapma (aldatıcı kırılma, hacimsiz spike) eğilimini gösterir. Yüksek = dikkat!",
    "betrayal_score": "Sık sık fake hareket yapma (aldatıcı kırılma, hacimsiz spike) eğilimini gösterir. Yüksek = dikkat!",
    
    "VolumeTrust": "VolumeTrust, hacmin hareketi destekleyip desteklemediğine dair güven skorudur. Yüksek = hacim güvenilir.",
    "volume_trust": "Hacmin hareketi destekleyip desteklemediğine dair güven skorudur. Yüksek = hacim güvenilir.",
    
    "opportunity_score": "Bu coin'in şu anki teknik durumuna göre hesaplanan fırsat skoru. 100'e yakın = yüksek potansiyel.",
    "self_trust_score": "Bu coin'in kendi tarihsel davranışlarına göre kendine güven skoru. Yüksek = tutarlı performans.",
    "risk_level": "Volatilite ve ihanet skorlarına göre belirlenen risk seviyesi: low, medium, high, extreme.",
    "export_ready": "Bu coin'in Tezaver Bulut'a export edilmeye hazır olup olmadığını gösterir.",
    
    # ===== Regime / Shock Metrikleri =====
    "regime": "Piyasa rejimi: trending (trendli), range_bound (yatay), chaotic (kaotik), low_liquidity (düşük likidite).",
    "shock_flag": "Bu barın, olağandışı büyük gövde ve hacimle oluşan şok mum olup olmadığını gösterir.",
    "shock_risk": "Bu coin'de son dönemde görülen shock mum sıklığına bağlı risk skoru. Yüksek = ani hareketlere açık.",
    
    # ===== Volatilite Metrikleri =====
    "ATR": "Average True Range - Coin'in ortalama gerçek aralığı. Volatilite ölçüsü olarak kullanılır. Yüksek ATR = dalgalı coin.",
    "atr": "Average True Range - Ortalama gerçek aralık. Volatilite ölçüsü. Yüksek değer = dalgalı hareket.",
    "avg_atr": "Ortalama ATR değeri. Bu coin'in tipik volatilite genişliği.",
    "atr_std": "ATR'nin standart sapması. Volatilitenin ne kadar değişken olduğunu gösterir.",
    "vol_spike_freq": "Hacim patlaması sıklığı. Yüksek değer = sık sık hacim artışları.",
    "volatility_class": "Volatilite sınıfı: low (düşük), medium (orta), high (yüksek).",
    
    # ===== Hacim Metrikleri =====
    "volume_zscore": "Hacmin son dönemdeki ortalamasına göre kaç standart sapma uzaklıkta olduğunu gösterir. 2 üzeri = olağandışı yüksek hacim.",
    "vol_rel": "Hacmin son X barlık ortalamasına göre göreceli değeri. 1.0 = normal, 2.0 = 2 kat yüksek.",
    "vol_dry": "Hacim kuraklığı indikatörü. 1 = çok düşük hacim (likidite riski).",
    
    # ===== İndikatör Metrikleri =====
    "RSI": "Relative Strength Index - Aşırı alım/satım göstergesi. 70 üzeri = aşırı alım, 30 altı = aşırı satım.",
    "rsi": "Relative Strength Index. 70 üzeri = aşırı alım, 30 altı = aşırı satım.",
    "MACD": "Moving Average Convergence Divergence - Trend değişimi göstergesi.",
    "macd_line": "MACD çizgisi. Sinyal çizgisi ile kesişimi trend değişiminin habercisi.",
    "macd_signal": "MACD sinyal çizgisi. MACD ile kesişim önemli.",
    "macd_phase": "MACD fazı: bullish (yükseliş) / bearish (düşüş).",
    "ema_fast": "Hızlı EMA (üssel hareketli ortalama). Kısa dönem trendi gösterir.",
    "ema_mid": "Orta EMA. Orta dönem trendi.",
    "ema_slow": "Yavaş EMA. Uzun dönem trendi.",
    
    # ===== Rally Aileleri Metrikleri =====
    "rally_family_id": "Rally ailesinin kimliği. Benzer yükseliş örneklerini aynı aile altında toplar.",
    "family_id": "Rally ailesinin benzersiz numarası.",
    "sample_count": "Bu pattern / aile için kaç adet örnek (geçmiş vaka) bulunduğunu gösterir. Yüksek = daha güvenilir istatistik.",
    "median_max_gain_pct": "Bu ailedeki örneklerde, zirveye kadar görülen tipik (medyan) maksimum yükseliş yüzdesi.",
    "avg_future_max_gain_pct": "Bu ailedeki örneklerde görülen ortalama maksimum yükseliş yüzdesi.",
    "median_max_drawdown_pct": "Rally başlamadan önce tipik görülen en büyük geri çekilme yüzdesi.",
    "avg_future_max_loss_pct": "Rally sonrası görülen ortalama maksimum kayıp yüzdesi.",
    "success_rate_5p": "%5 ve üzeri yükselişle sonuçlanan örneklerin oranı.",
    "success_rate_10p": "%10 ve üzeri yükselişle sonuçlanan örneklerin oranı.",
    "success_rate_20p": "%20 ve üzeri yükselişle sonuçlanan örneklerin oranı.",
    "hit_5p_rate": "%5 ve üzeri yükselişle sonuçlanan örneklerin oranı (0-1 arası).",
    "hit_10p_rate": "%10 ve üzeri yükselişle sonuçlanan örneklerin oranı (0-1 arası).",
    "hit_20p_rate": "%20 ve üzeri yükselişle sonuçlanan örneklerin oranı (0-1 arası).",
    "trust_score": "Bu pattern/ailenin güvenilirlik skoru. Başarı oranı ve örnek sayısı dikkate alınır. 1.0'a yakın = çok güvenilir.",
    "rally_class": "Rally türü: micro (küçük), minor (orta), major (büyük), mega (çok büyük).",
    "base_timeframe": "Bu rally ailesinin hangi zaman diliminde analiz edildiği (1h, 4h, 1d).",
    
    # ===== Rally Lab / Yükseliş Örnekleri Metrikleri =====
    "timestamp": "Rally'nin başladığı tarih ve saat.",
    "trigger": "Rally'yi tetikleyen pattern veya durum.",
    "rally_label": "Rally'nin etiket sınıfı (örn: MICRO_5, MINOR_12, MAJOR_25).",
    "future_max_gain_pct": "Bu rally'de sonradan görülen maksimum yükseliş yüzdesi.",
    "future_max_loss_pct": "Bu rally'de sonradan görülen maksimum kayıp yüzdesi.",
    
    # ===== Seviyeler / Levels Metrikleri =====
    "type": "Seviye tipi: support (destek), resistance (direnç), exit (çıkış bölgesi).",
    "level_price": "Seviyenin fiyat değeri.",
    "touch_count": "Fiyatın bu seviyeyi kaç kez test ettiğini gösterir. Yüksek = güçlü seviye.",
    "strength_score": "Dokunma sayısı ve son dokunma zamanına bağlı güç puanı. 0-1 arası.",
    "strength_label": "Güç seviyesi etiketi: Güçlü / Orta / Zayıf.",
    "bounce_rate": "Bu seviyeden dönüş oranı. Yüksek = güçlü destek/direnç.",
    "break_success_rate": "Bu seviye kırıldığında hareketin devam etme olasılığı.",
    
    # ===== Pattern İstatistikleri =====
    "pattern_name": "Pattern adı veya trigger kodu.",
    "timeframe": "Pattern'in hangi zaman diliminde görüldüğü.",
    
    # ===== Risk & Kurallar Metrikleri =====
    "max_position_pct": "Bu coin için portföyünüzün en fazla hangi yüzdesiyle pozisyon açılması gerektiğini belirtir.",
    "daily_loss_limit_pct": "Günlük olarak izin verilen maksimum zarar yüzdesi. Bu sınır aşılırsa sistem durur.",
    "stop_atr_multiplier": "Stop loss mesafesi için ATR çarpanı. Örn: 2.0 = 2x ATR uzaklıkta stop.",
}

# ========== METRİK ETİKETLERİ (st.metric) ==========
METRIC_LABELS = {
    "avg_atr": "Ort. ATR",
    "atr_std": "ATR Std",
    "vol_spike_freq": "Vol. Spike Frekansı",
    "volatility_class": "Volatilite Sınıfı",
    "total_families": "Toplam Aile Sayısı",
    "high_trust_families": "Yüksek Güven (≥0.7)",
    "risk_level": "Risk Seviyesi",
    "regime": "Piyasa Rejimi",
    "opportunity_score": "Fırsat Skoru",
    "self_trust_score": "Öz Güven",
    "trend_soul": "Trend Soul",
    "harmony": "Ahenk",
    "betrayal_risk": "İhanet Riski",
    "shock_risk": "Şok Riski",
    "total_coins": "Toplam Coin",
    "export_ready": "Export Hazır",
    "avg_opportunity": "Ort. Fırsat Skoru",
    "high_risk_count": "Yüksek Riskli Coin",
    "avg_trust": "Ortalama Güven",
}

# ========== BUTON / WİDGET ETİKETLERİ ==========
BUTTON_LABELS = {
    "run_pipeline": "Pipeline Çalıştır",
    "full_pipeline": "🧠 Full Pipeline",
    "fast_pipeline": "⚡ Fast Pipeline",
    "run_tests": "✅ Testleri Çalıştır",
    "mini_backup": "📦 Mini Backup",
    "full_backup": "🗃 Full Backup",
    "show_logs": "📜 Logları Göster",
    "show_system_json": "🔍 Sistem Durumu JSON",
    "close": "❌ Kapat",
    "refresh": "🔄 Yenile",
    "export": "📤 Dışa Aktar",
    "view_chart": "📈 Grafikte Göster",
    "home": "🏠 Ana Sayfa",
    "market_summary": "📊 Piyasa Özeti",
}

# ========== BUTON TOOLTIP'LERİ ==========
BUTTON_TOOLTIPS = {
    "full_pipeline": "Tüm coin'ler için veri güncelleme, indikatör hesaplama ve beyin skorlamasını çalıştırır. Uzun sürebilir.",
    "fast_pipeline": "Sadece veri güncelleme ve temel indikatör hesaplamalarını yapar. Hızlı güncelleme için kullan.",
    "run_tests": "Tüm pytest testlerini çalıştırarak sistemin sağlığını kontrol eder.",
    "mini_backup": "Coin profilleri ve kritik verilerin hızlı yedeğini alır.",
    "full_backup": "Tüm veri ve yapılandırmaların tam yedeğini alır.",
    "show_logs": "Sistem log dosyasının son satırlarını gösterir. Hata ayıklama için kullanışlı.",
    "show_system_json": "Sistem durumu nesnesinin tam JSON çıktısını gösterir.",
    "explain_mode": "Açıklamaları ve felsefi notları göster / gizle.",
}

# ========== GRAFİK AÇIKLAMALARI ==========
CHART_EXPLANATIONS = {
    "indicator_legend_title": "📊 Grafikteki Göstergelerin Anlamı",
    "indicator_legend_content": """
- **RSI** – Relative Strength Index. 70 üzeri aşırı alım, 30 altı aşırı satım bölgesini gösterir.
- **ATR** – Average True Range. Volatilitenin büyüklüğünü ölçer. Yüksek ATR = dalgalı coin.
- **MACD** – Trend değişim göstergesi. MACD çizgisinin sinyal çizgisini kesmesi önemli sinyaldir.
- **Hacim** – İşlem hacminin yüksekliği. Yüksek hacimli hareketler daha güvenilir kabul edilir.
- **EMA** – Üssel Hareketli Ortalamalar. Hızlı/orta/yavaş EMA'lar farklı dönem trendlerini gösterir.
- **Destek/Direnç Çizgileri** – Fiyatın tarihsel olarak tepki verdiği önemli seviyeler.
""",
}

# ========== GENEL METİNLER ==========
GENERAL_TEXTS = {
    "app_title": "🧬 Tezaver Mac - Ana Panel",
    "welcome": "Hoş Geldiniz",
    "market_summary_title": "📊 Piyasa Özeti",
    "coin_detail_title": "Coin Detay İnceleme",
    "system_status": "Sistem Durumu",
    "system_control": "Sistem Kontrolü",
    "no_data": "Veri bulunamadı",
    "loading": "Yükleniyor...",
    "error": "Hata",
    "success": "Başarılı",
    "explanation_mode": "📜 Açıklama Modu",
    "select_coin": "İncelenecek Coin'i Seçin:",
}
