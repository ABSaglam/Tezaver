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
from tezaver.matrix.sniper.certification_registry import CertificationRegistry
from tezaver.matrix.sniper.benchmark_service import BenchmarkService
# Import locally to avoid circulars or ensure freshness
from tezaver.sniper.sniper_backtest_v2 import analyze_pack_performance


@st.cache_data(ttl=60)
def cached_scan_bundles_v2():
    """Cached bundle scanning (v2)."""
    return scan_bundles()


def render_foundry_page():
    """Main render function for Foundry tab."""
    st.title("🏭 Dökümhane - ApprovedRallyBundle Browser")
    
    # Rescan button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Rescan Bundles"):
            cached_scan_bundles_v2.clear()
            st.rerun()
    
    # Scan bundles
    df_bundles = cached_scan_bundles_v2()
    
    if df_bundles.empty:
        st.warning("No bundles found. Run packaging first to create ApprovedRallyBundles.")
        return
    
    # Load Certification Status
    cert_registry = CertificationRegistry()
    df_bundles["certification"] = df_bundles["bundle_id"].apply(cert_registry.get_bundle_stage)
    
    # Ensure essential columns exist in df_bundles
    for col in ["scenario_id", "qc_score", "qc_verdict"]:
        if col not in df_bundles.columns:
            df_bundles[col] = "N/A" if col == "scenario_id" else (0 if col == "qc_score" else "UNKNOWN")

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
    
        all_verdicts = ["PASS", "FAIL"]
        selected_verdicts = st.multiselect("QC Verdict", all_verdicts, default=["PASS"])
    
    all_certs = ["candidate", "sniper_passed", "live_certified", "demoted"]
    selected_certs = st.multiselect("Certification Stage", all_certs, default=all_certs)

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
    
    if selected_certs:
        df_filtered = df_filtered[df_filtered["certification"].isin(selected_certs)]
    
    st.markdown(f"**Filtered:** {len(df_filtered)} / {len(df_bundles)} bundles")
    
    # Bundle table
    st.markdown("---")
    st.markdown("### 📋 Bundle Inventory")
    
    if df_filtered.empty:
        st.info("No bundles match filters.")
        return
    
    # Display table (without bundle_dir column for cleaner view)
    display_cols = ["certification", "symbol", "timeframe", "tier", "qc_score", "qc_verdict", "scenario_id", "event_time_iso", "event_id"]
    available_display_cols = [c for c in display_cols if c in df_filtered.columns]
    st.dataframe(df_filtered[available_display_cols], use_container_width=True, height=300)
    
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
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "📋 Manifest",
            "📖 Story",
            "🛡️ Lifecycle",
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
            manifest = bundle_files.get("manifest")
            if manifest and "narrative" in manifest:
                nar = manifest["narrative"]
                st.markdown(f"### {nar.get('label', 'Unknown Story')}")
                st.info(nar.get('desc', 'No description'))
                st.write(f"**Scenario ID:** {manifest.get('scenario_id')}")
                st.write(f"**Risk Level:** {nar.get('risk', 'Medium')}")
            else:
                st.info("No story/narrative data in this bundle.")
        
        with tab3:
            # Lifecycle info
            cert = selected_bundle.get("certification", "candidate")
            
            # --- 1. STAGE HEADER ---
            status_colors = {
                "candidate": "#CFD8DC",     # Grey-Blue (Waiting in Sniper)
                "sniper_passed": "#FFD600", # Yellow (War Ready)
                "live_certified": "#00E676",# Green (Live Ready)
                "demoted": "#FF1744"        # Red
            }
            color = status_colors.get(cert, "#9E9E9E")
            cert_label = cert.upper().replace("_", " ")
            
            # Qualified ID
            qid = cert_registry.get_qualified_id(selected_bundle["bundle_id"])
            st.markdown(f"### 🏷️ **{qid}**")
            st.markdown(f"**Optimization Status:** <span style='color:{color}'>{cert_label}</span>", unsafe_allow_html=True)
            
            # --- 2. BENCHMARK METRICS (Sniper PnL Only) ---
            st.markdown("#### 🎯 Sniper Optimization Target")
            
            # Get Benchmarks
            bench_service = BenchmarkService()
            # We assume Tier is available in bundle or manifest. If unsure, default to Unknown for now.
            # In a full impl, we'd read manifest['tier']
            tier = selected_bundle.get("tier", "UNKNOWN")
            bench = bench_service.get_benchmark(selected_bundle.get("symbol"), selected_bundle.get("timeframe"), tier)
            
            # Get Actuals from Cert Registry if available
            cert_entry = cert_registry.data.get(selected_bundle["bundle_id"], {})
            metrics = cert_entry.get("metrics", {})
            
            # Default Actuals (PLACEHOLDERS if not yet run)
            # If no metrics, show 0.0 or N/A
            actual_pnl = metrics.get("actual_pnl", 0.0)
            m1, m2 = st.columns(2)
            with m1:
                # PnL Metric
                target_pnl = bench["target_pnl"]
                delta_pnl = round(actual_pnl - target_pnl, 2)
                st.metric(
                    label="Sniper Backtest PnL",
                    value=f"{actual_pnl:.2f}",
                    delta=f"{delta_pnl:.2f} (Target {target_pnl:.2f})",
                    delta_color="normal"
                )
            with m2:
                # Potential/Tier
                st.metric(label="Tier Potential", value=tier, delta="Benchmark Class", delta_color="off")
                
            st.progress(min(1.0, max(0.0, actual_pnl / (bench["target_pnl"] or 1.0))), text="Optimization Progress (PnL)")

            # --- 3. TIMELINE (Simplified) ---
            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("📦 **Foundry**")
                st.caption("Packaged & Ready")
                st.write("✅")
                    
            with c2:
                st.markdown("🎯 **Sniper**")
                st.caption("Benchmark & Optimize")
                if cert == "candidate":
                    st.write("🏃 In Progress...")
                else:
                    st.write("✅ **PASSED**")
            
            # --- 4. MANUAL SNIPER CHECK (User Request) ---
            st.markdown("---")
            st.markdown("#### 🔬 Manual Verification")
            st.caption("Check bundle performance with your own hands.")
            
            col_run, col_res = st.columns([1, 2])
            with col_run:
                if st.button("▶️ Run Sniper Check", key="btn_run_sniper"):
                    with st.spinner("Running Sniper Simulation..."):
                        # We use scenario_id or bundle_id. analysis uses scenario_id usually for packs,
                        # but here we might want single bundle. 
                        # analyze_pack_performance takes scenario_id.
                        # If bundle has scenario_id, use it. Else use bundle_id as scenario (if compatible).
                        # CAUTION: analyze_pack_performance aggregates by scenario_id.
                        sid = selected_bundle.get("scenario_id")
                        if sid:
                            report = analyze_pack_performance(sid)
                            st.session_state["last_sniper_report"] = report
                        else:
                            st.error("No Scenario ID found for this bundle.")
            
            with col_res:
                if "last_sniper_report" in st.session_state:
                    rep = st.session_state["last_sniper_report"]
                    # If report allows access to dict or attributes
                    # Check if it matches current selection
                    if rep.scenario_id == selected_bundle.get("scenario_id"):
                        st.success("Sniper Result:")
                        sub_c1, sub_c2 = st.columns(2)
                        sub_c1.metric("Sim PnL", f"{rep.pnl_pct:.2f}%")
                        sub_c2.metric("Sim WinRate", f"{rep.win_rate:.0%}")
                    else:
                        st.info("Run check to see results.")

            # Cert Registry Data
            cert_entry = cert_registry.data.get(selected_bundle["bundle_id"])
            if cert_entry:
                st.markdown("---")
                st.markdown("#### Certification Details")
                st.json(cert_entry)
        
        with tab4:
            if bundle_files.get("qc_report"):
                st.json(bundle_files["qc_report"])
            else:
                st.warning("qc_report.json not found")
        
        with tab5:
            if bundle_files.get("event_row"):
                st.json(bundle_files["event_row"])
            else:
                st.warning("event_row.json not found")
        
        with tab6:
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
