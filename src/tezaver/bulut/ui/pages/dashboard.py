# Tezaver Bulut - Streamlit Dashboard
"""
Dashboard page for Bulut UI.
"""

import streamlit as st
from datetime import datetime, timezone

from tezaver.bulut.core.context import get_context


def render_dashboard():
    """Render main dashboard."""
    ctx = get_context()
    
    st.title("🌩️ Tezaver Bulut Dashboard")
    st.caption("Cloud Trading System v0.01")
    
    # =========================================================================
    # Trade Lock Status
    # =========================================================================
    st.subheader("🔒 Trade Status")
    
    ctx.update_trade_lock()
    
    if ctx.state.trade_locked:
        st.error(f"⛔ **TRADE LOCKED**: {ctx.state.trade_lock_reason}")
    else:
        st.success("✅ **TRADE UNLOCKED** - System ready for trading")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Pattern Pack",
            "Loaded ✓" if ctx.state.pattern_pack_loaded else "Missing ✗",
        )
    
    with col2:
        st.metric(
            "Open Positions",
            f"{ctx.state.open_positions_count} / {ctx.config.max_open_positions}",
        )
    
    with col3:
        st.metric(
            "Notional USDT",
            f"${ctx.state.total_notional_usdt:.2f} / ${ctx.config.max_total_notional_usdt:.2f}",
        )
    
    # =========================================================================
    # Latest Ranking
    # =========================================================================
    st.subheader("📊 Latest Ranking")
    
    # Import ranking cache
    from tezaver.bulut.api.routes_ranking import _latest_ranking
    
    if _latest_ranking is None:
        st.info("No ranking data. Click 'Run Scan' to generate.")
    else:
        from tezaver.bulut.schemas.ranking_snapshot_v1 import RankingSnapshotV1
        ranking = RankingSnapshotV1.from_dict(_latest_ranking)
        
        if ranking:
            st.caption(f"Cycle: {ranking.cycle_ts.isoformat()} | Universe: {ranking.universe_size} | Threshold: {ranking.threshold}")
            
            shortlist = ranking.shortlist
            if shortlist:
                import pandas as pd
                df = pd.DataFrame([
                    {
                        "Symbol": c.symbol,
                        "Score": c.score,
                        "Pattern": c.components.get("pattern", 0),
                        "Trend": c.components.get("trend", 0),
                        "Risk": c.components.get("risk", 0),
                        "Flags": ", ".join(c.flags),
                    }
                    for c in shortlist
                ])
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("Shortlist is empty (no candidates above threshold)")
    
    # Manual scan button
    if st.button("🔄 Run Scan"):
        with st.spinner("Scanning..."):
            from tezaver.bulut.engine.scanner import run_scan
            
            ctx.load_pattern_pack()
            pack = ctx.pattern_loader.load_latest_parsed()
            ranking = run_scan(ctx.config, pack)
            
            # Update cache
            import tezaver.bulut.api.routes_ranking as ranking_routes
            ranking_routes._latest_ranking = ranking.to_dict()
            
            ctx.telemetry.emit_ranking_snapshot(ranking.to_dict())
            ctx.state.last_scan_ts = ranking.cycle_ts
        
        st.success(f"Scan complete! Found {len(ranking.shortlist)} candidates in shortlist.")
        st.rerun()
    
    # =========================================================================
    # Config Summary
    # =========================================================================
    with st.expander("⚙️ Configuration"):
        config = ctx.config.to_dict()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Exchange Settings**")
            st.write(f"- Exchange: `{config['exchange']}`")
            st.write(f"- Market: `{config['market']}`")
            st.write(f"- Direction: `{config['direction']}`")
            st.write(f"- Base TF: `{config['base_tf']}`")
            st.write(f"- Derived TFs: `{config['derived_tfs']}`")
        
        with col2:
            st.markdown("**Risk Limits**")
            st.write(f"- Max Open Positions: `{config['max_open_positions']}`")
            st.write(f"- Max Total Notional: `${config['max_total_notional_usdt']}`")
            st.write(f"- Max Cell Notional: `${config['max_cell_notional_usdt']}`")
            st.write(f"- Scan Top-K: `{config['scan_topk']}`")
            st.write(f"- Scan Min Score: `{config['scan_min_score']}`")
    
    # =========================================================================
    # Pattern Pack Info
    # =========================================================================
    with st.expander("📦 Pattern Pack"):
        summary = ctx.pattern_loader.get_pack_summary()
        
        if summary.get("loaded"):
            st.success("Pattern pack loaded")
            st.write(f"- Pack ID: `{summary.get('pack_id')}`")
            st.write(f"- Hash: `{summary.get('hash')}`")
            st.write(f"- Symbols: `{summary.get('symbol_count')}`")
            st.write(f"- Timeframes: `{summary.get('timeframes')}`")
        else:
            st.warning("No pattern pack loaded")
            st.write(f"Expected path: `{ctx.config.pattern_pack_dir}`")
            st.write("Place a valid `pattern_pack_v1.json` file in this directory.")


if __name__ == "__main__":
    render_dashboard()
