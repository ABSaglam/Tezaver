
"""
Tezaver Insight UI Tab (M25)
============================

Renders the centralized market overview dashboard.
"""

import streamlit as st
import pandas as pd
from tezaver.insight.insight_engine import load_market_overview
from tezaver.core.config import DEFAULT_COINS

def render_insight_tab():
    st.header("👁️ Tezaver Insight Panel")
    st.caption("Piyasa genel bakış, radar durumu ve onaylı stratejiler.")
    
    # Controls
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Yenile"):
            st.rerun()
            
    # Load Data (Cached if possible, but for now direct load)
    with st.spinner("Piyasa taranıyor..."):
        df = load_market_overview()
        
    if df.empty:
        st.info("Henüz veri yok. Lütfen Offline Maintenance çalıştırın.")
        return
        
    # Filters
    st.markdown("### Filtreler")
    f_col1, f_col2, f_col3 = st.columns(3)
    
    with f_col1:
        show_hot = st.checkbox("🔥 Sadece HOT", value=False)
    with f_col2:
        show_approved = st.checkbox("✅ Sadece Onaylı Stratejisi Olanlar", value=False)
    with f_col3:
        search_sym = st.text_input("🔍 Sembol Ara", value="")
        
    # Apply Filters
    filtered_df = df.copy()
    
    if show_hot:
        filtered_df = filtered_df[filtered_df["Radar"].str.contains("HOT")]
        
    if show_approved:
        # Check if Approved column is not "-" and not empty
        filtered_df = filtered_df[filtered_df["Approved"] != "-"]
        
    if search_sym:
        filtered_df = filtered_df[filtered_df["Symbol"].str.contains(search_sym.upper())]
        
    # Display Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Toplam Coin", len(df))
    m2.metric("🔥 Fırsat (HOT)", len(df[df["Radar"].str.contains("HOT")]))
    m3.metric("✅ Onaylı Strateji", len(df[df["Approved"] != "-"]))
    
    st.markdown("---")
    
    # Table styling using St.dataframe with column config
    # Table styling using St.dataframe with column config & selection
    event = st.dataframe(
        filtered_df,
        use_container_width=True,
        column_config={
            "Symbol": "Sembol",
            "Radar": "Radar Durumu",
            "Score": st.column_config.ProgressColumn(
                "Skor",
                help="Radar Environment Score (0-100)",
                min_value=0,
                max_value=100,
                format="%.1f"
            ),
            "Lane": "Baskın Kulvar",
            "Approved": "Onaylı Stratejiler",
            "Candidates": "Adaylar",
            "Last Update": "Son Güncelleme"
        },
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    # Handle Selection Navigation
    if event and event.selection and event.selection.rows:
        selected_index = event.selection.rows[0]
        # map back to filtered_df using iloc
        selected_symbol = filtered_df.iloc[selected_index]["Symbol"]
        
        # Navigate
        st.session_state['selected_coin'] = selected_symbol
        st.session_state['current_page'] = 'coin_detail'
        st.rerun()
