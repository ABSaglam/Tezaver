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



def render_matrix_operator_tab() -> None:
    """
    Matrix Tek Ekran Kokpit.
    
    Single-screen cockpit with:
    - Top fixed strip (Preset, Safety, Scope, Start/Stop, Status)
    - 3 Critical cards (Locks, Position Summary, Last Alarm)
    - Trade Replay main content
    - Default-closed expanders (Events, Bundles, Resolved Settings)
    """
    from pathlib import Path
    from tezaver.ui.matrix_presets import (
        get_preset, resolve_preset, preset_help_text, 
        get_preset_names, get_preset_labels, SAFETY_LEVELS
    )
    from tezaver.matrix.live.live_loop_service import LiveLoopService
    from tezaver.ui.matrix_operator_data import load_ndjson_tail, summarize_health
    
    st.markdown("## 🧭 Matrix Kokpit")
    
    # === Session State Defaults ===
    if "matrix_preset" not in st.session_state:
        st.session_state["matrix_preset"] = "CANLI"
    if "matrix_running" not in st.session_state:
        st.session_state["matrix_running"] = False
    
    # === A) ÜST SABİT ŞERİT ===
    strip_cols = st.columns([2, 1.5, 2, 1, 1, 2])
    
    # A1) Profil Dropdown
    with strip_cols[0]:
        preset_labels = get_preset_labels()
        preset_options = list(preset_labels.keys())
        selected_preset = st.selectbox(
            "Profil",
            options=preset_options,
            format_func=lambda x: preset_labels[x],
            index=preset_options.index(st.session_state["matrix_preset"]),
            key="kokpit_preset",
            help=preset_help_text("profil"),
        )
        st.session_state["matrix_preset"] = selected_preset
    
    preset = get_preset(selected_preset)
    
    # A2) Güvenlik Seviyesi
    with strip_cols[1]:
        safety = st.selectbox(
            "Güvenlik",
            options=SAFETY_LEVELS,
            index=SAFETY_LEVELS.index(preset.safety_level) if preset.safety_level in SAFETY_LEVELS else 1,
            key="kokpit_safety",
            help=preset_help_text("guvenlik_seviyesi"),
        )
    
    # A3) Kapsam (Allowlist + TF)
    with strip_cols[2]:
        scope_text = f"{', '.join(preset.allowlist[:2])}{'...' if len(preset.allowlist) > 2 else ''} | {', '.join(preset.timeframes)}"
        st.text_input("Kapsam", value=scope_text, disabled=True, key="kokpit_scope",
                      help=preset_help_text("allowlist"))
    
    # A4) Başlat / Durdur
    with strip_cols[3]:
        is_running = st.session_state.get("matrix_running", False)
        if st.button("🛑 Durdur" if is_running else "▶️ Başlat",
                     type="primary" if not is_running else "secondary",
                     use_container_width=True, key="kokpit_startstop"):
            st.session_state["matrix_running"] = not is_running
            st.rerun()
    
    # A5) Durum
    with strip_cols[4]:
        status_text = "ÇALIŞIYOR" if is_running else "DURDU"
        if is_running:
            st.success(f"✅ {status_text}")
        else:
            st.warning(f"⏸ {status_text}")
    
    # A6) Son Paket Link (if BLOCK)
    with strip_cols[5]:
        # Check for recent BLOCK
        ndjson_path = Path("data/logs/live_events.ndjson")
        last_block_reason = None
        if ndjson_path.exists():
            events = load_ndjson_tail(ndjson_path, max_lines=50)
            health = summarize_health(events)
            if health.get("incident_bundle"):
                last_block_reason = health["incident_bundle"].get("reason", "")[:30]
        
        if last_block_reason:
            st.error(f"⛔ {last_block_reason}")
        else:
            st.info("✓ Temiz")
    
    st.divider()
    
    # === B) 3 KRİTİK KART ===
    card_cols = st.columns(3)
    
    # Get real lock states from telemetry
    from tezaver.ui.matrix_operator_data import summarize_locks_from_ndjson
    lock_states = summarize_locks_from_ndjson(ndjson_path, tail_n=2000)
    
    def state_to_icon(state: str) -> str:
        """Convert state to emoji icon."""
        if state == "PASS":
            return "✅"
        elif state == "WARN":
            return "⚠️"
        elif state == "BLOCK":
            return "⛔"
        else:  # UNKNOWN
            return "❓"
    
    # B1) Kilitler
    with card_cols[0]:
        st.markdown("##### 🔒 Kilitler")
        locks = [
            ("Ön Kontrol", state_to_icon(lock_states["preflight"]["state"])),
            ("Kart Kapısı", state_to_icon(lock_states["card_gate"]["state"])),
            ("Risk Freni", state_to_icon(lock_states["risk"]["state"])),
            ("Reconcile", state_to_icon(lock_states["reconcile"]["state"])),
        ]
        lock_line = " | ".join([f"{l[0]} {l[1]}" for l in locks])
        st.caption(lock_line)
        
        # Show reason if any BLOCK
        for name, key in [("Ön Kontrol", "preflight"), ("Kart Kapısı", "card_gate"), 
                          ("Risk Freni", "risk"), ("Reconcile", "reconcile")]:
            if lock_states[key]["state"] == "BLOCK" and lock_states[key].get("reason"):
                st.caption(f"⛔ {name}: {lock_states[key]['reason'][:40]}")
                break
    
    # B2) Pozisyon Özeti (real data from account page)
    with card_cols[1]:
        st.markdown("##### 💼 Pozisyon Özeti")
        try:
            from tezaver.ui.subpages.account_page import get_position_summary
            pos_summary = get_position_summary()
            pos_count = pos_summary["count"]
            notional = pos_summary["notional"]
            unrealized_pnl = pos_summary["unrealized_pnl"]
        except Exception:
            pos_count = 0
            notional = 0.0
            unrealized_pnl = 0.0
        pnl_color = "green" if unrealized_pnl >= 0 else "red"
        st.markdown(f"**{pos_count}** Açık | **${notional:.0f}** Notional")
        st.markdown(f"PnL: :{pnl_color}[${unrealized_pnl:.2f}]")
    
    # B3) Son Alarm (from real telemetry)
    with card_cols[2]:
        st.markdown("##### 🔔 Son Alarm")
        last_block = lock_states.get("last_block_reason")
        if last_block:
            st.error(f"BLOCK: {last_block[:40]}")
            if st.button("📦 Son Paketi İncele", key="kokpit_inspect_bundle"):
                pass  # Will show in expander
        else:
            st.info("Alarm yok")
    
    st.divider()
    
    # === C) İŞLEM TEKRARI (Trade Replay) - Main Content ===
    st.subheader("🎬 İşlem Tekrarı", help=preset_help_text("islem_tekrari"))
    
    # Symbol/TF filters
    filter_cols = st.columns([1, 1, 4])
    with filter_cols[0]:
        st.selectbox("Sembol", ["TÜMÜ"] + preset.allowlist, key="kokpit_tr_symbol")
    with filter_cols[1]:
        st.selectbox("TF", ["TÜMÜ"] + preset.timeframes, key="kokpit_tr_tf")
    with filter_cols[2]:
        # Overlay toggles row
        tog_cols = st.columns(4)
        with tog_cols[0]:
            st.checkbox("📡 Sinyaller", value=True, key="kokpit_tr_signals")
        with tog_cols[1]:
            st.checkbox("📍 Poz. Çizgileri", value=True, key="kokpit_tr_positions")
        with tog_cols[2]:
            st.checkbox("⚡ Rally", value=True, key="kokpit_tr_rally")
        with tog_cols[3]:
            st.checkbox("🟨 Rally Bölgeleri", value=True, key="kokpit_tr_zones")
    
    # Trade Replay Chart (reuse existing logic from _render_live_section_v2)
    # Delegate to existing Trade Replay implementation
    try:
        rows = build_profile_board()
    except Exception:
        rows = []
    
    # Render Trade Replay content (simplified - calls existing implementation)
    _render_trade_replay_content(ndjson_path, preset)
    
    # Neden & Timeline - default closed
    with st.expander("🔍 Neden & Timeline", expanded=False):
        st.info("Trade seçildiğinde karar bağlamı ve olay zaman çizelgesi burada görünür.")
    
    st.divider()
    
    # === D) EXPANDERS (Default Closed) ===
    
    # D1) Olay Gezgini
    with st.expander("📊 Olay Gezgini", expanded=False):
        st.caption(preset_help_text("olay_gezgini"))
        if ndjson_path.exists():
            events = load_ndjson_tail(ndjson_path, max_lines=100)
            if events:
                import pandas as pd
                rows_data = [{
                    "ts": str(e.get("ts", ""))[:19],
                    "type": e.get("event_type", ""),
                    "symbol": e.get("symbol", ""),
                } for e in events[-20:]]
                st.dataframe(pd.DataFrame(rows_data), use_container_width=True, hide_index=True)
            else:
                st.info("Olay bulunamadı.")
        else:
            st.info("NDJSON dosyası yok. Döngü başlatıldığında olaylar burada görünür.")
    
    # D2) Paketler
    with st.expander("📦 Paketler (Bundles)", expanded=False):
        st.caption(preset_help_text("paketler"))
        from tezaver.ui.matrix_operator_data import list_incident_bundles
        incident_dir = Path("data/incidents")
        bundles = list_incident_bundles(incident_dir)
        if bundles:
            for b in bundles[:5]:
                if not b.error:
                    st.markdown(f"**{Path(b.path).name}** — {b.reason[:40]}")
        else:
            st.info("Paket bulunamadı.")
    
    # D3) Çözümlenmiş Ayarlar
    with st.expander("⚙️ Çözümlenmiş Ayarlar", expanded=False):
        st.caption(preset_help_text("cozumlenmis_ayarlar"))
        
        # Resolved preset
        resolved = resolve_preset(selected_preset, {"safety_level": safety})
        st.json(resolved)
        
        # Diagnostics (small)
        st.markdown("---")
        st.markdown("**Tanı Bilgisi:**")
        st.caption(f"events_path: {ndjson_path}")
        if ndjson_path.exists():
            events = load_ndjson_tail(ndjson_path, max_lines=1)
            if events:
                last_ts = events[-1].get("ts", "N/A")[:19]
                st.caption(f"son olay: {last_ts}")


def _render_trade_replay_content(ndjson_path, preset) -> None:
    """Render Trade Replay with full chart (candlestick/fallback + overlays)."""
    import pandas as pd
    import plotly.graph_objects as go
    from tezaver.ui.trade_replay_data import (
        parse_trades_from_events, build_trade_timeline,
        load_ohlcv, get_trade_context, filter_trades,
        extract_strategy_signals, resolve_price_for_signal,
        extract_rally_events, parse_open_trades_from_events,
        build_fallback_candles_from_events, OverlayPoint,
    )
    from tezaver.ui.matrix_operator_data import load_ndjson_tail
    
    if not ndjson_path.exists():
        st.info("📭 Olay yok. Döngü başlatın veya bring-up aracını çalıştırın:")
        st.code("python -m tezaver.tools.bringup", language="bash")
        return
    
    events = load_ndjson_tail(ndjson_path, max_lines=2000)
    if not events:
        st.info("📭 Olay bulunamadı.")
        return
    
    # Parse trades
    all_trades = parse_trades_from_events(events)
    if not all_trades:
        open_trades = parse_open_trades_from_events(events)
        if open_trades:
            st.info(f"ℹ️ Tamamlanmış işlem yok, {len(open_trades)} açık pozisyon gösteriliyor.")
            all_trades = open_trades
        else:
            st.info("📭 İşlem bulunamadı.")
            return
    
    # Get toggle states from session
    show_signals = st.session_state.get("kokpit_tr_signals", True)
    show_positions = st.session_state.get("kokpit_tr_positions", True)
    show_rally = st.session_state.get("kokpit_tr_rally", True)
    show_zones = st.session_state.get("kokpit_tr_zones", True)
    
    # Get filter states
    selected_symbol = st.session_state.get("kokpit_tr_symbol", "TÜMÜ")
    selected_tf = st.session_state.get("kokpit_tr_tf", "TÜMÜ")
    
    # Apply filters
    filtered_trades = filter_trades(
        all_trades,
        symbol=None if selected_symbol == "TÜMÜ" else selected_symbol,
        timeframe=None if selected_tf == "TÜMÜ" else selected_tf,
        limit=20
    )
    
    if not filtered_trades:
        st.info("Filtreye uyan işlem yok.")
        return
    
    # Show trade count
    st.caption(f"Toplam: {len(all_trades)} işlem | Filtrelenmiş: {len(filtered_trades)}")
    
    # Select first trade for chart
    selected_trade = filtered_trades[0]
    
    # Trade selector (compact)
    if len(filtered_trades) > 1:
        trade_options = [f"{t.symbol}/{t.timeframe} @ {t.open_ts[:16] if t.open_ts else '?'}" for t in filtered_trades[:10]]
        selected_idx = st.selectbox("İşlem Seç", range(len(trade_options)), format_func=lambda i: trade_options[i], key="kokpit_trade_select")
        selected_trade = filtered_trades[selected_idx]
    
    # === CHART ===
    if selected_trade.open_ts:
        chart_end_ts = selected_trade.close_ts
        if not chart_end_ts:
            # Use last event time
            last_evt = events[-1] if events else {}
            chart_end_ts = last_evt.get("ts") or last_evt.get("bar_close_ts") or selected_trade.open_ts
        
        # Try to load OHLCV
        candles, paths_tried = load_ohlcv(
            selected_trade.symbol,
            selected_trade.timeframe,
            selected_trade.open_ts,
            chart_end_ts,
        )
        
        fallback_mode = False
        if not candles:
            # Fallback from events
            candles = build_fallback_candles_from_events(events, selected_trade.open_ts, chart_end_ts)
            if candles:
                fallback_mode = True
        
        if candles and len(candles) >= 2:
            # Build chart
            if fallback_mode:
                # Line chart for fallback
                st.caption("⚠️ OHLCV bulunamadı, fallback gösteriliyor.")
                fig = go.Figure(data=[go.Scatter(
                    x=[c["ts"] for c in candles],
                    y=[c["close"] for c in candles],
                    mode="lines+markers",
                    line=dict(color="blue", width=1),
                    marker=dict(size=4),
                    name="Fiyat"
                )])
            else:
                # Candlestick chart
                fig = go.Figure(data=[go.Candlestick(
                    x=[c["ts"] for c in candles],
                    open=[c["open"] for c in candles],
                    high=[c["high"] for c in candles],
                    low=[c["low"] for c in candles],
                    close=[c["close"] for c in candles],
                    name="Fiyat"
                )])
            
            # Entry marker
            if selected_trade.open_px:
                fig.add_trace(go.Scatter(
                    x=[selected_trade.open_ts],
                    y=[selected_trade.open_px],
                    mode="markers",
                    marker=dict(size=12, color="green", symbol="triangle-up"),
                    name="Giriş"
                ))
            
            # Exit marker
            if selected_trade.close_px and selected_trade.close_ts:
                fig.add_trace(go.Scatter(
                    x=[selected_trade.close_ts],
                    y=[selected_trade.close_px],
                    mode="markers",
                    marker=dict(size=12, color="red", symbol="triangle-down"),
                    name="Çıkış"
                ))
            
            # SL/TP lines
            x_range = [candles[0]["ts"], candles[-1]["ts"]]
            if selected_trade.sl_px and show_positions:
                fig.add_trace(go.Scatter(
                    x=x_range,
                    y=[selected_trade.sl_px, selected_trade.sl_px],
                    mode="lines",
                    line=dict(color="red", dash="dash", width=1),
                    name=f"SL @ {selected_trade.sl_px:.2f}"
                ))
            if selected_trade.tp_px and show_positions:
                fig.add_trace(go.Scatter(
                    x=x_range,
                    y=[selected_trade.tp_px, selected_trade.tp_px],
                    mode="lines",
                    line=dict(color="green", dash="dash", width=1),
                    name=f"TP @ {selected_trade.tp_px:.2f}"
                ))
            
            # Strategy signals overlay
            if show_signals:
                overlay_points = extract_strategy_signals(
                    events,
                    selected_trade.open_ts,
                    selected_trade.close_ts or chart_end_ts,
                    symbol=selected_trade.symbol,
                    timeframe=selected_trade.timeframe,
                )
                for pt in overlay_points:
                    y_val = resolve_price_for_signal(pt, candles)
                    if y_val > 0:
                        fig.add_trace(go.Scatter(
                            x=[pt.ts],
                            y=[y_val],
                            mode="markers",
                            marker=dict(size=8, color=pt.color, symbol=pt.symbol_shape),
                            name=pt.signal,
                            hovertext=f"{pt.signal}: {pt.reason or ''}",
                            hoverinfo="text",
                            showlegend=False,
                        ))
            
            # Rally overlay
            if show_rally:
                rallies = extract_rally_events(
                    events,
                    selected_trade.open_ts,
                    selected_trade.close_ts or chart_end_ts,
                    symbol=selected_trade.symbol,
                    timeframe=selected_trade.timeframe,
                )
                for r in rallies:
                    dummy_pt = OverlayPoint(ts=r.ts, price=None, marker_type="rally", signal="RALLY", reason=None, passed_filters=None)
                    y_val = resolve_price_for_signal(dummy_pt, candles)
                    if y_val > 0:
                        fig.add_trace(go.Scatter(
                            x=[r.ts],
                            y=[y_val],
                            mode="markers+text",
                            text=[f"⚡ {r.gain_pct:.1%}"],
                            textposition="top center",
                            marker=dict(size=14, color="orange", symbol="star"),
                            name="Rally",
                            hovertext=f"Rally: {r.gain_pct:.2%}, {r.bars_to_peak} bar",
                            hoverinfo="text",
                            showlegend=False,
                        ))
                        
                        # Rally zone
                        if show_zones and r.end_ts:
                            fig.add_shape(
                                type="rect",
                                x0=r.ts, x1=r.end_ts,
                                y0=0, y1=1,
                                xref="x", yref="paper",
                                fillcolor="orange",
                                opacity=0.1,
                                layer="below",
                                line_width=0,
                            )
            
            fig.update_layout(
                title=f"{selected_trade.symbol} / {selected_trade.timeframe} - İşlem Tekrarı",
                xaxis_title="Zaman",
                yaxis_title="Fiyat",
                height=450,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # Not enough data
            paths_short = [str(p)[-50:] for p in paths_tried[:2]] if paths_tried else []
            st.warning(f"⚠️ Grafik için yeterli veri yok. Denenen: {', '.join(paths_short) or 'N/A'}")
    
    # Trade table (secondary, compact)
    with st.expander("📋 İşlem Listesi", expanded=False):
        trade_rows = [{
            "Sembol": t.symbol,
            "TF": t.timeframe,
            "Açılış": t.open_ts[:16] if t.open_ts else "-",
            "Kapanış": t.close_ts[:16] if t.close_ts else "-",
            "PnL": f"${t.net_pnl:.2f}" if t.net_pnl else "-",
        } for t in filtered_trades[:10]]
        st.dataframe(pd.DataFrame(trade_rows), use_container_width=True, hide_index=True)



