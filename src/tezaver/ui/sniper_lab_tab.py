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
from tezaver.foundry.bundle_packer_v2 import load_pack

def render_sniper_lab_page():
    """Main render function for Sniper Lab tab."""
    import importlib
    import tezaver.sniper.sniper_backtest_v2
    importlib.reload(tezaver.sniper.sniper_backtest_v2)
    from tezaver.sniper.sniper_backtest_v2 import analyze_pack_performance
    
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
        col1.metric("Toplam İşlem", report.get("total_trades", 0))
        col2.metric("Başarı Oranı", f"{report.get('win_rate', 0):.1f}%")
        col3.metric("Toplam P&L", f"{report.get('pnl_pct', 0):.2f}%")
        col4.metric("Max Drawdown", f"{report.get('max_drawdown', 0):.2f}%")

        # Feedback Area
        st.markdown("### 💡 Sniper Geri Bildirimi")
        for fb in report["feedback"]:
            st.info(fb)
            
        if report["suggested_params"]:
             st.success(f"**Önerilen Değişiklikler:** {report['suggested_params']}")

        # Trades Table
        st.markdown("---")
        st.markdown("### 📋 İşlem Geçmişi (Ledger)")
        trades_df = pd.DataFrame(report["trades"])
        if not trades_df.empty:
            # Table
            display_df = trades_df.copy()
            # Clean up for display
            if "pnl_eff_pct" in display_df.columns:
                 display_df = display_df.rename(columns={"pnl_eff_pct": "PnL %", "exit_reason": "Çıkış Nedeni", "equity_after": "Sermaye"})
            
            st.dataframe(display_df[["trade_id", "PnL %", "Çıkış Nedeni", "Sermaye"]], use_container_width=True)

            # P&L & Equity Chart
            fig = go.Figure()
            
            # Bar chart for P&L
            fig.add_trace(go.Bar(
                x=trades_df.index,
                y=trades_df["pnl_eff_pct"],
                marker_color=trades_df["pnl_eff_pct"].apply(lambda x: '#26a69a' if x > 0 else '#ef5350'),
                name="İşlem Bazlı P&L (%)",
                yaxis="y"
            ))
            
            # Line chart for Equity
            fig.add_trace(go.Scatter(
                x=trades_df.index,
                y=trades_df["equity_after"],
                mode='lines+markers',
                name="Sermaye Eğrisi",
                line=dict(color='#ff9800', width=3),
                yaxis="y2"
            ))

            fig.update_layout(
                title="Performans Analizi (Arena Mode)",
                template="plotly_dark",
                height=450,
                hovermode='x unified',
                yaxis=dict(title="PnL %", side="left"),
                yaxis2=dict(title="Equity", side="right", overlaying="y", showgrid=False)
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Approve for WAR button
        st.markdown("---")
        if st.button("🎖️ Sniper Onayı Ver ve WAR'a Hazırla", use_container_width=True):
            st.balloons()
            st.success("✅ Paket Sniper onayından geçti. Matrix War havuzunda önceliklendirildi.")
