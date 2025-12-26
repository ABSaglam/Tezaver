"""
Foundry Tab - Dökümhane Bundle Browser
=======================================

UI for browsing ApprovedRallyBundle packages.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import importlib
from pathlib import Path

from tezaver.foundry.bundle_index import scan_bundles, filter_bundles, load_bundle_files
from tezaver.matrix.adapters.candidate_registry import CandidateRegistry
import tezaver.foundry.configuration_service
importlib.reload(tezaver.foundry.configuration_service)
from tezaver.foundry.configuration_service import ConfigurationService
from tezaver.foundry.audit_service import AuditService
from tezaver.foundry.clustering_service import ClusteringService
from tezaver.foundry.archetype_storyteller import ArchetypeStoryteller
# from tezaver.matrix.sniper.benchmark_service import BenchmarkService # Removed/Missing
# from tezaver.sniper.sniper_backtest_v2 import analyze_pack_performance # Removed/Missing


@st.cache_data(ttl=60)
def cached_scan_bundles_v2():
    """Cached bundle scanning (v2)."""
    return scan_bundles()


def render_foundry_page():
    """Main render function for Foundry tab."""
    st.title("🏭 Dökümhane")
    
    tab_inv, tab_gov, tab_alc = st.tabs(["📦 Envanter", "⚖️ Karar Defteri", "🧪 Simyacı"])
    
    with tab_inv:
        _render_inventory_tab()
        
    with tab_gov:
        _render_governance_tab()
        
    with tab_alc:
        _render_alchemist_tab()

def _render_alchemist_tab():
    """Render The Alchemist (Clustering) Tab."""
    st.markdown("### 🧪 Simyacı: Arketip Keşfi")
    st.info("Bu modül, tekil paketleri analiz ederek ortak desenleri (Arketipleri/Ruhları) ortaya çıkarır.")
    
    # 1. Select Cohort
    df_bundles = cached_scan_bundles_v2()
    
    if not df_bundles.empty:
        c1, c2, c3 = st.columns(3)
        with c1:
            symbols = sorted(df_bundles["symbol"].unique().tolist())
            sel_sym = st.selectbox("Sembol (Coin)", symbols, key="alc_sym")
        with c2:
            timeframes = sorted(df_bundles["timeframe"].unique().tolist())
            sel_tf = st.selectbox("Zaman Dilimi (TF)", timeframes, key="alc_tf")
        with c3:
            clusters_n = st.slider("Arketip Sayısı (K)", 2, 5, 3, key="alc_k")
            
        # Filter Cohort
        cohort = df_bundles[
            (df_bundles["symbol"] == sel_sym) & 
            (df_bundles["timeframe"] == sel_tf)
        ]
        
        st.markdown(f"**Havuz:** {len(cohort)} adet paket var.")
        
        if len(cohort) < 3:
            st.error("Analiz için en az 3 paket gerekli.")
            
        elif st.button("⚗️ Simyayı Başlat (Analyze)", type="primary"):
            with st.spinner("Damıtılıyor... (Distilling Essence)"):
                mixer = ClusteringService()
                storyteller = ArchetypeStoryteller()
                
                # Run Clustering
                result = mixer.cluster_bundles(cohort, n_clusters=clusters_n)
                
                if "error" in result:
                    st.error(result["error"])
                else:
                    # Display Archetypes
                    st.success("✨ Keşif Tamamlandı!")
                    
                    centroids = result["centroids"]
                    cols = st.columns(len(centroids))
                    
                    for i, cent in enumerate(centroids):
                        story = storyteller.tell_story(cent)
                        
                        with cols[i]:
                            st.markdown(f"#### {story['label']}")
                            st.caption(f"Risk: {story['risk_profile']}")
                            st.markdown(f"**{cent['count']}** Üye")
                            st.progress(cent['avg_gain']/20.0, text=f"Gain: {cent['avg_gain']:.1f}%") # Visual bar
                            st.progress(min(1.0, cent['avg_duration']/50.0), text=f"Dur: {int(cent['avg_duration'])} bars")
                            st.info(story['description'])
                            
                            with st.expander("Üye Listesi"):
                                st.write(cent['member_ids'])
    else:
        st.warning("Analiz için veri yok. Önce paketleme yapın.")

    st.divider()
    with st.expander("📘 Teknik Tasarım (Design Doc) v1.1"):
        try:
            # Resolve relative to this file: ../foundry/docs/archetype_design.md
            # tezaver/ui/foundry_tab.py -> parent=tezaver/ui -> parent.parent=tezaver
            base_dir = Path(__file__).resolve().parent.parent
            doc_path = base_dir / "foundry/docs/archetype_design.md"
            
            if doc_path.exists():
                st.markdown(doc_path.read_text(encoding="utf-8"))
            else:
                st.warning(f"Tasarım dokümanı bulunamadı: {doc_path}")
        except Exception as e:
            st.error(f"Doküman okunamadı: {e}")

def _render_governance_tab():
    """Render Governance (Karar Defteri) Tab."""
    config = ConfigurationService()
    audit = AuditService()
    
    subtab_rules, subtab_config, subtab_log = st.tabs(["📜 Anayasa Maddeleri", "⚙️ Konfigürasyon", "📙 Tutanaklar"])
    
    qc = config.get_qc_rules()
    pkg = config.get_packaging_rules()
    alc = config.get_alchemist_rules()

    with subtab_rules:
        st.markdown("### Dökümhane Anayasası")
        st.info("İşbu Anayasa, Revize Stüdyosu'ndan çıkan işlerin denetim ve üretim süreçlerini düzenler.")
        
        # Article 1: QC
        st.markdown("#### BÖLÜM 1: KALİTE VE DENETİM")
        st.markdown("**Madde 1 - Kabul Şartları ve Puanlama**")
        st.write(f"""
        **1.1. Puanlama Esası:** Herbir revizyon paketi, QC Gate v1 denetim motoru tarafından 100 üzerinden puanlanır. Onay için asgari **{qc.get('min_score', 60)}** puan gereklidir.
        
        **1.2. Kırmızı Çizgiler (Zorunlu Denetimler):** Aşağıdaki denetimlerden herhangi birinin başarısız olması durumunda, puan dikkate alınmaksızın paket reddedilir:
        *   a) **QC-010:** Fiyat geçmişi eksiksiz olmalı.
        *   b) **QC-040:** Olay, ana veri setinde (Rally Dataset) kayıtlı olmalı.
        *   c) **QC-050:** Giriş ve Olay zamanları mantıksal olarak tutarlı olmalı.
        
        **1.3. Denetim Modu:** {'Sistem **Katı Mod (Strict Mode)** ile çalışır; en ufak bir uyumsuzluk reddine sebebiyet verir.' if qc.get('strict_mode') else 'Sistem **Esnek Mod** ile çalışır; kritik olmayan hatalarda puan yeterliyse geçiş izni verilir.'}
        """)
        
        st.divider()
        
        # Article 2: Packaging
        st.markdown("#### BÖLÜM 2: ÜRETİM VE SEVKİYAT")
        st.markdown("**Madde 2 - Paketleme Standartları**")
        st.write(f"""
        **2.1. Yetkilendirilmiş Sınıflar:** Yalnızca **{', '.join(pkg.get('allowed_tiers', []))}** sertifika sınıfına sahip varlıklar üretim hattına alınır. Diğer sınıflar işleme kapatılmıştır.
        
        **2.2. Üretim Kotaları:** Kaynak verimliliği adına, her bir parite (Coin) ve zaman dilimi (TF) kombinasyonu için azami **{pkg.get('max_bundles_per_coin', 5)}** adet paket üretilmesine izin verilir.
        
        **2.3. İsimlendirme ve Etiketleme:** Üretilen tüm paketler, izlenebilirliği sağlamak amacıyla istisnasız `{pkg.get('naming_convention', 'STANDARD_V1')}` standardına uygun olarak etiketlenir.
        """)
        
        st.divider()
        
        # Article 3: Alchemy
        st.markdown("#### BÖLÜM 3: SİMYA VE KEŞİF (AR-GE)")
        st.markdown("**Madde 3 - Arketip Damıtma**")
        st.write(f"""
        **3.1. Havuz Büyüklüğü:** İstatistiksel anlamlılık için en az **{alc.get('min_cohort_size', 3)}** adet paket biriktirilmeden damıtma işlemi yapılamaz.
        
        **3.2. DNA Analizi:** Arketiplerin ayrıştırılmasında şu öznitelikler esas alınır: `{', '.join(alc.get('features', []))}`
        """)
        
    with subtab_config:
        st.subheader("⚙️ Sistem Ayarları")
        st.caption(f"Sürüm: {config.get_version()}")
        
        c1, c2 = st.columns(2)
        with c1:
            with st.expander("🛡️ Kalite Kontrol (QC)", expanded=True):
                 if "description" in qc: st.caption(qc["description"])
                 st.number_input("Min Geçme Puanı", value=qc.get("min_score", 60), disabled=True)
                 st.checkbox("Katı Mod (Strict)", value=qc.get("strict_mode", True), disabled=True)
                 st.multiselect("Zorunlu Kontroller", options=qc.get("mandatory_checks", []), default=qc.get("mandatory_checks", []), disabled=True)
                 
            with st.expander("⚗️ Simyacı Kuralları", expanded=True):
                 if "description" in alc: st.caption(alc["description"])
                 st.number_input("Min Havuz Boyutu", value=alc.get("min_cohort_size", 3), disabled=True)
                 st.number_input("Varsayılan K", value=alc.get("default_k", 3), disabled=True)
        
        with c2:
            with st.expander("📦 Paketleme Kuralları", expanded=True):
                 if "description" in pkg: st.caption(pkg["description"])
                 st.multiselect("İzin Verilen Tier'lar", options=pkg.get("allowed_tiers", []), default=pkg.get("allowed_tiers", []), disabled=True)
                 st.number_input("Max Paket / Coin", value=pkg.get("max_bundles_per_coin", 5), disabled=True)


    with subtab_log:
        st.subheader("📙 Tutanaklar (Audit Log)")
        logs = audit.read_recent_logs(limit=100)
        
        if logs:
            df_logs = pd.DataFrame(logs)
            st.dataframe(
                df_logs[["ts", "action", "subject", "verdict", "details"]],
                use_container_width=True,
                height=500
            )
        else:
            st.info("Henüz kayıt bulunmuyor. İşlem yapıldığında burada görünecektir.")

def _render_inventory_tab():
    """Render Existing Bundle Browser."""
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
    
    # Load Certification Status from Matrix Registry
    candidate_registry = CandidateRegistry()
    
    def get_stage(bid):
        c = candidate_registry.get(bid)
        return c.get("status", "foundry") if c else "foundry"
        
    df_bundles["certification"] = df_bundles["bundle_id"].apply(get_stage)
    
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
        
        from pathlib import Path
        bundle_dir = Path(selected_bundle["bundle_dir"])
        
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
                details = nar.get("details", {})
                
                # Header: The Soul (Label)
                st.markdown(f"### ✨ {nar.get('label', 'Unknown Archetype')}")
                st.caption(f"Risk Level: {nar.get('risk', 'Medium')}")
                
                # The Story (Description)
                st.info(nar.get('desc', 'No description available.'))
                
                st.markdown("---")
                
                # Centroid Metrics (The Structure)
                if "centroid" in details:
                    st.markdown("#### 🏗️ Archetype Structure (Centroid)")
                    cent = details["centroid"]
                    sc1, sc2, sc3 = st.columns(3)
                    with sc1:
                        st.metric("Avg Gain", f"{cent.get('gain', 0):.2f}%")
                    with sc2:
                        st.metric("Avg Duration", f"{int(cent.get('duration', 0))} bars")
                    with sc3:
                        st.metric("Group Size", f"{cent.get('count', 0)} members")
                
                # Cluster Members (The Constituents)
                if "cluster_members" in details:
                    members = details["cluster_members"]
                    with st.expander(f"📦 Archetype Members ({len(members)})"):
                        st.table(pd.DataFrame(members, columns=["Event ID"]))
                
                # Analysis Details
                if "htf_trend" in details:
                    st.markdown("---")
                    st.markdown("#### 🧠 Deep Analysis")
                    dc1, dc2, dc3 = st.columns(3)
                    dc1.metric("HTF Context", details.get("htf_trend", "N/A"))
                    dc2.metric("RSI Slope", details.get("rsi_slope", "N/A"))
                    dc3.metric("Volume", details.get("volume", "N/A"))
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
            # cert_registry = CandidateRegistry() # Already loaded
            qid = candidate_registry.get_qualified_id(selected_bundle["bundle_id"])
            st.markdown(f"### 🏷️ **{qid}**")
            st.markdown(f"**Optimization Status:** <span style='color:{color}'>{cert_label}</span>", unsafe_allow_html=True)
            
            # --- 2. BENCHMARK METRICS (Sniper PnL Only) ---
            st.markdown("#### 🎯 Sniper Optimization Target")
            
            # Get Benchmarks
            # bench_service = BenchmarkService()
            # We assume Tier is available in bundle or manifest. If unsure, default to Unknown for now.
            # In a full impl, we'd read manifest['tier']
            tier = selected_bundle.get("tier", "UNKNOWN")
            # bench = bench_service.get_benchmark(selected_bundle.get("symbol"), selected_bundle.get("timeframe"), tier)
            
            # Get Actuals from Cert Registry if available
            cert_entry = candidate_registry.data.get(selected_bundle["bundle_id"], {})
            metrics = cert_entry.get("metrics", {})
            
            # Default Actuals (PLACEHOLDERS if not yet run)
            # If no metrics, show 0.0 or N/A
            actual_pnl = metrics.get("actual_pnl", 0.0)
            
            st.info("Benchmark Service temporarily disabled in UI Refactor.")
            # m1, m2 = st.columns(2)
            # with m1:
            #     # PnL Metric
            #     target_pnl = bench["target_pnl"]
            #     delta_pnl = round(actual_pnl - target_pnl, 2)
            #     st.metric(
            #         label="Sniper Backtest PnL",
            #         value=f"{actual_pnl:.2f}",
            #         delta=f"{delta_pnl:.2f} (Target {target_pnl:.2f})",
            #         delta_color="normal"
            #     )
            # with m2:
            #     # Potential/Tier
            #     st.metric(label="Tier Potential", value=tier, delta="Benchmark Class", delta_color="off")
                
            # st.progress(min(1.0, max(0.0, actual_pnl / (bench["target_pnl"] or 1.0))), text="Optimization Progress (PnL)")

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
            
            # Cert Registry Data
            cert_entry = candidate_registry.data.get(selected_bundle["bundle_id"])
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
                
        with tab7:
            # New Tab: Raw Files Layout
            import os
            files = [str(f.name) for f in bundle_dir.iterdir()]
            st.write(files) # Simple list for now


