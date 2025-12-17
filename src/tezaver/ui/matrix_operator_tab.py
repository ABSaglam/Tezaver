# Matrix Operator Tab v1
"""
Matrix Operator Tab for Streamlit.

Shows Strategy Board and Live Cluster preview in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import os
import streamlit as st

from tezaver.matrix.profile_board import build_profile_board, ProfileBoardRow
from tezaver.matrix.live.live_cluster import build_live_cluster_from_profile_board


def _render_strategy_board_table(rows: List[ProfileBoardRow]) -> None:
    """
    Render Strategy Board table in Streamlit.
    """
    if not rows:
        st.info("Henüz CoinPage V2 profili bulunamadı. profile_tools CLI'ını kontrol et.")
        return

    # Prepare data for display
    data = []
    for r in rows:
        data.append({
            "Coin": r.symbol,
            "TF": r.timeframe,
            "Profil": r.profile_id,
            "Durum": r.status,
            "PnL %": f"{r.pnl_pct:.2f}" if r.pnl_pct is not None else "-",
            "İşlem": r.trades if r.trades is not None else "-",
            "Max Risk %": f"{r.max_risk_per_trade * 100:.2f}" if r.max_risk_per_trade is not None else "-",
            "LIVE?": "✅ Evet" if r.live_eligible else "❌ Hayır",
        })

    st.dataframe(data, use_container_width=True)

    total_profiles = len(rows)
    live_eligible = sum(1 for r in rows if r.live_eligible)
    st.caption(f"Toplam profil: {total_profiles} | LIVE uygun: {live_eligible}")


def _render_live_cluster_preview(
    rows: List[ProfileBoardRow],
    initial_capital: float,
    risk_mode: str,
) -> None:
    """
    Render Live Cluster preview from live-eligible profiles.
    """
    st.subheader("📡 Live Cluster Önizleme")

    st.caption(
        "Strategy Board'dan LIVE'a uygun profilleri alır ve "
        "**Matrix Live Cluster** içinde hangi cell'lerin açılacağını gösterir. "
        "Şu anda *simülasyon / read-only* moddadır."
    )

    try:
        cluster = build_live_cluster_from_profile_board(
            initial_capital=initial_capital,
            risk_mode=risk_mode,
        )
    except Exception as exc:
        st.error(
            "Live Cluster oluşturulurken hata oluştu.\n\n"
            f"Detay: {exc}"
        )
        return

    cells = cluster.list_cells()
    if not cells:
        st.warning("Şu anda LIVE için uygun cell bulunamadı.")
        return

    # Build preview data
    preview = []
    for cell in cells:
        # Find corresponding row for max_risk
        max_risk = None
        for r in rows:
            if (r.symbol == cell.symbol and 
                r.timeframe == cell.timeframe and
                r.profile_id == cell.profile_id):
                max_risk = r.max_risk_per_trade
                break
        
        equity = cluster.get_equity(cell.symbol, cell.timeframe, cell.profile_id)

        preview.append({
            "Coin": cell.symbol,
            "TF": cell.timeframe,
            "Profil": cell.profile_id,
            "Max Risk %": f"{max_risk * 100:.2f}" if max_risk else "-",
            "Sermaye": f"{equity:.2f}",
        })

    st.table(preview)
    st.success(f"Toplam {len(cells)} cell LIVE'a hazır!")


def render_matrix_operator_tab() -> None:
    """
    Main entry: Matrix Operator panel (Live Only).
    """
    st.markdown("## 🧭 Matrix Operator")
    
    # === Strategy Board (common, collapsible) ===
    try:
        rows = build_profile_board()
    except Exception as e:
        st.error(f"Strategy Board yüklenirken hata: {e}")
        rows = []
    
    with st.expander("📋 Strategy Board | Strateji Panosu", expanded=False):
        _render_strategy_board_table(rows)
    
    st.divider()
    
    # Always render Live section
    _render_live_section_v2(rows)




def _render_live_section_v2(rows: List[ProfileBoardRow]) -> None:
    """Live mode - Live Cluster config and monitoring."""
    st.header("📡 Live Mode – Cluster Yapılandırma")
    st.caption(
        "Live için uygun profilleri (status=APPROVED) bir cluster'a toplar. "
        "Şimdilik simülasyon amaçlı."
    )
    
    # =========================================================================
    # SIDEBAR ROUTING: Expander Allow Mapping
    # =========================================================================
    ALLOW = {
        "matrix": {
            "🎬 Trade Replay | İşlem Tekrarı",
            "🩺 System Health Summary | Sistem Sağlık Özeti",
            "🎮 Live Gate Status | Canlı Kapı Durumu",
            "🟢 Live Freshness / Lag | Canlı Veri Tazeliği",
            "🔁 Live Loop Control | Canlı Döngü Kontrolü",
        },
        "operation": {
            "🔁 Live Loop Control | Canlı Döngü Kontrolü",
            "🧭 Live Ops Console | Canlı Operasyon Konsolu",
            "📊 Cycles Report | Döngü Raporu",
        },
        "strategy": {
            "📋 Strategy Board | Strateji Panosu",
        },
        "security": {
            "⚙️ Exchange & Arm Controls | Borsa & Yetkilendirme Kontrolleri",
            "🔐 Secrets Vault | Gizli Anahtar Kasası",
            "🧯 Auto-Incident on BLOCK | Otomatik Olay Kaydı",
        },
        "account": {
            "🧹 Dust & Position Hygiene | Bakiye & Pozisyon Temizliği",
        },
        "events": {
            "📊 Events Explorer | Olay Gezgini",
            "📜 NDJSON Tail Viewer | NDJSON Log Görüntüleyici",
            "🧾 Last Orders (per cell) | Son Emirler (hücre bazında)",
        },
        "bundles": {
            "📦 Incident Bundles | Olay Paketi Arşivi",
        },
        "proof": {
            "✅ Closed Bar Proof | Kapalı Bar Kanıtı",
            "🔀 Closed-bar Router | Kapalı Bar Yönlendiricisi",
            "🧾 Proof+Router (E2E) | Kanıt+Yönlendirici (Uçtan Uca)",
            "🧾 Proof+Router+Cluster (E2E) | Kanıt+Yönlendirici+Küme (Uçtan Uca)",
        },
        "debug": {
            "🔧 Advanced Debug | Gelişmiş Hata Ayıklama",
        },
    }
    
    # Get active page and allowed expanders
    active_page = st.session_state.get("nav_page", "matrix")
    allowed_expanders = ALLOW.get(active_page, set())
    
    # Helper for conditional rendering
    def _is_allowed(title: str) -> bool:
        """Check if expander should be rendered."""
        return title in allowed_expanders
    
    # =========================================================================
    # Live Loop Control (NEW)
    # =========================================================================
    with st.expander("🔁 Live Loop Control | Canlı Döngü Kontrolü", expanded=True):
        from tezaver.matrix.live.live_loop_service import LiveLoopService
        from tezaver.matrix.live.live_loop import TICK_POLICY_ON_CLOSED_BAR, TICK_POLICY_ON_ANY_NEW_BAR
        
        service = LiveLoopService.get()
        status = service.status()
        
        # Status line
        if status.running:
            st.success(f"RUNNING ✅ | polls={status.polls} ticks={status.ticks} skips={status.skips}")
        else:
            st.warning(f"STOPPED ⛔ | polls={status.polls} ticks={status.ticks} skips={status.skips}")
        
        if status.last_error:
            st.error(f"❌ Error: {status.last_error}")
        
        st.divider()
        
        # Controls
        col1, col2, col3 = st.columns(3)
        with col1:
            use_real = st.checkbox("🌐 Use REAL Binance", value=False, key="loop_use_real")
            tf_override = st.selectbox(
                "Timeframe",
                ["inherit", "1m", "15m"],
                key="loop_tf_override"
            )
        with col2:
            tick_policy = st.radio(
                "Tick Policy",
                [TICK_POLICY_ON_CLOSED_BAR, TICK_POLICY_ON_ANY_NEW_BAR],
                key="loop_tick_policy"
            )
        with col3:
            poll_interval = st.slider("Poll interval (s)", 1, 15, 5, key="loop_poll_interval")
            until_next_closed = st.checkbox("Until next closed", value=False, key="loop_until_next_closed")
        
        # Start/Stop buttons
        col_start, col_stop = st.columns(2)
        with col_start:
            if st.button("✅ Start Loop", type="primary", disabled=status.running, use_container_width=True):
                # Build cells from live eligible profiles
                live_cells = []
                for row in rows:
                    if row.live_eligible:
                        tf = row.timeframe if tf_override == "inherit" else tf_override
                        live_cells.append((row.symbol, tf))
                
                if live_cells:
                    # Use until_next_closed to set max_runtime
                    max_runtime = 3600.0 if not until_next_closed else 900.0
                    
                    started = service.start(
                        cells=live_cells[:5],  # Limit to 5 cells
                        use_real=use_real,
                        tick_policy=tick_policy,
                        poll_interval=float(poll_interval),
                        max_runtime=max_runtime,
                    )
                    if started:
                        st.success("Loop started!")
                        st.rerun()
                else:
                    st.warning("No live eligible profiles found")
        
        with col_stop:
            if st.button("⛔ Stop Loop", type="secondary", disabled=not status.running, use_container_width=True):
                stopped = service.stop()
                if stopped:
                    st.warning("Loop stopped")
                    st.rerun()
    
    # =========================================================================
    # E1) Health Summary (from NDJSON events)
    # =========================================================================
    with st.expander("🩺 System Health Summary | Sistem Sağlık Özeti", expanded=False):
        from pathlib import Path
        from tezaver.ui.matrix_operator_data import load_ndjson_tail, summarize_health
        
        ndjson_path = Path("data/logs/live_events.ndjson")
        
        if st.button("🔄 Refresh Health", key="refresh_health"):
            st.rerun()
        
        events = load_ndjson_tail(ndjson_path, max_lines=500)
        
        if not events:
            st.info("📭 No events found. Run live loop to generate events.")
        else:
            health = summarize_health(events)
            
            col1, col2 = st.columns(2)
            with col1:
                if health["preflight"]:
                    pf = health["preflight"]
                    icon = "✅" if pf["decision"] == "PASS" else "⚠️" if pf["decision"] == "WARN" else "⛔"
                    st.metric("Preflight", f"{icon} {pf['decision']}", pf["ts"][:19] if pf["ts"] else "")
                else:
                    st.metric("Preflight", "—", "No data")
                
                if health["risk_limit"]:
                    rl = health["risk_limit"]
                    icon = "✅" if rl.get("allow") else "⛔"
                    notional = f"${rl.get('total_notional', 0):.0f}" if rl.get("total_notional") else ""
                    st.metric("RiskLimiter", f"{icon} {rl.get('decision', 'N/A')}", notional)
                else:
                    st.metric("RiskLimiter", "—", "No data")
            
            with col2:
                if health["card_gate"]:
                    cg = health["card_gate"]
                    icon = "✅" if cg.get("allow") else "⛔"
                    st.metric("CardGate", f"{icon} {cg.get('decision', 'N/A')}", cg["ts"][:19] if cg.get("ts") else "")
                else:
                    st.metric("CardGate", "—", "No data")
                
                if health["incident_bundle"]:
                    ib = health["incident_bundle"]
                    st.metric("Last Incident", ib.get("reason", "")[:30], ib["ts"][:19] if ib.get("ts") else "")
                else:
                    st.metric("Last Incident", "—", "No exports")
    
    # =========================================================================
    # E2) Incident Bundles Panel
    # =========================================================================
    with st.expander("📦 Incident Bundles | Olay Paketi Arşivi", expanded=False):
        from tezaver.ui.matrix_operator_data import list_incident_bundles
        
        incident_dir = Path("data/incidents")
        bundles = list_incident_bundles(incident_dir)
        
        if not bundles:
            st.info("📭 No incident bundles found.")
        else:
            for b in bundles[:10]:
                if b.error:
                    st.warning(f"⚠️ {Path(b.path).name}: {b.error}")
                else:
                    with st.container():
                        st.markdown(f"**{Path(b.path).name}**")
                        st.caption(f"📅 {b.created_ts[:19]} | 💬 {b.reason[:50]} | 📁 {b.files_count} files | 🔗 `{b.repo_commit[:7]}`")
                        st.code(b.path, language=None)
    
    # =========================================================================
    # E3) Events Explorer
    # =========================================================================
    with st.expander("📊 Events Explorer | Olay Gezgini", expanded=False):
        from tezaver.ui.matrix_operator_data import filter_events
        
        col_type, col_sym, col_limit = st.columns([2, 1, 1])
        with col_type:
            event_type_filter = st.text_input("Event Type (comma-sep)", placeholder="ROUTER_TICK,PREFLIGHT_EVAL", key="evt_type_filter")
        with col_sym:
            sym_filter = st.text_input("Symbol", placeholder="BTCUSDT", key="evt_sym_filter")
        with col_limit:
            limit = st.number_input("Max Lines", min_value=10, max_value=2000, value=100, key="evt_limit")
        
        events = load_ndjson_tail(ndjson_path, max_lines=int(limit))
        
        if event_type_filter:
            types_list = [t.strip() for t in event_type_filter.split(",") if t.strip()]
            events = filter_events(events, event_types=types_list)
        if sym_filter:
            events = filter_events(events, symbol=sym_filter.strip())
        
        if not events:
            st.info("📭 No matching events.")
        else:
            import pandas as pd
            rows = []
            for e in events[-100:]:  # Show last 100
                rows.append({
                    "ts": str(e.get("ts", ""))[:19],
                    "type": e.get("event_type", ""),
                    "symbol": e.get("symbol", ""),
                    "tf": e.get("timeframe", ""),
                    "detail": str(e)[:80],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.caption(f"Showing {len(rows)}/{len(events)} events")

    # =========================================================================
    # G1-G3) Trade Replay v1.1
    # =========================================================================
    with st.expander("🎬 Trade Replay | İşlem Tekrarı", expanded=False):
        from tezaver.ui.trade_replay_data import (
            parse_trades_from_events, build_trade_timeline, 
            load_ohlcv, get_trade_context, Trade, filter_trades
        )
        
        # Load events
        events = load_ndjson_tail(ndjson_path, max_lines=2000)
        
        if not events:
            st.info("📭 No events found. Run live loop to generate trade data.")
        else:
            # Parse trades
            all_trades = parse_trades_from_events(events)
            
            if not all_trades:
                st.info("📭 No completed trades found in events.")
            else:
                # --- G1: Filters ---
                filter_cols = st.columns(3)
                with filter_cols[0]:
                    symbols = ["ALL"] + sorted(set(t.symbol for t in all_trades if t.symbol))
                    selected_symbol = st.selectbox("Symbol", symbols, index=0, key="tr_sym")
                with filter_cols[1]:
                    timeframes = ["ALL"] + sorted(set(t.timeframe for t in all_trades if t.timeframe))
                    selected_tf = st.selectbox("Timeframe", timeframes, index=0, key="tr_tf")
                with filter_cols[2]:
                    st.caption(f"Total: {len(all_trades)} trades")
                
                # Apply filters
                trades = filter_trades(all_trades, selected_symbol, selected_tf, limit=50)
                
                col_list, col_detail = st.columns([1, 2])
                
                with col_list:
                    st.markdown(f"**📋 Trade List** ({len(trades)} shown)")
                    
                    # Trade table
                    trade_rows = []
                    for i, t in enumerate(trades):
                        trade_rows.append({
                            "idx": i,
                            "Symbol": t.symbol,
                            "TF": t.timeframe,
                            "Open": t.open_ts[:16] if t.open_ts else "",
                            "Close": t.close_ts[:16] if t.close_ts else "",
                            "PnL": f"{t.net_pnl:.2f}" if t.net_pnl else "-",
                        })
                    
                    if trade_rows:
                        import pandas as pd
                        df_trades = pd.DataFrame(trade_rows)
                        st.dataframe(df_trades, use_container_width=True, hide_index=True)
                        
                        # Select trade
                        selected_idx = st.selectbox(
                            "Select Trade", 
                            options=range(len(trades)),
                            format_func=lambda i: f"{trades[i].symbol}/{trades[i].timeframe} @ {trades[i].open_ts[:16]}",
                            key="tr_select"
                        )
                        selected_trade = trades[selected_idx]
                
                with col_detail:
                    if trades:
                        selected_trade = trades[selected_idx] if 'selected_idx' in dir() else trades[0]
                        
                        st.markdown(f"**📊 Trade: {selected_trade.symbol}/{selected_trade.timeframe}**")
                        
                        # Trade summary
                        st.markdown(f"""
                        - **Open:** {selected_trade.open_ts[:19]} @ {selected_trade.open_px or 'N/A'}
                        - **Close:** {(selected_trade.close_ts or '')[:19]} @ {selected_trade.close_px or 'N/A'}
                        - **Side:** {selected_trade.side} | **Qty:** {selected_trade.qty or 'N/A'}
                        - **Net PnL:** {f'${selected_trade.net_pnl:.2f}' if selected_trade.net_pnl else 'N/A'}
                        - **Close Reason:** {selected_trade.close_reason or 'N/A'}
                        """)
                        
                        # Load OHLCV and render chart
                        if selected_trade.open_ts and selected_trade.close_ts:
                            candles, paths_tried = load_ohlcv(
                                selected_trade.symbol, 
                                selected_trade.timeframe,
                                selected_trade.open_ts,
                                selected_trade.close_ts,
                            )
                            
                            if candles:
                                import plotly.graph_objects as go
                                
                                fig = go.Figure(data=[go.Candlestick(
                                    x=[c["ts"] for c in candles],
                                    open=[c["open"] for c in candles],
                                    high=[c["high"] for c in candles],
                                    low=[c["low"] for c in candles],
                                    close=[c["close"] for c in candles],
                                    name="Price"
                                )])
                                
                                # Entry marker
                                if selected_trade.open_px:
                                    fig.add_trace(go.Scatter(
                                        x=[selected_trade.open_ts],
                                        y=[selected_trade.open_px],
                                        mode="markers",
                                        marker=dict(size=12, color="green", symbol="triangle-up"),
                                        name="Entry"
                                    ))
                                
                                # Exit marker
                                if selected_trade.close_px and selected_trade.close_ts:
                                    fig.add_trace(go.Scatter(
                                        x=[selected_trade.close_ts],
                                        y=[selected_trade.close_px],
                                        mode="markers",
                                        marker=dict(size=12, color="red", symbol="triangle-down"),
                                        name="Exit"
                                    ))
                                
                                # G2: SL/TP lines (optional)
                                x_range = [candles[0]["ts"], candles[-1]["ts"]]
                                if selected_trade.sl_px:
                                    fig.add_trace(go.Scatter(
                                        x=x_range,
                                        y=[selected_trade.sl_px, selected_trade.sl_px],
                                        mode="lines",
                                        line=dict(color="red", dash="dash", width=1),
                                        name=f"SL @ {selected_trade.sl_px:.2f}"
                                    ))
                                if selected_trade.tp_px:
                                    fig.add_trace(go.Scatter(
                                        x=x_range,
                                        y=[selected_trade.tp_px, selected_trade.tp_px],
                                        mode="lines",
                                        line=dict(color="green", dash="dash", width=1),
                                        name=f"TP @ {selected_trade.tp_px:.2f}"
                                    ))
                                
                                fig.update_layout(
                                    title=f"{selected_trade.symbol} - Trade Replay",
                                    xaxis_title="Time",
                                    yaxis_title="Price",
                                    height=400,
                                    showlegend=True,
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                # G3: Show paths tried
                                paths_str = ", ".join([str(p)[-50:] for p in paths_tried[:3]])
                                st.warning(f"⚠️ No OHLCV data found. Tried: {paths_str}")
                        
                        # Why box
                        st.markdown("**🔍 Why (Decision Context)**")
                        ctx = get_trade_context(events, selected_trade)
                        ctx_items = []
                        if ctx.get("preflight"):
                            ctx_items.append(f"• Preflight: {ctx['preflight']}")
                        if ctx.get("card_gate"):
                            ctx_items.append(f"• CardGate: {ctx['card_gate']}")
                        if ctx.get("risk_limit"):
                            ctx_items.append(f"• RiskLimit: {ctx['risk_limit']}")
                        if ctx.get("mainnet_guard"):
                            ctx_items.append(f"• MainnetGuard: {ctx['mainnet_guard']}")
                        if ctx.get("close_reason"):
                            ctx_items.append(f"• CloseReason: {ctx['close_reason']}")
                        
                        if ctx_items:
                            st.markdown("\n".join(ctx_items[:6]))
                        else:
                            st.caption("No decision context found.")
                        
                        # Timeline
                        st.markdown("**📜 Event Timeline**")
                        timeline = build_trade_timeline(events, selected_trade)
                        
                        if timeline:
                            tl_rows = [{"ts": r.ts, "type": r.event_type, "decision": r.decision or "", "reason": r.reason or ""} for r in timeline[:20]]
                            st.dataframe(pd.DataFrame(tl_rows), use_container_width=True, hide_index=True)
                        else:
                            st.caption("No timeline events found.")

    # =========================================================================
    # Live Freshness Table
    # =========================================================================
    with st.expander("🟢 Live Freshness / Lag | Canlı Veri Tazeliği", expanded=status.running):
        cell_metrics = service.get_cell_metrics()
        
        if cell_metrics:
            import pandas as pd
            freshness_rows = []
            for m in cell_metrics:
                lag = m.get("lag_sec")
                lag_str = f"{lag:.0f}s" if lag else "-"
                if lag and lag > 120:
                    lag_str = f"⚠️ {lag_str}"
                
                freshness_rows.append({
                    "Symbol": m.get("symbol"),
                    "TF": m.get("timeframe"),
                    "last_closed_bar": m.get("last_closed_bar_ts", "-")[:19] if m.get("last_closed_bar_ts") else "-",
                    "lag": lag_str,
                    "ticks": m.get("ticks_count", 0),
                    "skips": m.get("skips_count", 0),
                    "reason": m.get("last_tick_reason", "-"),
                    "close": f"{m.get('last_close'):.2f}" if m.get("last_close") else "-",
                })
            
            st.dataframe(pd.DataFrame(freshness_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Loop başlatıldığında freshness verileri burada görünür.")
    
    # =========================================================================
    # Cycles Report (NEW) - Multi-cycle summary from NDJSON
    # =========================================================================
    with st.expander("📊 Cycles Report | Döngü Raporu", expanded=False):
        st.caption("Çalıştırılmış trade cycle'larının özeti. NDJSON log'undan okunur.")
        
        from pathlib import Path
        try:
            from tezaver.matrix.live.cycle_events import (
                load_cycle_records,
                compute_aggregates,
                CycleAlertLevel,
            )
            
            ndjson_path = Path("data/logs/live_events.ndjson")
            
            # Controls
            col1, col2, col3 = st.columns(3)
            with col1:
                cr_symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], key="cr_symbol")
            with col2:
                cr_tf = st.selectbox("Timeframe", ["15m", "1m", "1h"], key="cr_tf")
            with col3:
                cr_last = st.slider("Last N", 1, 50, 10, key="cr_last")
            
            if st.button("🔄 Refresh", key="cr_refresh"):
                st.rerun()
            
            # =========================================================================
            # Auto-Incident Controls
            # =========================================================================
            with st.expander("🧯 Auto-Incident on BLOCK | Otomatik Olay Kaydı", expanded=False):
                st.caption("Automatically export incident bundles for BLOCK/WARN cycles. Matches CLI behavior.")
                
                ai_col1, ai_col2, ai_col3 = st.columns(3)
                with ai_col1:
                    auto_incident_on = st.selectbox(
                        "Auto-export on",
                        options=["BLOCK", "WARN", "OFF"],
                        index=0,  # Default: BLOCK
                        key="auto_incident_on"
                    )
                with ai_col2:
                    auto_incident_max = st.slider(
                        "Max bundles",
                        min_value=1,
                        max_value=5,
                        value=1,
                        key="auto_incident_max"
                    )
                with ai_col3:
                    auto_incident_only_relevant = st.checkbox(
                        "Only relevant events",
                        value=True,
                        key="auto_incident_only_relevant"
                    )
                
                auto_incident_out_dir = st.text_input(
                    "Output directory",
                    value="data/incidents",
                    key="auto_incident_out_dir"
                )
                
                # Run auto-incident button
                if st.button("🔄 Run Auto-Incident Export", key="btn_auto_incident", type="primary"):
                    if ndjson_path.exists():
                        try:
                            from tezaver.matrix.live.cycle_events import (
                                IncidentBundleSpec,
                                build_incident_bundle,
                            )
                            from tezaver.matrix.live.live_loop import emit_incident_bundle_telemetry
                            
                            # Load records
                            temp_records = load_cycle_records(ndjson_path, cr_symbol, cr_tf, 50)
                            
                            # Filter by alert level
                            auto_records = []
                            if auto_incident_on == "BLOCK":
                                auto_records = [r for r in temp_records if r.alert_level == CycleAlertLevel.BLOCK]
                            elif auto_incident_on == "WARN":
                                auto_records = [r for r in temp_records if r.alert_level in [CycleAlertLevel.WARN, CycleAlertLevel.BLOCK]]
                            
                            # Limit to max
                            auto_records = auto_records[:auto_incident_max]
                            
                            if auto_records:
                                exported_count = 0
                                for r in auto_records:
                                    try:
                                        spec = IncidentBundleSpec(
                                            symbol=cr_symbol,
                                            timeframe=cr_tf,
                                            cycle_idx=r.cycle_idx,
                                            ndjson_path=str(ndjson_path),
                                            equity_start=100.0,
                                            out_dir=auto_incident_out_dir,
                                            only_relevant=auto_incident_only_relevant,
                                        )
                                        
                                        result = build_incident_bundle(spec)
                                        
                                        if result["success"]:
                                            exported_count += 1
                                            
                                            # Store last incident in session state
                                            st.session_state["last_auto_incident"] = {
                                                "cycle_idx": r.cycle_idx,
                                                "alert_level": result["alert"],
                                                "out_path": result["bundle_path"],
                                                "files_count": len(result["files"]),
                                                "ts": r.done_ts or r.start_ts,
                                            }
                                            
                                            # Emit telemetry
                                            emit_incident_bundle_telemetry(
                                                symbol=cr_symbol,
                                                timeframe=cr_tf,
                                                cycle_idx=r.cycle_idx,
                                                alert_level=result["alert"],
                                                out_path=result["bundle_path"],
                                                files_count=len(result["files"]),
                                            )
                                    except Exception as e:
                                        st.error(f"Export failed for cycle {r.cycle_idx}: {e}")
                                
                                st.success(f"✅ Exported {exported_count} incident bundle(s)!")
                                st.rerun()
                            else:
                                st.warning(f"No cycles found matching {auto_incident_on} alert level.")
                        except Exception as e:
                            st.error(f"Auto-incident export error: {e}")
                    else:
                        st.warning("NDJSON file not found. Run a cycle first.")
            
            # Last Incident Card
            if "last_auto_incident" in st.session_state:
                st.divider()
                st.subheader("🆘 Last Auto-Incident Export")
                
                last_incident = st.session_state["last_auto_incident"]
                
                inc_cols = st.columns(4)
                with inc_cols[0]:
                    st.metric("Cycle", last_incident.get("cycle_idx"))
                with inc_cols[1]:
                    st.metric("Alert", last_incident.get("alert_level"))
                with inc_cols[2]:
                    st.metric("Files", last_incident.get("files_count"))
                with inc_cols[3]:
                    timestamp = last_incident.get("ts", "")[:19] if last_incident.get("ts") else "-"
                    st.metric("Exported", timestamp)
                
                st.code(last_incident.get("out_path"))
                
                # README preview button
                readme_path = Path(last_incident.get("out_path")) / "README.txt"
                if readme_path.exists():
                    with st.expander("📄 README Preview"):
                        with open(readme_path, "r") as rf:
                            st.code(rf.read()[:2000])
            
            if not ndjson_path.exists():
                st.warning(f"NDJSON dosyası bulunamadı: {ndjson_path}")
                st.info("Runbook: Önce bir cycle çalıştırın:")
            else:
                records = load_cycle_records(ndjson_path, cr_symbol, cr_tf, cr_last)
                
                if not records:
                    st.info("Filtrelere uyan cycle kaydı bulunamadı.")
                else:
                    import pandas as pd
                    
                    # Aggregates first for banner
                    agg = compute_aggregates(records)
                    
                    # Alert Banner
                    ok_count = agg.get("ok_count", 0)
                    warn_count = agg.get("warn_count", 0)
                    block_count = agg.get("block_count", 0)
                    
                    if block_count > 0:
                        st.error(f"⛔ BLOCK: {block_count} | ⚠️ WARN: {warn_count} | ✅ OK: {ok_count}")
                    elif warn_count > 0:
                        st.warning(f"⚠️ WARN: {warn_count} | ✅ OK: {ok_count}")
                    else:
                        st.success(f"✅ All OK: {ok_count} cycles")
                    
                    # Build table data with Alert column
                    table_data = []
                    for r in records:
                        # Alert emoji
                        if r.alert_level == CycleAlertLevel.BLOCK:
                            alert = "⛔ BLOCK"
                        elif r.alert_level == CycleAlertLevel.WARN:
                            alert = "⚠️ WARN"
                        else:
                            alert = "✅ OK"
                        
                        table_data.append({
                            "Cycle": r.cycle_idx,
                            "Alert": alert,
                            "Status": r.status,
                            "Open ID": r.open_order_id[:10] if r.open_order_id else "-",
                            "Close ID": r.close_order_id[:10] if r.close_order_id else "-",
                            "Entry": f"{r.entry_price:.2f}" if r.entry_price else "-",
                            "Exit": f"{r.exit_price:.2f}" if r.exit_price else "-",
                            "Net": f"{r.net_pnl:.4f}" if r.net_pnl is not None else "-",
                            "Fee": f"{r.fee:.4f}" if r.fee is not None else "-",
                            "Gross": f"{r.gross_pnl:.4f}" if r.gross_pnl is not None else "-",
                            "Bars": r.cycle_bars,
                            "Lag": f"{r.eff_lag:.0f}s" if r.eff_lag else "-",
                            "Residual": f"{r.residual_after:.6f}" if r.residual_after else "0",
                            "ReduceOnly": "✓" if r.reduce_only else "✗",
                            "PosAfter": f"{r.pos_after:.6f}" if r.pos_after is not None else "-",
                        })
                    
                    df = pd.DataFrame(table_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    
                    # Timeline Drilldown
                    st.divider()
                    st.subheader("🔍 Cycle Timeline Drilldown")
                    
                    cycle_options = [r.cycle_idx for r in records]
                    if cycle_options:
                        # Row selection
                        col_sel1, col_sel2 = st.columns([2, 3])
                        with col_sel1:
                            selected_cycle = st.selectbox(
                                "Select cycle to view timeline",
                                options=cycle_options,
                                key="timeline_cycle_select"
                            )
                        
                        # Get selected record for alert info
                        selected_record = next((r for r in records if r.cycle_idx == selected_cycle), None)
                        
                        with col_sel2:
                            if selected_record:
                                alert_badge = "✅ OK" if selected_record.alert_level == CycleAlertLevel.OK else \
                                             "⚠️ WARN" if selected_record.alert_level == CycleAlertLevel.WARN else "⛔ BLOCK"
                                st.info(f"**Active Cycle: {selected_cycle}** | Status: {selected_record.status} | Alert: {alert_badge}")
                        
                        if selected_cycle is not None:
                            try:
                                from tezaver.matrix.live.cycle_events import (
                                    get_cycle_events,
                                    TIMELINE_EVENT_TYPES,
                                )
                                
                                timeline_events = get_cycle_events(ndjson_path, selected_cycle, cr_symbol)
                                
                                # Filters
                                st.caption("Timeline Filters")
                                filter_col1, filter_col2, filter_col3 = st.columns(3)
                                
                                with filter_col1:
                                    # Event type filter
                                    all_event_types = list(set(e.get("event_type", "") for e in timeline_events))
                                    selected_types = st.multiselect(
                                        "Event Types",
                                        options=all_event_types,
                                        default=all_event_types,
                                        key="timeline_event_types"
                                    )
                                
                                with filter_col2:
                                    # Search box
                                    search_text = st.text_input("Search key fields", key="timeline_search")
                                
                                with filter_col3:
                                    # Only relevant toggle
                                    only_relevant = st.checkbox(
                                        "Only relevant events",
                                        value=False,
                                        key="timeline_only_relevant"
                                    )
                                    relevant_types = [
                                        "CYCLE_START", "CYCLE_DONE", "CYCLE_TIMEOUT",
                                        "STRATEGY_SIGNAL", "ROUTER_POLICY_STATE",
                                        "ORDER_SUBMIT", "ORDER_RESULT",
                                        "ORDER_FETCH_OPEN", "ORDER_FETCH_CLOSE",
                                        "TRADE_AUDIT_V2_DONE", "POSITION_SNAPSHOT_CLOSE"
                                    ]
                                
                                # Apply filters
                                filtered_events = timeline_events
                                
                                if selected_types:
                                    filtered_events = [e for e in filtered_events if e.get("event_type") in selected_types]
                                
                                if search_text:
                                    import json as json_module
                                    filtered_events = [
                                        e for e in filtered_events 
                                        if search_text.lower() in json_module.dumps(e, default=str).lower()
                                    ]
                                
                                if only_relevant:
                                    filtered_events = [e for e in filtered_events if e.get("event_type") in relevant_types]
                                
                                if filtered_events:
                                    # Show timeline table
                                    timeline_data = []
                                    for idx, evt in enumerate(filtered_events):
                                        evt_type = evt.get("event_type", "")
                                        ts = evt.get("ts", "")[:25]
                                        
                                        # Key field extraction
                                        if evt_type == "ORDER_RESULT":
                                            key = f"order={evt.get('order_id')}, action={evt.get('action')}, success={evt.get('success')}"
                                        elif evt_type == "TRADE_AUDIT_V2_DONE":
                                            key = f"entry={evt.get('entry_price')}, exit={evt.get('exit_price')}, net={evt.get('net_pnl_usdt')}"
                                        elif evt_type == "CYCLE_DONE":
                                            key = f"open={evt.get('open_order_id')}, close={evt.get('close_order_id')}, bars={evt.get('cycle_bars')}"
                                        elif evt_type == "POSITION_SNAPSHOT_CLOSE":
                                            key = f"pos={evt.get('pos_amt_now')}"
                                        elif evt_type == "ORDER_FETCH_OPEN" or evt_type == "ORDER_FETCH_CLOSE":
                                            key = f"order={evt.get('order_id')}, status={evt.get('status')}"
                                        elif evt_type == "NEW_CLOSED_BAR":
                                            key = f"close={evt.get('close')}"
                                        else:
                                            key = "-"
                                        
                                        timeline_data.append({
                                            "#": idx + 1,
                                            "Timestamp": ts,
                                            "Event": evt_type,
                                            "Key": key[:60],
                                        })
                                    
                                    timeline_df = pd.DataFrame(timeline_data)
                                    st.dataframe(timeline_df, use_container_width=True, hide_index=True)
                                    
                                    # Raw JSON viewer per event
                                    st.subheader("📄 Raw Event JSON")
                                    event_idx = st.number_input(
                                        "Event # to view",
                                        min_value=1,
                                        max_value=len(filtered_events),
                                        value=1,
                                        key="raw_event_idx"
                                    )
                                    
                                    if 1 <= event_idx <= len(filtered_events):
                                        import json as json_module
                                        raw_event = filtered_events[event_idx - 1]
                                        raw_json_str = json_module.dumps(raw_event, indent=2, default=str)
                                        st.code(raw_json_str, language="json")
                                        
                                        # Copy button (using st.download_button as workaround)
                                        st.download_button(
                                            label="📋 Copy JSON",
                                            data=raw_json_str,
                                            file_name=f"event_{selected_cycle}_{event_idx}.json",
                                            mime="application/json"
                                        )
                                else:
                                    st.info(f"No timeline events found for cycle {selected_cycle} with current filters.")
                                
                                # Alert Explanation Panel
                                if selected_record and selected_record.alert_level != CycleAlertLevel.OK:
                                    st.divider()
                                    st.subheader("⚠️ Alert Explanation")
                                    
                                    if selected_record.alert_level == CycleAlertLevel.BLOCK:
                                        st.error("**BLOCK Violations:**")
                                        for reason in selected_record.block_reasons:
                                            st.markdown(f"- ❌ {reason}")
                                        
                                        st.warning("**Suggested Actions:**")
                                        if any("reduce_only" in r.lower() for r in selected_record.block_reasons):
                                            st.markdown("- Enforce `reduceOnly=True` for all CLOSE orders")
                                        if any("pos_after" in r.lower() for r in selected_record.block_reasons):
                                            st.markdown("- Tighten dust policy or investigate gateway")
                                        if any("status" in r.lower() for r in selected_record.block_reasons):
                                            st.markdown("- Check order execution logs for failures")
                                        if any("audit" in r.lower() for r in selected_record.block_reasons):
                                            st.markdown("- Enable `--audit` flag for complete cycle data")
                                    
                                    elif selected_record.alert_level == CycleAlertLevel.WARN:
                                        st.warning("**WARN Conditions:**")
                                        for reason in selected_record.warn_reasons:
                                            st.markdown(f"- ⚠️ {reason}")
                                        
                                        st.info("**Suggested Review:**")
                                        if any("residual" in r.lower() for r in selected_record.warn_reasons):
                                            st.markdown("- Consider adjusting dust threshold")
                                        if any("timeout" in r.lower() for r in selected_record.warn_reasons):
                                            st.markdown("- Review timeout configuration")
                                        if any("bars" in r.lower() for r in selected_record.warn_reasons):
                                            st.markdown("- Cycle bars approaching timeout threshold")
                                
                                # Export Incident Bundle
                                st.divider()
                                st.subheader("📦 Export Incident Bundle")
                                
                                bundle_col1, bundle_col2 = st.columns(2)
                                with bundle_col1:
                                    bundle_out_dir = st.text_input(
                                        "Output Directory",
                                        value="data/incidents",
                                        key="bundle_out_dir"
                                    )
                                with bundle_col2:
                                    bundle_only_relevant = st.checkbox(
                                        "Only relevant events",
                                        value=True,
                                        key="bundle_only_relevant"
                                    )
                                
                                if st.button("📦 Export Bundle", key="export_bundle_btn"):
                                    try:
                                        from tezaver.matrix.live.cycle_events import (
                                            IncidentBundleSpec,
                                            build_incident_bundle,
                                        )
                                        
                                        spec = IncidentBundleSpec(
                                            symbol=cr_symbol,
                                            timeframe=cr_tf,
                                            cycle_idx=selected_cycle,
                                            ndjson_path=str(ndjson_path),
                                            equity_start=100.0,
                                            out_dir=bundle_out_dir,
                                            only_relevant=bundle_only_relevant,
                                        )
                                        
                                        result = build_incident_bundle(spec)
                                        
                                        if result["success"]:
                                            st.success(f"✅ Bundle exported: {result['bundle_path']}")
                                            st.markdown("**Files created:**")
                                            for f in result['files']:
                                                st.markdown(f"- `{f}`")
                                            
                                            # README preview
                                            readme_path = Path(result['bundle_path']) / "README.txt"
                                            if readme_path.exists():
                                                with st.expander("📄 README Preview"):
                                                    with open(readme_path, "r") as rf:
                                                        readme_content = rf.read()
                                                    st.code(readme_content[:2000])
                                        else:
                                            st.error(f"Bundle export failed: {result['error']}")
                                    except Exception as bundle_err:
                                        st.error(f"Bundle export error: {bundle_err}")
                            except Exception as timeline_err:
                                st.warning(f"Timeline yüklenemedi: {timeline_err}")
                    
                    # Aggregates metrics
                    cols = st.columns(4)
                    with cols[0]:
                        st.metric("Total Cycles", agg["total_cycles"])
                        st.metric("Done", agg["done_cycles"])
                    with cols[1]:
                        st.metric("Winrate", f"{agg['winrate']:.1f}%")
                        st.metric("W/L", f"{agg['win_count']}/{agg['loss_count']}")
                    with cols[2]:
                        st.metric("Total Net", f"{agg['total_net']:.4f} USDT")
                        st.metric("Total Fee", f"{agg['total_fee']:.4f} USDT")
                    with cols[3]:
                        st.metric("Avg Lag", f"{agg['avg_eff_lag']:.0f}s")
                        st.metric("Max DD", f"{agg['max_drawdown']:.4f}")
                    
                    # Drilldown for BLOCK/WARN
                    if block_count > 0 or warn_count > 0:
                        with st.expander("🔍 Alert Details", expanded=True):
                            for r in records:
                                if r.alert_level == CycleAlertLevel.BLOCK:
                                    st.error(f"**Cycle {r.cycle_idx}** BLOCK: {', '.join(r.block_reasons)}")
                                elif r.alert_level == CycleAlertLevel.WARN:
                                    st.warning(f"**Cycle {r.cycle_idx}** WARN: {', '.join(r.warn_reasons)}")
                    
                    # CSV Export
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name=f"cycles_{cr_symbol}_{cr_tf}.csv",
                        mime="text/csv",
                    )
                    
                    # =========================================================
                    # Equity Curve Chart + Risk Metrics
                    # =========================================================
                    st.divider()
                    
                    try:
                        from tezaver.matrix.live.cycle_events import (
                            compute_equity_curve,
                            compute_risk_metrics,
                        )
                        import matplotlib.pyplot as plt
                        import io
                        
                        equity_start = 100.0
                        equity_points = compute_equity_curve(records, equity_start)
                        risk_metrics = compute_risk_metrics(records, equity_points, equity_start)
                        
                        if equity_points:
                            # Risk Metrics Cards
                            st.subheader("📌 Risk Metrics")
                            m_cols = st.columns(5)
                            with m_cols[0]:
                                st.metric("MDD", f"{risk_metrics['mdd']:.4f}")
                                st.caption(f"{risk_metrics['mdd_pct']:.2f}%")
                            with m_cols[1]:
                                pf = risk_metrics['profit_factor']
                                pf_str = f"{pf:.2f}" if pf != float('inf') else "∞"
                                st.metric("Profit Factor", pf_str)
                            with m_cols[2]:
                                st.metric("Avg Net", f"{risk_metrics['avg_net']:.4f}")
                            with m_cols[3]:
                                st.metric("Std Dev", f"{risk_metrics['std_net']:.4f}")
                            with m_cols[4]:
                                st.metric("Avg Bars", f"{risk_metrics['avg_bars']:.1f}")
                            
                            # Equity Curve Chart
                            st.subheader("📉 Equity Curve")
                            
                            fig, ax = plt.subplots(figsize=(10, 4))
                            idxs = [pt.cycle_idx for pt in equity_points]
                            equities = [pt.equity for pt in equity_points]
                            
                            ax.plot(idxs, equities, marker='o', linewidth=2)
                            ax.axhline(y=equity_start, color='gray', linestyle='--', alpha=0.5)
                            ax.set_xlabel("Cycle Index")
                            ax.set_ylabel("Equity (USDT)")
                            ax.set_title(f"Equity Curve - {cr_symbol}/{cr_tf}")
                            ax.grid(True, alpha=0.3)
                            
                            st.pyplot(fig)
                            plt.close(fig)
                            
                            # Equity CSV Export
                            equity_data = [{
                                "Cycle": pt.cycle_idx,
                                "Timestamp": pt.ts,
                                "Net": pt.net_pnl,
                                "Equity": pt.equity,
                                "Cum%": pt.cum_return_pct,
                            } for pt in equity_points]
                            equity_df = pd.DataFrame(equity_data)
                            equity_csv = equity_df.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Equity CSV",
                                data=equity_csv,
                                file_name=f"equity_{cr_symbol}_{cr_tf}.csv",
                                mime="text/csv",
                            )
                        else:
                            st.info("Equity curve hesaplanamadı (DONE cycle yok).")
                    except Exception as chart_err:
                        st.warning(f"Equity chart yüklenemedi: {chart_err}")
        except Exception as e:
            st.error(f"Cycles Report yüklenirken hata: {e}")
    
    # =========================================================================
    # Closed Bar Proof (NEW)
    # =========================================================================
    with st.expander("✅ Closed Bar Proof | Kapalı Bar Kanıtı", expanded=False):
        st.caption("Kapalı bar tick'ini tek tuşla kanıtla. Proof sırasında trade devre dışı.")
        
        from tezaver.matrix.live.timeframe_utils import eta_to_next_close, format_eta
        from datetime import datetime, timezone as tz
        
        proof_state = service.get_proof_state()
        
        # Controls
        col1, col2, col3 = st.columns(3)
        with col1:
            proof_symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], key="proof_symbol")
        with col2:
            proof_tf = st.selectbox("Timeframe", ["1m", "15m"], key="proof_tf")
        with col3:
            proof_poll = st.slider("Poll (s)", 3, 10, 5, key="proof_poll")
        
        proof_real = st.checkbox("🌐 Use REAL Binance", value=True, key="proof_real")
        
        # ETA countdown
        now_utc = datetime.now(tz.utc)
        eta_sec, progress, next_close = eta_to_next_close(now_utc, proof_tf)
        eta_str = format_eta(eta_sec)
        
        st.caption(f"⏳ Next {proof_tf} close ETA: **{eta_str}** (UTC)")
        st.progress(progress)
        
        # Refresh button
        if st.button("🔄 Refresh", key="btn_proof_refresh"):
            st.rerun()
        
        st.divider()
        
        # Status line
        if proof_state.get("running"):
            st.success(f"PROOF RUNNING ✅ | run_id={proof_state.get('proof_run_id')} | ETA: {eta_str}")
        else:
            if proof_state.get("last_proof_event"):
                st.success("PROOF_OK ✅")
            else:
                st.info("PROOF STOPPED ⛔")
        
        if proof_state.get("last_error"):
            st.error(f"Error: {proof_state.get('last_error')}")
        
        # Buttons
        col_start, col_stop = st.columns(2)
        with col_start:
            if st.button("▶️ Start Proof", type="primary", disabled=proof_state.get("running", False), key="btn_start_proof"):
                run_id = service.start_proof_closed(
                    symbol=proof_symbol,
                    timeframe=proof_tf,
                    poll_sec=float(proof_poll),
                    use_real=proof_real,
                )
                if run_id:
                    st.success(f"Proof started: {run_id}")
                    st.rerun()
        
        with col_stop:
            if st.button("⏹ Stop Proof", disabled=not proof_state.get("running", False), key="btn_stop_proof"):
                service.stop_proof_closed()
                st.warning("Proof stopped")
                st.rerun()
        
        # Proof result card
        last_proof = proof_state.get("last_proof_event")
        if last_proof:
            st.divider()
            st.markdown("### 🎯 Proof Result")
            
            proof_cols = st.columns(4)
            with proof_cols[0]:
                st.metric("Symbol", f"{last_proof.get('symbol')}/{last_proof.get('timeframe')}")
            with proof_cols[1]:
                st.metric("bar_close_ts", last_proof.get("bar_close_ts", "-")[:19] if last_proof.get("bar_close_ts") else "-")
            with proof_cols[2]:
                lag = last_proof.get("lag_sec")
                st.metric("lag_sec", f"{lag:.1f}" if lag else "-")
            with proof_cols[3]:
                close = last_proof.get("close")
                st.metric("close", f"{close:.2f}" if close else "-")
            
            st.code(f"PROOF_OK | {last_proof.get('symbol')}/{last_proof.get('timeframe')} bar_close_ts={last_proof.get('bar_close_ts')} lag={last_proof.get('lag_sec')} close={last_proof.get('close')} policy={last_proof.get('policy')} dry_run={last_proof.get('proof_force_dry_run')}")
        
        # Proof history table
        proof_history = service.get_proof_history()
        if proof_history:
            st.divider()
            st.markdown("### 📋 Proof History (Last 10)")
            
            import pandas as pd
            history_rows = []
            for p in proof_history:
                history_rows.append({
                    "ts": p.get("ts", "-")[:19] if p.get("ts") else "-",
                    "symbol": p.get("symbol"),
                    "tf": p.get("timeframe"),
                    "bar_close_ts": p.get("bar_close_ts", "-")[:19] if p.get("bar_close_ts") else "-",
                    "lag": f"{p.get('lag_sec'):.1f}" if p.get("lag_sec") else "-",
                    "close": f"{p.get('close'):.2f}" if p.get("close") else "-",
                    "policy": p.get("policy", "-"),
                })
            
            st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
    
    # =========================================================================
    # Dust & Position Hygiene (NEW)
    # =========================================================================
    with st.expander("🧹 Dust & Position Hygiene | Bakiye & Pozisyon Temizliği", expanded=False):
        st.caption("Pozisyon temizliği ve dust policy ayarları. Proof cycle çalıştırarak test edebilirsiniz.")
        
        # Control columns
        ctrl_col1, ctrl_col2 = st.columns(2)
        
        with ctrl_col1:
            dust_policy = st.selectbox(
                "Dust Policy",
                options=["IGNORE", "FLATTEN_AFTER", "BLOCK"],
                index=1,  # Default: FLATTEN_AFTER (production-safe)
                help="IGNORE: dust kabul, FLATTEN_AFTER: temizleme emri (önerilen), BLOCK: fail if dust",
                key="dust_policy_select"
            )
            
            dust_threshold = st.slider(
                "Dust Threshold (BTC)",
                min_value=0.0001,
                max_value=0.01,
                value=0.001,  # Default: 0.001 (production-safe)
                step=0.0001,
                format="%.4f",
                help="0.001 BTC ≈ $100 @ 100k. Threshold altı 'dust' kabul edilir.",
                key="dust_threshold_slider"
            )
        
        with ctrl_col2:
            preflight_mode = st.selectbox(
                "Preflight Mode",
                options=["BLOCK", "FLATTEN_FIRST", "IGNORE"],
                index=1,  # Default: FLATTEN_FIRST (production-safe)
                help="Mevcut pozisyon varsa: FLATTEN_FIRST önerilir",
                key="preflight_mode_select"
            )
            
            close_policy = st.selectbox(
                "Close Policy",
                options=["NEXT_CLOSED_BAR", "NEXT_SIGNAL"],
                index=0,  # Default: NEXT_CLOSED_BAR
                help="CLOSE tetikleme politikası",
                key="close_policy_select"
            )
        
        # Advanced Debug (hidden by default)
        close_qty_mult = 1.0  # Safe default
        with st.expander("🔧 Advanced Debug | Gelişmiş Hata Ayıklama", expanded=False):
            close_qty_mult = st.slider(
                "Close Qty Multiplier",
                min_value=0.1,
                max_value=1.0,
                value=1.0,
                step=0.1,
                help="1.0 = full close, <1.0 = partial close (DEBUG ONLY - pozisyon kalır!)",
                key="close_qty_mult_slider"
            )
            
            # Guardrail warning
            if close_qty_mult < 1.0:
                st.error("🚨 **DEBUG ONLY**: close_qty_mult < 1.0 - Partial close aktif! Pozisyon kalacak!")
                st.warning("⚠️ Bu ayar sadece BLOCK fail kanıtı için kullanılmalıdır.")
        
        # Expected Behavior card
        st.divider()
        behavior_text = {
            "IGNORE": "✅ Dust kabul edilir, cleanup yapılmaz.",
            "FLATTEN_AFTER": "🧹 CLOSE sonrası dust varsa temizleme emri gönderilir. (Önerilen)",
            "BLOCK": "⛔ Dust threshold aşılırsa sistem durur (RuntimeError).",
        }
        st.info(f"**Beklenen Davranış:** {behavior_text.get(dust_policy, '-')}")
        
        # Exchange mode selection
        st.divider()
        proof_exchange_mode = st.radio(
            "Exchange Mode",
            options=["DUMMY_ORDER", "REAL_TESTNET"],
            index=0,
            horizontal=True,
            help="DUMMY: gerçek emir yok, REAL_TESTNET: gerçek testnet emri",
            key="proof_exchange_mode"
        )
        
        # Guardrails check
        can_run = True
        guardrail_msg = ""
        
        if proof_exchange_mode == "REAL_TESTNET" and close_qty_mult < 1.0:
            st.error("🚨 **DANGER**: REAL_TESTNET + partial close! Gerçek pozisyon kalabilir!")
        
        # BLOCK + close_qty_mult < 1.0 = sabotage prevention
        if dust_policy == "BLOCK" and close_qty_mult < 1.0:
            can_run = False
            st.error("⛔ **BLOCKED**: BLOCK mode + close_qty_mult < 1.0 kombinasyonu izin verilmez! "
                    "Bu kasıtlı fail senaryosudur. Test için dust_policy=IGNORE veya FLATTEN_AFTER kullanın.")
        
        # Run Proof Cycle button
        if st.button("▶️ Run Proof Cycle", type="primary", use_container_width=True, 
                     disabled=not can_run, key="btn_run_proof_cycle"):
            with st.spinner("Proof cycle çalışıyor... (2-3 bar bekleniyor, ~3 dk)"):
                import subprocess
                
                cmd = [
                    "./venv/bin/python", "-m", "tezaver.matrix.live.live_loop",
                    "proof_router_cluster",
                    "--real", "--tf", "1m", "--poll", "5",
                    f"--exchange-mode", proof_exchange_mode,
                    "--armed", "--no-force-dry-run", "--exchange-enabled",
                    "--hold-policy", "HOLD_NEXT_CLOSED", "--until-done",
                    f"--dust-policy", dust_policy,
                    f"--dust-threshold", str(dust_threshold),
                    f"--close-qty-mult", str(close_qty_mult),
                ]
                
                try:
                    result = subprocess.run(
                        cmd,
                        cwd="/Users/alisaglam/TezaverMac",
                        capture_output=True,
                        text=True,
                        timeout=360,  # 6 min timeout
                    )
                    
                    st.session_state["proof_cycle_stdout"] = result.stdout
                    st.session_state["proof_cycle_stderr"] = result.stderr
                    st.session_state["proof_cycle_exit_code"] = result.returncode
                    
                except subprocess.TimeoutExpired:
                    st.session_state["proof_cycle_exit_code"] = -1
                    st.session_state["proof_cycle_stderr"] = "TIMEOUT (360s)"
                except Exception as e:
                    st.session_state["proof_cycle_exit_code"] = -2
                    st.session_state["proof_cycle_stderr"] = str(e)
                
                st.rerun()
        
        # Show proof cycle result
        if "proof_cycle_exit_code" in st.session_state:
            st.divider()
            exit_code = st.session_state.get("proof_cycle_exit_code", 0)
            stdout = st.session_state.get("proof_cycle_stdout", "")
            stderr = st.session_state.get("proof_cycle_stderr", "")
            
            # Status display
            if exit_code == 0:
                st.success(f"✅ Proof Cycle BAŞARILI (exit_code={exit_code})")
            else:
                st.error(f"⛔ Proof Cycle FAIL (exit_code={exit_code})")
            
            # Extract summary line
            summary_line = ""
            for line in stdout.split("\n"):
                if "PROOF_ROUTER_CLUSTER_POLICY_OK" in line or "BLOCKED" in line:
                    summary_line = line
                    break
            
            if summary_line:
                st.code(summary_line, language="text")
            
            # Extract key metrics
            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
            
            # Parse from stdout
            residual = "-"
            cleanup_attempted = "-"
            cleanup_result = "-"
            
            for line in stdout.split("\n"):
                if "residual_after:" in line:
                    residual = line.split("residual_after:")[1].strip().split()[0] if "residual_after:" in line else "-"
                if "cleanup_attempted:" in line:
                    cleanup_attempted = line.split("cleanup_attempted:")[1].strip().split()[0] if "cleanup_attempted:" in line else "-"
                if "cleanup_result:" in line:
                    cleanup_result = line.split("cleanup_result:")[1].strip().split()[0] if "cleanup_result:" in line else "-"
            
            with metrics_col1:
                st.metric("exit_code", exit_code)
            with metrics_col2:
                st.metric("residual", residual)
            with metrics_col3:
                st.metric("cleanup", cleanup_attempted)
            
            # Detailed output
            with st.expander("📊 Detaylı Çıktı", expanded=exit_code != 0):
                st.text(stdout[-3000:] if len(stdout) > 3000 else stdout)
                if stderr:
                    st.error(stderr[-1000:] if len(stderr) > 1000 else stderr)
            
            # Clear button
            if st.button("🗑️ Sonuçları Temizle", key="btn_clear_proof_result"):
                for key in ["proof_cycle_exit_code", "proof_cycle_stdout", "proof_cycle_stderr"]:
                    st.session_state.pop(key, None)
                st.rerun()
        
        # NDJSON Event Viewer
        st.divider()
        st.markdown("### 📋 Son PROOF_* Events")
        
        ndjson_path = "/Users/alisaglam/TezaverMac/data/logs/live_events.ndjson"
        try:
            import json
            proof_events = []
            if os.path.exists(ndjson_path):
                with open(ndjson_path, "r") as f:
                    for line in f:
                        try:
                            event = json.loads(line.strip())
                            event_type = event.get("event_type", "")
                            if event_type.startswith("PROOF_") or event_type.startswith("ROUTER_POLICY"):
                                proof_events.append(event)
                        except:
                            pass
                
                # Show last 20
                proof_events = proof_events[-20:]
                
                if proof_events:
                    import pandas as pd
                    event_rows = []
                    for e in proof_events:
                        event_rows.append({
                            "ts": e.get("ts", "-")[:19] if e.get("ts") else "-",
                            "type": e.get("event_type", "-"),
                            "state": e.get("state", "-"),
                            "symbol": e.get("symbol", "-"),
                            "residual": e.get("residual_after", e.get("residual", "-")),
                            "dust_policy": e.get("dust_policy", "-"),
                        })
                    st.dataframe(pd.DataFrame(event_rows), use_container_width=True, hide_index=True)
                else:
                    st.info("PROOF_* event bulunamadı.")
            else:
                st.warning(f"NDJSON dosyası bulunamadı: {ndjson_path}")
        except Exception as e:
            st.error(f"NDJSON okuma hatası: {e}")
    
    # =========================================================================
    # Closed-bar Router (NEW)
    with st.expander("🔀 Closed-bar Router | Kapalı Bar Yönlendiricisi", expanded=False):
        st.caption("Kapalı bar tick'lerini MatrixLiveCluster'a yönlendir.")
        
        from tezaver.matrix.live.live_router import MatrixLiveRouter, LiveRouterConfig
        
        router_state = service.get_router_state()
        
        # Controls
        col1, col2 = st.columns(2)
        with col1:
            router_enabled = st.toggle("Router Enabled", value=False, key="router_enabled")
        with col2:
            router_dry_run = st.toggle("Force DRY RUN", value=True, key="router_dry_run")
        
        router_symbols = st.multiselect("Symbols", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], default=["BTCUSDT"], key="router_symbols")
        router_tf = st.selectbox("Timeframe", ["1m", "15m"], key="router_tf")
        
        # Hold Policy control
        st.divider()
        st.markdown("### 🎯 Hold Policy")
        
        hold_policy_col1, hold_policy_col2 = st.columns(2)
        with hold_policy_col1:
            router_hold_policy = st.selectbox(
                "Hold Policy",
                options=["OFF", "HOLD_NEXT_CLOSED"],
                index=0,
                help="OFF: no hold, HOLD_NEXT_CLOSED: OPEN→wait→CLOSE",
                key="router_hold_policy"
            )
        with hold_policy_col2:
            router_exchange_mode = st.selectbox(
                "Exchange Mode",
                options=["DRY_RUN", "DUMMY_ORDER", "REAL_TESTNET"],
                index=0,
                help="Policy order execution mode",
                key="router_exchange_mode"
            )
        
        # Status line
        if router_state.get("attached"):
            policy_status = router_state.get("hold_policy", "OFF")
            st.success(f"✅ Router ATTACHED | ticks={router_state.get('ticks', 0)} | policy={policy_status}")
        else:
            st.info("⛔ Router NOT attached")
        
        # Attach/Detach buttons
        col_attach, col_detach = st.columns(2)
        with col_attach:
            if st.button("▶️ Attach Router", type="primary", disabled=router_state.get("attached", False), key="btn_attach_router"):
                # Create router with config including policy
                config = LiveRouterConfig(
                    enabled=router_enabled,
                    force_dry_run=router_dry_run,
                    only_symbols=router_symbols if router_symbols else None,
                    only_timeframes=[router_tf] if router_tf else None,
                    # Policy config
                    hold_policy=router_hold_policy,
                    exchange_mode=router_exchange_mode,
                    armed=not router_dry_run,
                    exchange_enabled=not router_dry_run,
                )
                
                # Get gateway for policy if needed
                gateway = None
                if router_hold_policy == "HOLD_NEXT_CLOSED" and router_exchange_mode == "REAL_TESTNET":
                    try:
                        from tezaver.matrix.live.live_gateway import BinanceTestnetGateway
                        gateway = BinanceTestnetGateway()
                    except Exception as gw_err:
                        st.error(f"Gateway oluşturulamadı: {gw_err}")
                
                router = MatrixLiveRouter(cluster=None, config=config, gateway=gateway)
                service.set_on_closed_bar_callback(router.handle_snapshot)
                st.success("Router attached!")
                st.rerun()
        
        with col_detach:
            if st.button("⏹ Detach Router", disabled=not router_state.get("attached", False), key="btn_detach_router"):
                service.detach_router()
                st.warning("Router detached")
                st.rerun()
        
        # Router stats
        st.divider()
        st.markdown("**Router Stats:**")
        stats_cols = st.columns(4)
        with stats_cols[0]:
            st.metric("Ticks", router_state.get("ticks", 0))
        with stats_cols[1]:
            skip_count = router_state.get("skip_count", 0) if "skip_count" in str(router_state) else 0
            st.metric("Skips", skip_count)
        with stats_cols[2]:
            st.metric("Errors", router_state.get("error_count", 0))
        with stats_cols[3]:
            attached_str = "✅ YES" if router_state.get("attached") else "⛔ NO"
            st.metric("Attached", attached_str)
        
        # Last router tick
        last_tick = router_state.get("last_tick")
        if last_tick:
            st.markdown("### 🎯 Last Router Tick")
            st.code(f"ROUTER_OK | {last_tick.get('symbol')}/{last_tick.get('timeframe')} bar_close_ts={last_tick.get('bar_close_ts')} close={last_tick.get('close')} dry_run=True ticks={router_state.get('ticks', 0)}")
        
        # ARM gating check
        st.divider()
        arm_check = service.check_arm_allowed(router_enabled=router_enabled, exchange_enabled=False, exchange_mode="DRY_RUN")
        
        if arm_check.get("allowed"):
            st.success("🔫 ARMED toggle available")
        else:
            st.warning("🔒 ARMED not available. Missing requirements:")
            for reason in arm_check.get("missing_reasons", []):
                st.caption(f"  ⚠️ {reason}")
        
        st.caption(f"`ARMED_GATE | allowed={arm_check.get('allowed')} missing={arm_check.get('missing_reasons')}`")
    
    # =========================================================================
    # Proof+Router (E2E) Panel
    # =========================================================================
    with st.expander("🧾 Proof+Router (E2E) | Kanıt+Yönlendirici (Uçtan Uca)", expanded=False):
        st.caption("Tek butonla 15m bar kapanışını + router tick'ini kanıtla. Forced DRY RUN.")
        
        from tezaver.matrix.live.timeframe_utils import eta_to_next_close, format_eta
        from datetime import datetime, timezone as tz
        
        pr_state = service.get_proof_router_state()
        
        # Controls
        col1, col2, col3 = st.columns(3)
        with col1:
            pr_symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], key="pr_symbol")
        with col2:
            pr_tf = st.selectbox("Timeframe", ["15m", "1m"], key="pr_tf")
        with col3:
            pr_poll = st.slider("Poll (s)", 3, 10, 5, key="pr_poll")
        
        # ETA countdown
        now_utc = datetime.now(tz.utc)
        eta_sec, progress, next_close = eta_to_next_close(now_utc, pr_tf)
        eta_str = format_eta(eta_sec)
        
        st.caption(f"⏳ Next {pr_tf} close ETA: **{eta_str}** (UTC) | Next close: {next_close.strftime('%H:%M:%S')}")
        st.progress(progress)
        
        # Status line
        if pr_state.get("running"):
            st.success(f"PROOF+ROUTER RUNNING ✅ | run_id={pr_state.get('proof_run_id')} | ETA: {eta_str}")
        else:
            if pr_state.get("last_proof_event"):
                st.success("PROOF_OK + ROUTER_OK ✅")
            else:
                st.info("⛔ Proof+Router not running")
        
        if pr_state.get("last_error"):
            st.error(f"Error: {pr_state.get('last_error')}")
        
        # Buttons
        col_run, col_stop, col_refresh = st.columns(3)
        with col_run:
            if st.button("▶️ Run Proof+Router", type="primary", disabled=pr_state.get("running", False), key="btn_run_pr"):
                run_id = service.start_proof_router(
                    symbol=pr_symbol,
                    timeframe=pr_tf,
                    poll_sec=float(pr_poll),
                    use_real=True,
                )
                if run_id:
                    st.success(f"Started: {run_id}")
                    st.rerun()
        
        with col_stop:
            if st.button("⏹ Stop", disabled=not pr_state.get("running", False), key="btn_stop_pr"):
                service.stop_proof_closed()
                st.warning("Stopped")
                st.rerun()
        
        with col_refresh:
            if st.button("🔄 Refresh", key="btn_refresh_pr"):
                st.rerun()
        
        # Result card
        last_proof = pr_state.get("last_proof_event")
        if last_proof:
            st.divider()
            st.markdown("### 🎯 Proof+Router Result")
            
            # Proof metrics
            proof_cols = st.columns(5)
            with proof_cols[0]:
                st.metric("Symbol", f"{last_proof.get('symbol')}/{last_proof.get('timeframe')}")
            with proof_cols[1]:
                bar_close = last_proof.get("bar_close_ts", "-")
                st.metric("bar_close_ts", bar_close[:19] if bar_close else "-")
            with proof_cols[2]:
                lag = last_proof.get("lag_sec")
                st.metric("lag_sec", f"{lag:.1f}" if lag else "-")
            with proof_cols[3]:
                close = last_proof.get("close")
                st.metric("close", f"{close:.2f}" if close else "-")
            with proof_cols[4]:
                st.metric("strict", "✅" if last_proof.get("strict_new_closed") else "❌")
            
            # Router metrics
            router_cols = st.columns(3)
            with router_cols[0]:
                st.metric("Router Ticks", pr_state.get("router_ticks", 0))
            with router_cols[1]:
                st.metric("Router Skips", pr_state.get("router_skips", 0))
            with router_cols[2]:
                st.metric("dry_run", "TRUE ✅")
            
            # Result code
            st.code(f"PROOF_OK | {last_proof.get('symbol')}/{last_proof.get('timeframe')} baseline={last_proof.get('baseline_closed_ts', '-')[:19] if last_proof.get('baseline_closed_ts') else '-'} seen={last_proof.get('bar_close_ts', '-')[:19] if last_proof.get('bar_close_ts') else '-'} lag={last_proof.get('lag_sec', '-')} strict=True")
            st.code(f"ROUTER_OK | ticks={pr_state.get('router_ticks', 0)} skips={pr_state.get('router_skips', 0)} dry_run=True")
        
        # E2E History
        proof_history = service.get_proof_history()
        if proof_history:
            st.divider()
            st.markdown("### 📋 E2E History (Last 10)")
            
            import pandas as pd
            history_rows = []
            for p in proof_history:
                history_rows.append({
                    "ts": p.get("ts", "-")[:19] if p.get("ts") else "-",
                    "symbol": p.get("symbol"),
                    "tf": p.get("timeframe"),
                    "bar_close": p.get("bar_close_ts", "-")[:19] if p.get("bar_close_ts") else "-",
                    "lag": f"{p.get('lag_sec'):.1f}" if p.get("lag_sec") else "-",
                    "strict": "✅" if p.get("strict_new_closed") else "❌",
                })
            
            st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
    
    # =========================================================================
    # Proof+Router+Cluster (E2E) Panel
    # =========================================================================
    with st.expander("🧾 Proof+Router+Cluster (E2E) | Kanıt+Yönlendirici+Küme (Uçtan Uca)", expanded=False):
        st.caption("Proof + Router + Cluster (DRY RUN) tam E2E kanıtı. Forced DRY RUN.")
        
        from tezaver.matrix.live.timeframe_utils import eta_to_next_close, format_eta
        from datetime import datetime, timezone as tz
        
        prc_state = service.get_proof_router_cluster_state()
        
        # Controls
        col1, col2, col3 = st.columns(3)
        with col1:
            prc_symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "SOLUSDT"], key="prc_symbol")
        with col2:
            prc_tf = st.selectbox("Timeframe", ["15m", "1m"], key="prc_tf")
        with col3:
            prc_poll = st.slider("Poll (s)", 3, 10, 5, key="prc_poll")
        
        # ETA countdown
        now_utc = datetime.now(tz.utc)
        eta_sec, progress, next_close = eta_to_next_close(now_utc, prc_tf)
        eta_str = format_eta(eta_sec)
        
        st.caption(f"⏳ Next {prc_tf} close ETA: **{eta_str}** | Next close: {next_close.strftime('%H:%M:%S')} UTC")
        st.progress(progress)
        
        # Status line
        if prc_state.get("running"):
            st.success(f"✅ PROOF+ROUTER+CLUSTER RUNNING | run_id={prc_state.get('proof_run_id')} | ETA: {eta_str}")
        else:
            cluster_result = prc_state.get("cluster_last_result")
            if cluster_result:
                st.success(f"✅ PROOF_ROUTER_CLUSTER_OK | allow={cluster_result.get('allow')} dry_run=True order_id={cluster_result.get('order_id')}")
            else:
                st.info("⛔ Proof+Router+Cluster not running")
        
        if prc_state.get("last_error"):
            st.error(f"Error: {prc_state.get('last_error')}")
        
        # Buttons
        col_run, col_stop, col_refresh = st.columns(3)
        with col_run:
            if st.button("▶️ Run Proof+Router+Cluster", type="primary", disabled=prc_state.get("running", False), key="btn_run_prc"):
                run_id = service.start_proof_router_cluster(
                    symbol=prc_symbol,
                    timeframe=prc_tf,
                    poll_sec=float(prc_poll),
                    use_real=True,
                )
                if run_id:
                    st.success(f"Started: {run_id}")
                    st.rerun()
        
        with col_stop:
            if st.button("⏹ Stop", disabled=not prc_state.get("running", False), key="btn_stop_prc"):
                service.stop()
                st.warning("Stopped")
                st.rerun()
        
        with col_refresh:
            if st.button("🔄 Refresh", key="btn_refresh_prc"):
                st.rerun()
        
        # Result cards - 3 columns
        last_proof = prc_state.get("last_proof_event")
        last_router = prc_state.get("router_last_tick")
        cluster_result = prc_state.get("cluster_last_result")
        
        if last_proof or last_router or cluster_result:
            st.divider()
            
            card_cols = st.columns(3)
            
            # Proof card
            with card_cols[0]:
                st.markdown("**📋 Proof Result**")
                if last_proof:
                    st.metric("bar_close_ts", last_proof.get("bar_close_ts", "-")[:19] if last_proof.get("bar_close_ts") else "-")
                    lag = last_proof.get("lag_sec")
                    st.metric("lag_sec", f"{lag:.1f}" if lag else "-")
                    st.metric("strict", "✅" if last_proof.get("strict_new_closed") else "❌")
                else:
                    st.caption("No proof yet")
            
            # Router card
            with card_cols[1]:
                st.markdown("**🔀 Router Result**")
                st.metric("Ticks", prc_state.get("router_ticks", 0))
                st.metric("Skips", prc_state.get("router_skips", 0))
                if last_router:
                    st.metric("close", last_router.get("close", "-"))
            
            # Cluster card
            with card_cols[2]:
                st.markdown("**🎯 Cluster Result**")
                if cluster_result:
                    st.metric("allow", "✅" if cluster_result.get("allow") else "❌")
                    st.metric("decisions", cluster_result.get("decisions_count", 0))
                    st.metric("dry_run", "TRUE ✅")
                    st.metric("order_id", cluster_result.get("order_id", "-"))
                else:
                    st.caption("No cluster result yet")
            
            # E2E proof line
            if cluster_result:
                bar_close = last_proof.get("bar_close_ts", "-")[:19] if last_proof and last_proof.get("bar_close_ts") else "-"
                close = last_proof.get("close") if last_proof else "-"
                st.code(f"PROOF_ROUTER_CLUSTER_OK | {prc_symbol}/{prc_tf} bar_close_ts={bar_close} close={close} allow={cluster_result.get('allow')} dry_run=True order_id={cluster_result.get('order_id')} decisions={cluster_result.get('decisions_count')}")
        
        # History table
        prc_history = prc_state.get("history", [])
        if prc_history:
            st.divider()
            st.markdown("### 📋 E2E History (Last 20)")
            
            import pandas as pd
            history_rows = []
            for h in prc_history[-20:]:
                history_rows.append({
                    "ts": h.get("ts", "-")[:19] if h.get("ts") else "-",
                    "symbol": h.get("symbol"),
                    "tf": h.get("timeframe"),
                    "bar_close": h.get("bar_close_ts", "-")[:19] if h.get("bar_close_ts") else "-",
                    "allow": "✅" if h.get("allow") else "❌",
                    "decisions": h.get("decisions_count", 0),
                    "dry_run": "✅" if h.get("dry_run") else "❌",
                })
            
            st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
    
    # =========================================================================
    # 🧭 Live Ops Console
    # =========================================================================
    with st.expander("🧭 Live Ops Console | Canlı Operasyon Konsolu", expanded=False):
        st.caption("Cells, positions, signals, policy, gates - tüm Live durumunu izle.")
        
        import pandas as pd
        
        router_state = service.get_router_state()
        
        # ========== Controls Row ==========
        ctrl_cols = st.columns(5)
        with ctrl_cols[0]:
            ops_force_dry = st.toggle("🚨 Force DRY RUN", value=True, key="ops_force_dry_run", help="Panic switch - forces DRY RUN")
        with ctrl_cols[1]:
            ops_pause_all = st.toggle("⏸️ Pause All", value=False, key="ops_pause_all", help="Global pause")
        with ctrl_cols[2]:
            st.metric("Router", "🟢 ON" if router_state.get("attached") else "⛔ OFF")
        with ctrl_cols[3]:
            st.metric("Ticks", router_state.get("ticks", 0))
        with ctrl_cols[4]:
            gates_ok = router_state.get("gates_passed", True)
            st.metric("Gates", "✅ PASS" if gates_ok else "⛔ FAIL")
        
        # ========== 🎛️ Strategy Controls ==========
        st.divider()
        st.markdown("### 🎛️ Strategy Controls")
        
        strat_cols = st.columns(4)
        with strat_cols[0]:
            strat_open_rule = st.selectbox(
                "Open Rule Mode",
                options=["ALWAYS_OFF", "AUTO_OPEN_FLAT", "CARD_STRICT_WINDOW", "CARD_SOURCE_WINDOW"],
                index=0,
                key="strat_open_rule_mode",
                help="ALWAYS_OFF: no opens, AUTO_OPEN_FLAT: V1 testing"
            )
        with strat_cols[1]:
            strat_cooldown = st.slider(
                "Cooldown (bars)",
                min_value=1,
                max_value=10,
                value=1,
                key="strat_cooldown_bars",
                help="Min bars between actions"
            )
        with strat_cols[2]:
            strat_contract = st.radio(
                "Contract Enforce",
                options=["WARN", "BLOCK"],
                index=0,
                key="strat_contract_enforce",
                help="BLOCK: suppress OPEN if contract violated"
            )
        with strat_cols[3]:
            strat_profile = st.selectbox(
                "Profile",
                options=["SILVER_15m", "SNIPER_V4"],
                index=0,
                key="strat_profile_id",
                help="Strategy profile for filter windows"
            )
        
        # Strategy Status
        strat_status_cols = st.columns(4)
        with strat_status_cols[0]:
            st.caption(f"**Mode**: {strat_open_rule}")
        with strat_status_cols[1]:
            st.caption(f"**Cooldown**: {strat_cooldown} bars")
        with strat_status_cols[2]:
            st.caption(f"**Contract**: {strat_contract}")
        with strat_status_cols[3]:
            st.caption(f"**Profile**: {strat_profile}")
        
        # ========== Helper: load_ndjson_events ==========
        def load_ndjson_events(limit: int = 20, event_types: list = None) -> list:
            """Load recent events from NDJSON log file, optionally filtered by event type."""
            from tezaver.matrix.live.logs_tail import read_ndjson_tail, filter_events
            
            ndjson_path = "data/logs/live_events.ndjson"
            result = read_ndjson_tail(ndjson_path, n=limit * 5)  # Read more to account for filtering
            events = result.get("events", [])
            
            if event_types:
                events = filter_events(events, include_types=set(event_types))
            
            # Return most recent first, limited to requested count
            return list(reversed(events[-limit:]))
        
        # ========== 🌐 Global Risk ==========
        st.divider()
        st.markdown("### 🌐 Global Risk Limiter")
        
        risk_cols = st.columns(4)
        with risk_cols[0]:
            risk_max_total = st.number_input(
                "Max Total Notional ($)",
                min_value=0.0,
                value=500.0,
                step=50.0,
                key="risk_max_total_notional",
                help="Max total notional USDT across all cells"
            )
        with risk_cols[1]:
            risk_max_cell = st.number_input(
                "Max Cell Notional ($)",
                min_value=0.0,
                value=300.0,
                step=50.0,
                key="risk_max_cell_notional",
                help="Max notional USDT per cell"
            )
        with risk_cols[2]:
            risk_max_pos = st.slider(
                "Max Positions",
                min_value=1,
                max_value=10,
                value=3,
                key="risk_max_positions",
                help="Max concurrent open positions"
            )
        with risk_cols[3]:
            risk_enforce = st.radio(
                "Enforce Mode",
                options=["BLOCK", "WARN"],
                index=0,
                key="risk_enforce_mode",
                help="BLOCK: reject order, WARN: log only"
            )
        
        # Risk Status (from last NDJSON events)
        risk_events = load_ndjson_events(limit=20, event_types=["RISK_LIMIT_CHECK", "RISK_LIMIT_BLOCK"])
        if risk_events:
            last_risk = risk_events[0]
            st.caption(f"**Last Check**: {last_risk.get('decision', 'N/A')} | Cell: {last_risk.get('cell_notional', 0):.0f}$ | Total: {last_risk.get('total_notional', 0):.0f}$")
        
        # ========== 🧩 Restart Reconciliation ==========
        st.divider()
        st.markdown("### 🧩 Restart Reconciliation")
        
        recon_cols = st.columns([3, 1])
        with recon_cols[0]:
            st.caption("Load persisted state, check exchange positions, detect residuals")
        with recon_cols[1]:
            if st.button("▶️ Run Reconcile", key="btn_run_reconcile"):
                import subprocess
                cmd = [
                    "./venv/bin/python", "-m", "tezaver.matrix.live.live_loop",
                    "reconcile",
                    "--symbols", "BTCUSDT",
                    "--tf", "1m",
                    "--exchange-mode", "DUMMY_ORDER",
                ]
                st.code(" ".join(cmd), language="bash")
                st.info("Run this command in terminal to test reconciliation.")
        
        # Show last RECON events
        recon_events = load_ndjson_events(limit=10, event_types=["RECON_START", "RECON_DONE", "RECON_WARN"])
        if recon_events:
            last_recon = recon_events[0]
            if last_recon.get("event_type") == "RECON_DONE":
                status = "✅ OK" if last_recon.get("ok", True) else "⚠️ WARNINGS"
                st.caption(f"**Last Reconcile**: {status} | Cells: {last_recon.get('cell_count', 0)} | Paused: {len(last_recon.get('paused_cells', []))}")
                if last_recon.get("warnings"):
                    for w in last_recon.get("warnings", [])[:3]:
                        st.caption(f"  ⚠️ {w}")
        
        # ========== 🪪 Card Governance ==========
        st.divider()
        st.markdown("### 🪪 Card Governance")
        
        card_gov_cols = st.columns(4)
        with card_gov_cols[0]:
            card_gate_enabled = st.toggle("Card Gate", value=True, key="card_gate_enabled_toggle")
        with card_gov_cols[1]:
            card_max_age = st.slider("Max Age (hrs)", min_value=12, max_value=168, value=72, key="card_max_age_slider")
        with card_gov_cols[2]:
            card_min_pass = st.slider("Min Pass Rate", min_value=0.0, max_value=0.5, value=0.2, step=0.05, key="card_min_pass_slider")
        with card_gov_cols[3]:
            card_enforce = st.radio("Enforce", ["BLOCK", "WARN"], index=0, horizontal=True, key="card_enforce_radio")
        
        # Show last CARD_GATE_EVAL events
        card_events = load_ndjson_events(limit=5, event_types=["CARD_GATE_EVAL"])
        if card_events:
            last_card = card_events[0]
            gate = last_card.get("gate", "NA")
            gate_icon = "✅" if gate == "PASS" else ("⚠️" if gate == "WARN" else ("🚫" if gate == "BLOCK" else "❔"))
            st.caption(f"**Last Card Gate**: {gate_icon} {gate} | allow={last_card.get('allow', True)} | violations={last_card.get('violations', [])[:2]}")
        
        # ========== One-click E2E Button ==========
        st.divider()
        e2e_cols = st.columns([3, 1])
        with e2e_cols[0]:
            st.markdown("#### ▶️ One-click E2E Test")
            st.caption("1m OPEN→CLOSE cycle with current settings")
        with e2e_cols[1]:
            if st.button("▶️ Run 1m E2E", type="primary", key="btn_run_1m_e2e"):
                import subprocess
                cmd = [
                    "./venv/bin/python", "-m", "tezaver.matrix.live.live_loop",
                    "proof_router_cluster",
                    "--real", "--tf", "1m", "--poll", "5",
                    "--exchange-mode", "REAL_TESTNET",
                    "--armed", "--no-force-dry-run", "--exchange-enabled",
                    "--hold-policy", "HOLD_NEXT_CLOSED",
                    "--until-done",
                    "--dust-policy", "FLATTEN_AFTER",
                    "--dust-threshold", "0.001",
                ]
                env = os.environ.copy()
                env["PYTHONPATH"] = "src"
                
                with st.spinner("Running 1m E2E cycle..."):
                    try:
                        result = subprocess.run(cmd, cwd="/Users/alisaglam/TezaverMac", env=env, capture_output=True, text=True, timeout=300)
                        if result.returncode == 0:
                            # Extract summary line
                            summary_line = [l for l in result.stdout.split("\\n") if "POLICY_DONE" in l or "PROOF_ROUTER_CLUSTER_POLICY_OK" in l]
                            if summary_line:
                                st.success(summary_line[-1])
                            else:
                                st.success("E2E OK!")
                            st.code(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
                        else:
                            st.error(f"Exit code: {result.returncode}")
                            st.code(result.stderr[:1000] if result.stderr else result.stdout[:1000])
                    except subprocess.TimeoutExpired:
                        st.error("Timeout (5min)")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # ========== Cells Status Table ==========
        st.divider()
        st.markdown("### 📊 Cells Status")
        
        # Build cells data from router state
        cells_data = []
        last_tick = router_state.get("last_tick")
        if last_tick:
            cells_data.append({
                "Cell": f"{last_tick.get('symbol')}/{last_tick.get('timeframe')}",
                "bar_close_ts": str(last_tick.get("bar_close_ts", "-"))[:19],
                "close": last_tick.get("close"),
                "signal": router_state.get("hold_policy", "OFF"),
                "policy": router_state.get("hold_policy", "OFF"),
                "gates": "✅" if router_state.get("gates_passed", True) else "⛔",
                "mode": router_state.get("exchange_mode", "DRY_RUN"),
            })
        
        if cells_data:
            st.dataframe(pd.DataFrame(cells_data), use_container_width=True, hide_index=True)
        else:
            st.info("No active cells yet. Start Router to see data.")
        
        # ========== Position State Table ==========
        st.divider()
        st.markdown("### 📈 Position State")
        
        # Get positions from strategy if available
        # Placeholder - PositionStateStore would be accessed here
        positions_data = []
        if last_tick:
            positions_data.append({
                "Cell": f"{last_tick.get('symbol')}/{last_tick.get('timeframe')}",
                "State": "FLAT",  # Would come from PositionStateStore
                "Open TS": "-",
                "Close TS": "-",
                "Cooldown": "0 bars",
            })
        
        if positions_data:
            st.dataframe(pd.DataFrame(positions_data), use_container_width=True, hide_index=True)
        else:
            st.info("No position data. Run a proof cycle to see data.")
        
        # ========== NDJSON Tail Viewer ==========
        st.divider()
        st.markdown("### 📋 Live Events (NDJSON)")
        
        # Preset filter buttons
        filter_cols = st.columns(6)
        with filter_cols[0]:
            if st.button("ALL", key="ndjson_all"):
                st.session_state["ndjson_filter"] = None
        with filter_cols[1]:
            if st.button("STRATEGY", key="ndjson_strategy"):
                st.session_state["ndjson_filter"] = "STRATEGY_SIGNAL"
        with filter_cols[2]:
            if st.button("ORDER", key="ndjson_order"):
                st.session_state["ndjson_filter"] = "ORDER_"
        with filter_cols[3]:
            if st.button("GUARDRAIL", key="ndjson_guardrail"):
                st.session_state["ndjson_filter"] = "GUARDRAIL"
        with filter_cols[4]:
            if st.button("POLICY", key="ndjson_policy"):
                st.session_state["ndjson_filter"] = "POLICY"
        with filter_cols[5]:
            ndjson_limit = st.selectbox("Limit", [20, 50, 100, 200], key="ndjson_limit")
        
        # Load and display NDJSON events
        ndjson_path = "data/logs/live_events.ndjson"
        import json
        from pathlib import Path
        
        events = []
        if Path(ndjson_path).exists():
            try:
                with open(ndjson_path, "r") as f:
                    lines = f.readlines()
                    for line in lines[-ndjson_limit:]:
                        try:
                            evt = json.loads(line.strip())
                            # Apply filter
                            filter_val = st.session_state.get("ndjson_filter")
                            if filter_val is None or filter_val in evt.get("event_type", ""):
                                events.append({
                                    "ts": str(evt.get("ts", "-"))[:19],
                                    "type": evt.get("event_type", "-"),
                                    "symbol": evt.get("symbol", "-"),
                                    "action": evt.get("action") or evt.get("signal") or "-",
                                    "success": evt.get("success", "-"),
                                })
                        except:
                            pass
            except:
                pass
        
        if events:
            st.dataframe(pd.DataFrame(events[::-1]), use_container_width=True, hide_index=True, height=300)
        else:
            st.info("No events yet. Run a proof cycle to generate events.")
    
    # =========================================================================
    # Exchange & Arm Controls (Phase-1)
    # =========================================================================
    with st.expander("⚙️ Exchange & Arm Controls | Borsa & Yetkilendirme Kontrolleri", expanded=False):
        st.caption("Exchange mode ve ARMED kontrolü. DUMMY_ORDER modunda secrets gerekmez.")
        
        from tezaver.matrix.live.live_gateway import ExchangeMode
        
        # Controls row
        ctrl_cols = st.columns(4)
        
        with ctrl_cols[0]:
            exchange_enabled = st.toggle("Exchange Enabled", value=False, key="exchange_enabled_toggle")
        
        with ctrl_cols[1]:
            exchange_mode = st.selectbox(
                "Exchange Mode",
                options=["DRY_RUN", "DUMMY_ORDER", "REAL_TESTNET", "REAL_MAINNET"],
                index=0,
                key="exchange_mode_select",
            )
        
        with ctrl_cols[2]:
            global_paused = st.toggle("⏸️ Global Pause", value=False, key="global_pause_toggle")
        
        with ctrl_cols[3]:
            st.metric("Mode", exchange_mode)
        
        # ARMED gating check
        router_state = service.get_router_state()
        router_attached = router_state.get("attached", False)
        
        arm_check = service.check_arm_allowed(
            router_enabled=router_attached,
            exchange_enabled=exchange_enabled,
            exchange_mode=exchange_mode,
        )
        
        st.divider()
        
        # ARMED checkbox with gating
        if arm_check.get("allowed"):
            st.success("✅ ARMED can be enabled")
            armed_enabled = st.checkbox("🔫 ARMED", value=False, key="armed_checkbox", disabled=False)
            if armed_enabled:
                st.warning("⚠️ ARMED: Orders will be submitted!")
        else:
            st.warning("🔒 ARMED not available. Missing requirements:")
            for reason in arm_check.get("missing_reasons", []):
                st.caption(f"  ⚠️ {reason}")
            st.checkbox("🔫 ARMED", value=False, key="armed_checkbox_disabled", disabled=True)
        
        # Status summary
        st.divider()
        st.markdown("**Summary:**")
        summary_cols = st.columns(4)
        with summary_cols[0]:
            st.metric("ExchangeMode", arm_check.get("exchange_mode", "-"))
        with summary_cols[1]:
            st.metric("Requires Secrets", "YES" if arm_check.get("requires_secrets") else "NO")
        with summary_cols[2]:
            st.metric("Router Attached", "✅" if router_attached else "❌")
        with summary_cols[3]:
            st.metric("Allowed to ARM", "✅" if arm_check.get("allowed") else "❌")
    
    # =========================================================================
    # Secrets Vault Panel (Phase-1)
    # =========================================================================
    with st.expander("🔐 Secrets Vault | Gizli Anahtar Kasası", expanded=False):
        st.caption("API key/secret yönetimi. REAL mode için gerekli, DUMMY_ORDER için gerekmez.")
        
        from tezaver.matrix.live.secrets import get_vault_status
        
        # Source selection
        vault_cols = st.columns(2)
        with vault_cols[0]:
            vault_source = st.radio("Vault Source", ["ENV", "FILE"], key="vault_source_radio", horizontal=True)
        with vault_cols[1]:
            if vault_source == "FILE":
                file_path = st.text_input("File Path", value="data/secrets/live_keys.txt", key="secrets_file_path")
            else:
                file_path = ""
                st.caption("Using environment variables")
        
        # Get vault status
        vault_status = get_vault_status(source=vault_source, file_path=file_path)
        
        st.divider()
        
        # Key status display
        st.markdown("**Key Status:**")
        key_cols = st.columns(2)
        with key_cols[0]:
            api_key_status = vault_status.get("api_key_status", "MISSING")
            if api_key_status == "FOUND":
                st.success("✅ API_KEY: FOUND")
            else:
                st.error("❌ API_KEY: MISSING")
        with key_cols[1]:
            api_secret_status = vault_status.get("api_secret_status", "MISSING")
            if api_secret_status == "FOUND":
                st.success("✅ API_SECRET: FOUND")
            else:
                st.error("❌ API_SECRET: MISSING")
        
        # Permission warning
        file_perms = vault_status.get("file_permissions")
        if file_perms:
            if not file_perms.get("is_secure"):
                st.warning(f"⚠️ {file_perms.get('warning', 'File permissions issue')}")
            else:
                st.success(f"✅ File permissions: {file_perms.get('mode')} (secure)")
        
        # Warnings
        for warning in vault_status.get("warnings", []):
            st.warning(f"⚠️ {warning}")
        
        # Setup hints
        st.divider()
        st.markdown("**Setup Hints:**")
        if vault_source == "ENV":
            st.code("""# Add to your shell profile (.bashrc, .zshrc, etc.)
export BINANCE_API_KEY=your_api_key_here
export BINANCE_API_SECRET=your_api_secret_here""", language="bash")
        else:
            st.code("""{
    "BINANCE_API_KEY": "***REDACTED***",
    "BINANCE_API_SECRET": "***REDACTED***"
}""", language="json")
            st.caption("⚠️ Set file permissions: chmod 600 <file_path>")
    
    # =========================================================================
    # Live Gate Status (existing)
    # =========================================================================
    with st.expander("🎮 Live Gate Status | Canlı Kapı Durumu", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            armed_mode = st.toggle("🔫 Armed Mode", value=False, key="live_armed_mode")
            if armed_mode:
                st.warning("⚠️ ARMED: Gerçek order gönderilecek!")
            else:
                st.info("💤 DRY RUN: Sadece simülasyon")
        with col2:
            st.metric("Data", "public ✅")
        with col3:
            st.metric("Trade", "private 🔒")
        
        st.markdown("**🚦 Gate Status:**")
        from tezaver.matrix.live.live_cluster import live_can_trade
        
        gate_rows = []
        live_eligible = [r for r in rows if (r.get("live_eligible") if isinstance(r, dict) else getattr(r, "live_eligible", False))]
        selection_mode = st.session_state.get("live_selection_mode", "ARENA_FILTERS")
        
        def _get(obj, key, default=None):
            """Get attribute from dict or dataclass."""
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)
        
        for row in live_eligible[:5]:  # Limit to 5 for display
            allow, details = live_can_trade(
                symbol=_get(row, "symbol"),
                timeframe=_get(row, "timeframe"),
                profile_id=_get(row, "profile_id"),
                profile_status=_get(row, "status"),
                selection_mode=selection_mode,
            )
            
            gates = details.get("gates", {})
            contract_gate = details.get("contract_gate", "NA")
            
            # Extract violation codes from violation objects
            violations = details.get("violations", [])
            viol_codes = []
            for v in violations:
                if isinstance(v, dict):
                    viol_codes.append(v.get("code", "?"))
                else:
                    viol_codes.append(str(v))
            
            gate_rows.append({
                "Cell": f"{_get(row, 'symbol')}/{_get(row, 'timeframe')}",
                "Profile": str(_get(row, 'profile_id', ''))[:20],
                "Allowed?": "✅ YES" if allow else "❌ NO",
                "ProfileGate": "✅" if gates.get("profile_status", {}).get("passed") else "❌",
                "RiskGate": "✅" if gates.get("risk_contract", {}).get("passed") else "❌",
                "ContractGate": contract_gate,
                "Violations": ",".join(viol_codes) if viol_codes else "-",
            })
        
        if gate_rows:
            import pandas as pd
            st.dataframe(pd.DataFrame(gate_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Live eligible profil bulunamadı.")
    
    # =========================================================================
    # NDJSON Tail Viewer
    # =========================================================================
    with st.expander("📜 NDJSON Tail Viewer | NDJSON Log Görüntüleyici", expanded=False):
        st.caption("Live event log dosyasından son N satır.")
        
        from tezaver.matrix.live.logs_tail import read_ndjson_tail, filter_events, events_to_table_rows
        
        tail_cols = st.columns(4)
        with tail_cols[0]:
            ndjson_path = st.text_input("NDJSON Path", value="data/logs/live_events.ndjson", key="ndjson_path_input")
        with tail_cols[1]:
            last_n = st.slider("Last N lines", min_value=50, max_value=2000, value=200, key="ndjson_last_n")
        with tail_cols[2]:
            event_types = st.multiselect(
                "Event Types", 
                options=["ROUTER_TICK", "ROUTER_CLUSTER_TICK", "ROUTER_CLUSTER_EXEC_SUMMARY", 
                         "ORDER_SUBMIT", "ORDER_RESULT", "ORDER_BLOCKED", "PROOF_CLOSED"],
                default=["ROUTER_CLUSTER_EXEC_SUMMARY"],
                key="ndjson_event_types"
            )
        with tail_cols[3]:
            symbol_filter = st.text_input("Symbol Filter", value="", key="ndjson_symbol_filter")
        
        if st.button("🔄 Refresh Tail", key="btn_refresh_tail"):
            st.rerun()
        
        # Read and display
        tail_result = read_ndjson_tail(ndjson_path, n=last_n)
        
        if tail_result.get("error"):
            st.warning(f"⚠️ {tail_result.get('error')}")
        
        # Filter events
        filtered = filter_events(
            tail_result.get("events", []),
            include_types=set(event_types) if event_types else None,
            symbol=symbol_filter if symbol_filter else None,
        )
        
        # Summary
        st.markdown(f"**Lines read:** {tail_result.get('lines_read', 0)} | **Parse errors:** {tail_result.get('parse_errors', 0)} | **Shown:** {len(filtered)}")
        
        # Table
        if filtered:
            import pandas as pd
            rows = events_to_table_rows(filtered[-100:])  # Limit display
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No events matching filters.")
    
    # =========================================================================
    # Last Orders (per cell)
    # =========================================================================
    with st.expander("🧾 Last Orders (per cell) | Son Emirler (hücre bazında)", expanded=False):
        st.caption("Her cell için son ORDER_SUBMIT/ORDER_RESULT durumu.")
        
        from tezaver.matrix.live.order_state import get_order_state_store
        
        order_store = get_order_state_store()
        cells_list = order_store.get_cells_list()
        
        if cells_list:
            import pandas as pd
            st.dataframe(pd.DataFrame(cells_list), use_container_width=True, hide_index=True)
        else:
            st.info("Henüz order state yok. proof_router_cluster çalıştırın.")
        
        if st.button("🧹 Clear All Cell State", key="btn_clear_order_state"):
            order_store.clear()
            st.success("Order state temizlendi.")
            st.rerun()
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        initial_capital = st.number_input(
            "Başlangıç sermaye (her cell için)",
            min_value=10.0,
            max_value=1_000_000.0,
            value=100.0,
            step=10.0,
            key="live_initial_capital",
        )
    with col2:
        risk_mode = st.selectbox(
            "Risk modu",
            options=["contract", "experiment"],
            index=0,
            key="live_risk_mode",
        )
    
    if st.button("📡 Live Cluster Oluştur", type="primary", use_container_width=True):
        _render_live_cluster_preview(rows, initial_capital, risk_mode)
    
    st.divider()
    
    st.subheader("📊 Live Monitor")
    _render_live_monitor_section(rows, initial_capital)


    """Live cell state monitor section."""
    st.subheader("📡 Live Durum – Hesap & İşlem Özeti")

    st.caption(
        "Matrix Live cluster'daki LIVE-eligible hücrelerin disk üzerindeki state dosyalarından "
        "okunan equity ve işlem özeti. State dosyaları: `data/live_state/...`"
    )

    # Get LIVE eligible rows
    live_rows = [r for r in rows if getattr(r, 'live_eligible', False)]

    if not live_rows:
        st.info("Henüz LIVE için uygun profil yok. Strategy Board'dan en az bir profil APPROVED + risk_contract ile işaretlenmeli.")
        return

    from tezaver.matrix.live.live_state_tools import load_live_cell_state
    import pandas as pd

    summaries = []
    for row in live_rows:
        state = load_live_cell_state(
            symbol=row.symbol,
            timeframe=row.timeframe,
            profile_id=row.profile_id,
            initial_capital=initial_capital,
        )

        summaries.append({
            "Coin": state.symbol,
            "TF": state.timeframe,
            "Profil": state.profile_id[:25] + "..." if len(state.profile_id) > 28 else state.profile_id,
            "Equity": f"{state.equity:.2f}" if state.equity else "-",
            "PnL %": f"{state.pnl_pct:+.2f}%" if state.pnl_pct else "-",
            "İşlem": state.trade_count,
            "Son İşlem": state.last_side or "-",
            "Son PnL": f"{state.last_pnl:+.2f}" if state.last_pnl else "-",
        })

    st.dataframe(summaries, use_container_width=True)

def _render_live_monitor_section(rows: List[ProfileBoardRow], initial_capital: float) -> None:
    """Live cell state monitor section."""
    st.subheader("📡 Live Durum – Hesap & İşlem Özeti")

    st.caption(
        "Matrix Live cluster'daki LIVE-eligible hücrelerin disk üzerindeki state dosyalarından "
        "okunan equity ve işlem özeti. State dosyaları: `data/live_state/...`"
    )

    # Get LIVE eligible rows
    live_rows = [r for r in rows if getattr(r, 'live_eligible', False)]

    if not live_rows:
        st.info("Henüz LIVE için uygun profil yok. Strategy Board'dan en az bir profil APPROVED + risk_contract ile işaretlenmeli.")
        return

    from tezaver.matrix.live.live_state_tools import load_live_cell_state
    import pandas as pd

    summaries = []
    for row in live_rows:
        state = load_live_cell_state(
            symbol=row.symbol,
            timeframe=row.timeframe,
            profile_id=row.profile_id,
            initial_capital=initial_capital,
        )

        summaries.append({
            "Coin": state.symbol,
            "TF": state.timeframe,
            "Profil": state.profile_id[:25] + "..." if len(state.profile_id) > 28 else state.profile_id,
            "Equity": f"{state.equity:.2f}" if state.equity else "-",
            "PnL %": f"{state.pnl_pct:+.2f}%" if state.pnl_pct else "-",
            "İşlem": state.trade_count,
            "Son İşlem": state.last_side or "-",
            "Son PnL": f"{state.last_pnl:+.2f}" if state.last_pnl else "-",
        })

    st.dataframe(summaries, use_container_width=True)
