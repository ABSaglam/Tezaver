import streamlit as st
import pandas as pd
from datetime import datetime
from tezaver.engines.tunnel_engine import TunnelEngine
from tezaver.core.config import get_turkey_now
from tezaver.ui.chart_area import render_universal_chart

def render_tunnel_tab():
    st.markdown("## 🚇 Ayaş Tüneli (Tunnel Vision)")
    
    # 1. Kontrol Paneli
    col1, col2, col3 = st.columns([2, 5, 2])
    
    with col1:
        scan_date = st.date_input("Tarih Seçimi", value=get_turkey_now(), max_value=get_turkey_now())
    with col2:
        st.info("💡 **Bilgi:** Tünel algoritması 00:00'da vize dağıtır, gün boyu geçişleri izler.")
    # 2. Otomatik Rapor Yükleme (V16 Öncelikli)
    engine = TunnelEngine()
    
    # Detect date change and clear stale data immediately
    if 'last_tunnel_date' in st.session_state and st.session_state['last_tunnel_date'] != scan_date:
        # Clear previous results to avoid confusion
        if 'last_tunnel_results' in st.session_state:
            del st.session_state['last_tunnel_results']
    
    # Try loading report
    report_df = pd.DataFrame()
    try:
        # Verify engine method exists
        if hasattr(engine, 'parse_static_report'):
            report_df = engine.parse_static_report(str(scan_date))
        else:
            st.error("🚨 HATA: Motor güncellenmedi. Lütfen terminali kapatıp (Ctrl+C) tekrar açın.")
            
    except Exception as e:
        st.error(f"Rapor okuma hatası: {e}")

    # Determine what to show
    if not report_df.empty:
        # Static Report Found (Past Days)
        st.session_state['last_tunnel_results'] = report_df
        st.session_state['last_tunnel_date'] = scan_date
        st.toast(f"📄 {scan_date.strftime('%d %B')} Raporu Yüklendi", icon="✅")
        
        # Show "Force Scan" button optionally
        if col3.button("🔄 Tekrar Tara", type="secondary"):
             with st.spinner("🦅 Canlı tarama..."):
                 results_df = engine.scan_tunnel_day(str(scan_date))
                 st.session_state['last_tunnel_results'] = results_df
                 st.session_state['last_tunnel_date'] = scan_date
                 st.rerun()
                 
    else:
        # No Report -> Show Scan Button
        with col3:
             # Just a visual indicator if nothing is found
             st.caption(f"📅 {scan_date} için hazır rapor bulunamadı.")
             btn_scan = st.button("🔭 CANLI TARA", type="primary", use_container_width=True)
             if btn_scan:
                with st.spinner("🦅 Canlı taranıyor..."):
                    results_df = engine.scan_tunnel_day(str(scan_date))
                    st.session_state['last_tunnel_results'] = results_df
                    st.session_state['last_tunnel_date'] = scan_date
                    st.success(f"Tarama Bitti: {len(results_df)} sinyal.")
                    st.rerun()

    # 3. Sonuç Tablosu
    if 'last_tunnel_results' in st.session_state and not st.session_state['last_tunnel_results'].empty:
        df = st.session_state['last_tunnel_results']
        
        # Filtreleme kaldırıldı (User isteği)
        # st.markdown(f"### 📅 {st.session_state['last_tunnel_date'].strftime('%d %B %Y')} Raporu")
        
        # Seçim ve Tam Tablo
        event = st.dataframe(
            df,
            column_config={
                "NO": st.column_config.TextColumn("NO", width="small"),
                "SYM": st.column_config.TextColumn("SYM", width="small"),
                "MAX": st.column_config.TextColumn("MAX", width="small"),
                "CLOSE": st.column_config.TextColumn("CLOSE", width="small"),
                "TIME": st.column_config.TextColumn("TIME", width="small"),
                "SIG": st.column_config.TextColumn("SIG", width="small"),
                "TREND": st.column_config.TextColumn("TREND", width="small"),
                "POS": st.column_config.TextColumn("POS", width="small"),
                "ANG": st.column_config.TextColumn("ANG", width="small"),
                "VAL": st.column_config.TextColumn("VAL", width="small"),
                "P": st.column_config.TextColumn("P", width="small"),
                "P-21": st.column_config.TextColumn("P-21", width="small"),
                "BAR": st.column_config.TextColumn("BAR", width="small"),
                "NEXT": st.column_config.TextColumn("NEXT", width="small"),
                "R-Rib": st.column_config.TextColumn("R-Rib", width="small"),
                "Vrsi": st.column_config.TextColumn("Vrsi", width="small"),
                "V100": st.column_config.TextColumn("V100", width="small"),
                "V21": st.column_config.TextColumn("V21", width="small"),
                "V-Mom": st.column_config.TextColumn("V-Mom", width="small"),
                "VBoy": st.column_config.TextColumn("VBoy", width="small"),
                "V-Ch": st.column_config.TextColumn("V-Ch", width="small"),
                "V-Avg": st.column_config.TextColumn("V-Avg", width="small"),
                "DNA": None, # Hide DNA, user wants exact match to report
                "RAW": None # Hidden
            },
            hide_index=True,
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun"
        )
        
        # 4. Detay (Cerrahi)
        if event and len(event.selection['rows']) > 0:
            selected_idx = event.selection['rows'][0]
            selected_row = df.iloc[selected_idx]
            
            # Sembolü al (_SYM_REAL varsa onu kullan, yoksa SYM)
            symbol = selected_row.get('_SYM_REAL', selected_row['SYM'])
            if not symbol: symbol = selected_row['SYM'] # Fallback
            
            st.markdown("---")
            st.markdown(f"### 🧬 Cerrahi Analiz: `{symbol}`")
            
            # DNA Kartı
            dna_text = selected_row.get('DNA', "")
            if not dna_text or "..." in dna_text:
                # DNA boşsa (Rapordan henüz yüklenmediyse), o an canlı çek
                # engine = TunnelEngine() # Already init
                _, _, fetched_dna = engine.check_permission(symbol, str(scan_date))
                dna_text = fetched_dna

            dna_parts = dna_text.split('|')
            if len(dna_parts) >= 6:
                d_cols = st.columns(6)
                labels = ["Faz", "Sıkışma", "Harmoni", "Ritim", "Konum", "Enerji"]
                for i, part in enumerate(dna_parts[:6]):
                    d_cols[i].metric(labels[i], part.replace('_', ' ').title())

            trigger_dt = datetime.strptime(f"{str(scan_date)} {selected_row['TIME']}", "%Y-%m-%d %H:%M")
            
            render_universal_chart(
                symbol=symbol,
                timeframe="15m",
                event_time=trigger_dt,
                bars_to_peak=0
            )
            
    elif 'last_tunnel_results' in st.session_state:
        st.warning("Bu tarih için kriterlere uyan sinyal bulunamadı.")
