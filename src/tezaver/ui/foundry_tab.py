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

# from tezaver.foundry.bundle_index import scan_bundles, filter_bundles, load_bundle_files
# from tezaver.matrix.adapters.candidate_registry import CandidateRegistry
# import tezaver.foundry.configuration_service
# import tezaver.foundry.clustering_service
# import tezaver.foundry.bundle_index
# import tezaver.foundry.archetype_storyteller
# importlib.reload(tezaver.foundry.configuration_service)
# importlib.reload(tezaver.foundry.clustering_service)
# importlib.reload(tezaver.foundry.bundle_index)
# importlib.reload(tezaver.foundry.archetype_storyteller)
import tezaver.foundry.archetype_service
importlib.reload(tezaver.foundry.archetype_service)

# from tezaver.foundry.configuration_service import ConfigurationService
# from tezaver.foundry.audit_service import AuditService
# from tezaver.foundry.clustering_service import ClusteringService
# from tezaver.foundry.archetype_storyteller import ArchetypeStoryteller
from tezaver.foundry.archetype_service import ArchetypeService
# from tezaver.matrix.sniper.benchmark_service import BenchmarkService # Removed/Missing
# from tezaver.sniper.sniper_backtest_v2 import analyze_pack_performance # Removed/Missing


# cached_scan_bundles_v2 removed


def render_foundry_page():
    """Main render function for Foundry tab."""
    st.title("🏭 Dökümhane")
    
    # Inventory removed, Alchemist Moved to Ony, Governance Moved to Alchemist
    # Only Archetypes remain
    _render_archetypes_tab()

# _render_alchemist_tab removed
# _render_governance_tab removed


# Inventory logic has been removed as per "The Great Cleanup" request.
# The data bundles persist on disk for Alchemist usage.





def _render_archetypes_tab():
    """Render Archetypes (Piyasa Karakterleri) Tab with Live Data."""
    st.markdown("### 🎭 Piyasa Karakter Envanteri")
    
    # 1. CONTROLS
    service = ArchetypeService()
    coins = service.get_available_coins()
    
    c1, c2 = st.columns([1, 1])
    with c1:
        sel_coin = st.selectbox("Coin Seçiniz:", coins, index=0 if coins else None, key="arch_coin_sel")
    
    if not sel_coin:
        st.warning("Lütfen bir coin seçin.")
        return

    # Helper: Get TFs for this coin
    tfs = service.get_available_timeframes(sel_coin)
    with c2:
        sel_tf = st.selectbox("Zaman Dilimi (TF):", tfs, index=0 if tfs else None, key="arch_tf_sel")

    if not sel_tf:
        st.warning("Bu coin için veri bulunamadı.")
        return

    # 2. LOAD DATA
    data_map = service.scan_coin_archetypes(sel_coin, timeframe=sel_tf)
    tiers = data_map["tiers"]
    archs = data_map["archetypes"]
    
    # 3. MAIN TABS
    tab_tier, tab_win, tab_lose, tab_cipher, tab_const = st.tabs(["💎 Tiers", "🏆 Kazananlar", "💀 Kaybedenler", "🔐 Şifreler", "📜 Anayasa"])

    # Shared Render Helper
    def render_list(items, empty_msg="Kayıt bulunamadı."):
        if items:
            df = pd.DataFrame(items)
            df['time'] = df['time'].dt.strftime('%Y-%m-%d %H:%M')
            df['gain'] = df['gain'].map('{:.1f}%'.format)
            df['rsi'] = df['rsi'].map('{:.1f}'.format)
            df['vol'] = df['vol'].map('{:.1f}x'.format)
            st.dataframe(df, use_container_width=True, hide_index=True, height=400)
            st.caption(f"Toplam: {len(items)} adet")
        else:
            st.info(empty_msg)

    # ---------------------------------------------------------
    # CIPHER TAB (New)
    # ---------------------------------------------------------
    with tab_cipher:
        from tezaver.smyrna.alchemist_engine import AlchemistEngine
        engine = AlchemistEngine()
        ciphers = engine.load_master_ciphers()
        
        if ciphers:
             st.success(f"📚 {len(ciphers)} Master Cipher (Üretim Bandında)")
             
             cols = st.columns(3)
             for i, mc in enumerate(ciphers):
                 with cols[i % 3]:
                     with st.expander(f"🔐 {mc.name}", expanded=True):
                         st.metric("Win Rate", f"%{mc.win_rate*100:.0f}")
                         st.metric("Avg Gain", f"%{mc.avg_gain_pct:.1f}")
                         st.caption(f"Score: {mc.conquest_score}")
                         st.code(mc.sequence_signature, language="text")
                         if st.button("Paketle (Üretim)", key=f"btn_pack_{i}"):
                             st.toast("Paketleme servisi henüz aktif değil.")
        else:
             st.info("Henüz üretilmiş şifre yok. Simyacı laboratuvarına gidiniz.")

    # ---------------------------------------------------------
    # TIER TAB
    # ---------------------------------------------------------
    with tab_tier:
        # Sub-tabs for Tiers
        tt_d, tt_g, tt_s, tt_b = st.tabs(["💎 ELMAS", "🥇 ALTIN", "🥈 GÜMÜŞ", "🥉 BRONZ"])
        
        with tt_d: render_list(tiers["DIAMOND 💎"])
        with tt_g: render_list(tiers["GOLD 🥇"])
        with tt_s: render_list(tiers["SILVER 🥈"])
        with tt_b: render_list(tiers["BRONZE 🥉"])

    # ---------------------------------------------------------
    # WINNERS TAB
    # ---------------------------------------------------------
    with tab_win:
        w_tabs = st.tabs([
            "GRIND 🪜", "GUILLOTINE 🩸", "SUPERNOVA 💥", 
            "PHOENIX 🔥", "NINJA 🥷", "SURFER 🏄‍♂️", "OTHER 👽"
        ])
        
        def render_arch_info(name, desc, dna, strat, items):
            c1, c2 = st.columns([1, 2])
            with c1:
                st.info(f"**{name}**")
                st.markdown(f"- {desc}")
                st.markdown(f"- **DNA:** {dna}")
                st.markdown(f"- **Hedef:** {strat}")
            with c2:
                render_list(items)

        with w_tabs[0]: render_arch_info("GRIND", "Sessiz tırmanış.", "<1.5x Hacim", "AL/UNUT", archs["GRIND"])
        with w_tabs[1]: render_arch_info("GUILLOTINE", "V-Dönüşü.", "RSI < 25", "SNIPE", archs["GUILLOTINE"])
        with w_tabs[2]: render_arch_info("SUPERNOVA", "Patlama.", ">5x Hacim", "MOMENTUM", archs["SUPERNOVA"])
        with w_tabs[3]: render_arch_info("PHOENIX", "İkinci Dalga.", "Supernova+4h", "DİP", archs["PHOENIX"])
        with w_tabs[4]: render_arch_info("NINJA", "Sinsi Toplama.", "RSI 30-40, Ölü", "AKÜMÜLE", archs["NINJA"])
        with w_tabs[5]: render_arch_info("SURFER", "Trend Takibi.", "RSI > 70", "İZ SÜR", archs["SURFER"])
        with w_tabs[6]: render_arch_info("OTHER", "Melez/Tanımsız.", "Uyumsuz", "İZLE", archs["OTHER"])

    # ---------------------------------------------------------
    # LOSERS TAB
    # ---------------------------------------------------------
    with tab_lose:
        l_tabs = st.tabs(["STORM ⛈️", "TRAP 🪤", "DEAD 🪦", "NEWS 📰"])
        
        with l_tabs[0]: st.error("STORM: Stop Patlatma (Whipsaw). YASAK.")
        with l_tabs[1]: st.error("TRAP: Fake Breakout. YASAK.")
        with l_tabs[2]: st.error("DEAD: Hacimsiz. BEKLE.")
        with l_tabs[3]: st.error("NEWS: Gap Riski. YASAK.")

    # ---------------------------------------------------------
    # CONSTITUTION TAB
    # ---------------------------------------------------------
    with tab_const:
        try:
            doc_path = Path("/Users/alisaglam/.gemini/antigravity/brain/f5d38091-3f29-4665-ba21-dbbe70827774/market_archetypes.md")
            if doc_path.exists():
                st.markdown(doc_path.read_text(encoding="utf-8"))
            else:
                st.warning("Dosya bulunamadı.")
        except Exception as e:
            st.error(f"Hata: {e}")
