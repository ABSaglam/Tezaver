"""
Foundry Tab - Dökümhane Bundle Browser
=======================================

UI for browsing ApprovedRallyBundle packages.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json

from tezaver.foundry.bundle_index import scan_bundles, filter_bundles, load_bundle_files


@st.cache_data(ttl=300)
def cached_scan_bundles():
    """Cached bundle scanning."""
    return scan_bundles()


def render_foundry_page():
    """Main render function for Foundry tab."""
    st.title("🏭 Dökümhane - ApprovedRallyBundle Browser")
    
    # Rescan button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Rescan Bundles"):
            cached_scan_bundles.clear()
            st.rerun()
    
    # Scan bundles
    df_bundles = cached_scan_bundles()
    
    if df_bundles.empty:
        st.warning("No bundles found. Run packaging first to create ApprovedRallyBundles.")
        return
    
    st.success(f"📦 Found **{len(df_bundles)}** bundles")
    
    # Filters
    st.markdown("---")
    st.markdown("### 🔍 Filters")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        symbols = ["All"] + sorted(df_bundles["symbol"].unique().tolist())
        selected_symbol = st.selectbox("Symbol", symbols)
    
    with col2:
        timeframes = ["All"] + sorted(df_bundles["timeframe"].unique().tolist())
        selected_timeframe = st.selectbox("Timeframe", timeframes)
    
    with col3:
        all_tiers = ["DIAMOND", "GOLD", "SILVER", "BRONZE", "UNKNOWN"]
        selected_tiers = st.multiselect("Tiers", all_tiers, default=all_tiers)
    
    with col4:
        all_verdicts = ["PASS", "FAIL"]
        selected_verdicts = st.multiselect("QC Verdict", all_verdicts, default=["PASS"])
    
    min_qc_score = st.slider("Min QC Score", 0, 100, 60)
    
    # Apply filters
    df_filtered = filter_bundles(
        df_bundles,
        symbol=selected_symbol,
        timeframe=selected_timeframe,
        tiers=selected_tiers if selected_tiers else None,
        qc_verdicts=selected_verdicts if selected_verdicts else None,
        min_qc_score=min_qc_score
    )
    
    st.markdown(f"**Filtered:** {len(df_filtered)} / {len(df_bundles)} bundles")
    
    # Bundle table
    st.markdown("---")
    st.markdown("### 📋 Bundle Inventory")
    
    if df_filtered.empty:
        st.info("No bundles match filters.")
        return
    
    # Display table (without bundle_dir column for cleaner view)
    display_cols = ["symbol", "timeframe", "tier", "qc_score", "qc_verdict", "event_time_iso", "event_id"]
    st.dataframe(df_filtered[display_cols], use_container_width=True, height=300)
    
    # Bundle selection for detail view
    st.markdown("---")
    st.markdown("### 📄 Bundle Detail")
    
    # Create selection options
    bundle_options = [
        f"{row['symbol']} | {row['timeframe']} | {row['tier']} | Score:{row['qc_score']} | {row['event_id']}"
        for idx, row in df_filtered.iterrows()
    ]
    
    if not bundle_options:
        st.info("Select a bundle from the table above")
        return
    
    selected_bundle_str = st.selectbox("Select Bundle", bundle_options)
    
    if selected_bundle_str:
        # Find selected bundle
        selected_idx = bundle_options.index(selected_bundle_str)
        selected_bundle = df_filtered.iloc[selected_idx]
        
        bundle_dir = selected_bundle["bundle_dir"]
        
        # Load bundle files
        bundle_files = load_bundle_files(bundle_dir)
        
        # Display in tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📋 Manifest",
            "📝 Annotation",
            "✅ QC Report",
            "📊 Event Row",
            "📈 Price Window"
        ])
        
        with tab1:
            if bundle_files["manifest"]:
                st.json(bundle_files["manifest"])
            else:
                st.warning("manifest.json not found")
        
        with tab2:
            if bundle_files["annotation"]:
                st.json(bundle_files["annotation"])
            else:
                st.warning("annotation.json not found")
        
        with tab3:
            if bundle_files["qc_report"]:
                st.json(bundle_files["qc_report"])
            else:
                st.warning("qc_report.json not found")
        
        with tab4:
            if bundle_files["event_row"]:
                st.json(bundle_files["event_row"])
            else:
                st.warning("event_row.json not found")
        
        with tab5:
            if bundle_files["price_window"] is not None and not bundle_files["price_window"].empty:
                df_price = bundle_files["price_window"]
                st.write(f"**Window:** {len(df_price)} bars")
                
                # Simple price chart (close price line)
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=df_price['open_time'],
                    y=df_price['close'],
                    mode='lines',
                    name='Close Price',
                    line=dict(color='#00E5FF', width=2)
                ))
                
                fig.update_layout(
                    title="Price Window (Close Price)",
                    xaxis_title="Time",
                    yaxis_title="Price",
                    height=400,
                    hovermode='x unified',
                    template='plotly_dark'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("price_window.parquet not found")
