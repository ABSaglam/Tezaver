"""
Sniper Lab Tab - Geri Bildirimli Backtest Laboratuvarı
=====================================================

UI for running Sniper V2 simulations on Foundry Story Packs.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import plotly.graph_objects as go

from tezaver.foundry.bundle_packer_v2 import load_pack
from tezaver.sniper.sniper_backtest_v2 import analyze_pack_performance

def render_sniper_lab_page():
    """Main render function for Sniper Lab tab."""
    st.title("🧪 Sniper Lab - Backtest & Refinement")
    st.caption("Dökümhane Hikaye Paketlerini test et ve geri bildirim al.")

    # List available story packs
    packs_dir = Path(".tezaver_matrix/foundry/story_packs")
    if not packs_dir.exists() or not list(packs_dir.glob("*.json")):
        st.warning("Henüz Hikaye Paketi oluşturulmamış. Önce Dökümhane'de paketleme yapın.")
        return

    pack_files = list(packs_dir.glob("*.json"))
    pack_names = [f.stem for f in pack_files]
    
    selected_scenario = st.selectbox("Hikaye Paketi Seç", pack_names)
    
    if st.button("🚀 Laboratuvar Testini Başlat", type="primary", use_container_width=True):
        with st.spinner(f"{selected_scenario} hikayesi simüle ediliyor..."):
            report = analyze_pack_performance(selected_scenario)
            st.session_state["sniper_lab_report"] = report.to_dict()

    if "sniper_lab_report" in st.session_state:
        report = st.session_state["sniper_lab_report"]
        
        # Metrics Row
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Toplam İşlem", report["total_trades"])
        col2.metric("Başarı Oranı", f"{report['win_rate']:.1f}%")
        col3.metric("Ort. P&L", f"{report['avg_pnl']:.2f}%")
        col4.metric("Profit Factor", f"{report['profit_factor']:.2f}")

        # Feedback Area
        st.markdown("### 💡 Sniper Geri Bildirimi")
        for fb in report["feedback"]:
            st.info(fb)
            
        if report["suggested_params"]:
             st.success(f"**Önerilen Değişiklikler:** {report['suggested_params']}")

        # Trades Table
        st.markdown("---")
        st.markdown("### 📋 İşlem Detayları")
        trades_df = pd.DataFrame(report["trades"])
        if not trades_df.empty:
            st.dataframe(trades_df[["bundle_id", "entry_ts", "exit_ts", "pnl_pct", "status"]], use_container_width=True)

            # P&L Chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=trades_df["bundle_id"],
                y=trades_df["pnl_pct"],
                marker_color=trades_df["pnl_pct"].apply(lambda x: 'green' if x > 0 else 'red'),
                name="P&L %"
            ))
            fig.update_layout(title="Hiyerarşik P&L Dağılımı", template="plotly_dark", height=300)
            st.plotly_chart(fig, use_container_width=True)
        
        # Approve for WAR button
        st.markdown("---")
        if st.button("🎖️ Sniper Onayı Ver ve WAR'a Hazırla", use_container_width=True):
            st.balloons()
            st.success("✅ Paket Sniper onayından geçti. Matrix War havuzunda önceliklendirildi.")
