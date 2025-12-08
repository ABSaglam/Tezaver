import streamlit as st
from tezaver.core.settings_manager import settings_manager

def render_settings_page():
    st.title("⚙️ Ayarlar")
    st.markdown("---")
    
    # Load current settings from session state or file
    if 'user_settings' not in st.session_state:
        st.session_state.user_settings = settings_manager.load_settings()
    
    settings = st.session_state.user_settings
    indicators = settings.get('indicators', {})
    
    # --- TOP BAR: SAVE BUTTON ---
    col_head1, col_head2 = st.columns([3, 1])
    with col_head1:
        st.caption("Tüm grafik ve sistem ayarlarını buradan yönetebilirsiniz.")
    with col_head2:
        if st.button("💾 Kaydet ve Uygula", type="primary", use_container_width=True):
            settings_manager.save_settings(settings)
            st.success("Ayarlar başarıyla kaydedildi!")
            
    # --- CATEGORIZED TABS ---
    # We use emojis for visual clarity
    tab_graphic, tab_ma, tab_momentum, tab_volatility = st.tabs([
        "📊 Grafik & Görünüm", 
        "📈 Hareketli Ortalamalar", 
        "🌊 Momentum (MACD/RSI)", 
        "⚡ Volatilite (ATR)"
    ])
    
    # 1. GRAFİK & GÖRÜNÜM (Fiyat, Hacim)
    with tab_graphic:
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader("🕯️ Mum Grafiği")
            candles = indicators.get('candles', {})
            candles['up_color'] = st.color_picker("Yükseliş Mumu (Yeşil)", value=candles.get('up_color', '#089981'))
            candles['down_color'] = st.color_picker("Düşüş Mumu (Kırmızı)", value=candles.get('down_color', '#F23645'))
            indicators['candles'] = candles
            
        with col_g2:
            st.subheader("📊 Hacim (Volume)")
            vol_cfg = indicators.get('volume', {})
            vol_cfg['enabled'] = st.toggle("Hacim Göster", value=vol_cfg.get('enabled', True))
            vol_cfg['up_color'] = st.color_picker("Yükseliş Hacmi", value=vol_cfg.get('up_color', '#089981'))
            vol_cfg['down_color'] = st.color_picker("Düşüş Hacmi", value=vol_cfg.get('down_color', '#F23645'))
            indicators['volume'] = vol_cfg

    # 2. HAREKETLİ ORTALAMALAR (EMA)
    with tab_ma:
        st.info("Üstel Hareketli Ortalamalar (EMA) trend yönünü belirlemeye yardımcı olur.")
        col_ma1, col_ma2 = st.columns(2)
        
        with col_ma1:
            st.markdown("##### Hızlı EMA (Fast)")
            ema_f = indicators.get('ema_fast', {})
            ema_f['enabled'] = st.toggle("Hızlı EMA Göster", value=ema_f.get('enabled', True))
            ema_f['period'] = st.number_input("Hızlı Periyot", min_value=1, value=ema_f.get('period', 20))
            ema_f['color'] = st.color_picker("Hızlı EMA Rengi", value=ema_f.get('color', '#2962FF'))
            indicators['ema_fast'] = ema_f
            
        with col_ma2:
            st.markdown("##### Yavaş EMA (Slow)")
            ema_s = indicators.get('ema_slow', {})
            ema_s['enabled'] = st.toggle("Yavaş EMA Göster", value=ema_s.get('enabled', True))
            ema_s['period'] = st.number_input("Yavaş Periyot", min_value=1, value=ema_s.get('period', 50))
            ema_s['color'] = st.color_picker("Yavaş EMA Rengi", value=ema_s.get('color', '#FF9800'))
            indicators['ema_slow'] = ema_s

    # 3. MOMENTUM (RSI & MACD)
    with tab_momentum:
        sub_rsi, sub_macd = st.tabs(["RSI", "MACD"])
        
        # RSI
        with sub_rsi:
            st.subheader("RSI Ayarları")
            rsi_cfg = indicators.get('rsi', {})
            c1, c2 = st.columns(2)
            with c1:
                rsi_cfg['enabled'] = st.toggle("RSI Göster", value=rsi_cfg.get('enabled', True))
                rsi_cfg['period'] = st.number_input("RSI Uzunluk", min_value=1, value=rsi_cfg.get('period', 11))
                rsi_cfg['ema_period'] = st.number_input("RSI Sinyal (EMA)", min_value=1, value=rsi_cfg.get('ema_period', 11))
            with c2:
                rsi_cfg['source'] = st.selectbox("Hesaplama Kaynağı", options=["close"], index=0, disabled=True, help="Şimdilik sadece 'close' destekleniyor.")
                rsi_cfg['color'] = st.color_picker("RSI Çizgisi", value=rsi_cfg.get('color', '#7E57C2'))
                rsi_cfg['ema_color'] = st.color_picker("RSI Sinyal (EMA)", value=rsi_cfg.get('ema_color', '#FFC107'))
            indicators['rsi'] = rsi_cfg

        # MACD
        with sub_macd:
            st.subheader("MACD Ayarları")
            macd_cfg = indicators.get('macd', {})
            c1, c2 = st.columns(2)
            with c1:
                macd_cfg['enabled'] = st.toggle("MACD Göster", value=macd_cfg.get('enabled', True))
                macd_cfg['fast'] = st.number_input("Hızlı (Fast) Uzunluk", min_value=1, value=macd_cfg.get('fast', 12))
                macd_cfg['slow'] = st.number_input("Yavaş (Slow) Uzunluk", min_value=1, value=macd_cfg.get('slow', 26))
                macd_cfg['signal'] = st.number_input("Sinyal (Signal) Uzunluk", min_value=1, value=macd_cfg.get('signal', 9))
                
                st.markdown("#### 🎨 Tolerans (Smoothness)")
                macd_cfg['color_tolerance'] = st.slider(
                    "Renk Değişim Toleransı (%)", 0.0, 100.0, 
                    value=float(macd_cfg.get('color_tolerance', 0.0)),
                    help="Ufak düzeltmelerde rengin hemen değişmesini engeller."
                )

            with c2:
                st.markdown("#### Renkler")
                macd_cfg['macd_color'] = st.color_picker("MACD Çizgisi", value=macd_cfg.get('macd_color', '#2962FF'))
                macd_cfg['signal_color'] = st.color_picker("Sinyal Çizgisi", value=macd_cfg.get('signal_color', '#FF9800'))
                
                st.divider()
                c_h1, c_h2 = st.columns(2)
                with c_h1:
                    macd_cfg['hist_pos_inc_color'] = st.color_picker("Yeşil (Yükseliş Güçlü)", value=macd_cfg.get('hist_pos_inc_color', '#00E676'))
                    macd_cfg['hist_neg_inc_color'] = st.color_picker("Kırmızı (Düşüş Güçlü)", value=macd_cfg.get('hist_neg_inc_color', '#FF1744'))
                with c_h2:
                    macd_cfg['hist_pos_dec_color'] = st.color_picker("Mor (Yükseliş Zayıf)", value=macd_cfg.get('hist_pos_dec_color', '#D500F9'))
                    macd_cfg['hist_neg_dec_color'] = st.color_picker("Sarı (Düşüş Zayıf)", value=macd_cfg.get('hist_neg_dec_color', '#FFEA00'))
            indicators['macd'] = macd_cfg

    # 4. VOLATİLİTE (ATR)
    with tab_volatility:
        st.subheader("ATR (Average True Range)")
        st.caption("Fiyatın etrafında volatilite bantları oluşturur.")
        atr_cfg = indicators.get('atr', {})
        
        c1, c2 = st.columns(2)
        with c1:
            atr_cfg['enabled'] = st.toggle("ATR Bantlarını Göster", value=atr_cfg.get('enabled', False))
            atr_cfg['period'] = st.number_input("ATR Periyodu", min_value=1, value=atr_cfg.get('period', 14))
        with c2:
            atr_cfg['multiplier'] = st.number_input("ATR Çarpanı (Bant Genişliği)", min_value=0.1, value=atr_cfg.get('multiplier', 2.0), step=0.1)
            atr_cfg['color'] = st.color_picker("Bant Rengi", value=atr_cfg.get('color', '#00BCD4'))
            
        indicators['atr'] = atr_cfg
            
    # Save back to settings structure
    settings['indicators'] = indicators
    st.session_state.user_settings = settings
