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
    # Portfolio Risk (v0.12)
    # =========================================================================
    st.subheader("🛡️ Risk Status")
    
    # Lazy load if needed context access ensures it
    risk_status = ctx.portfolio_risk.get_risk_status()
    
    risk_cols = st.columns(3)
    
    with risk_cols[0]:
        halted = risk_status["entry_halted"]
        status_text = "HALTED ⛔" if halted else "ACTIVE ✅"
        st.metric("Entry Status", status_text)
        if halted:
            st.caption("Daily Loss Limit Hit!")
            
    with risk_cols[1]:
        today_net = risk_status["today_net_pnl"]
        today_gross = risk_status["today_gross_pnl"]
        today_fees = risk_status["today_fees"]
        limit = risk_status["daily_loss_limit"]
        
        st.metric("Net Daily PnL", f"${today_net:.2f}", f"Gross: {today_gross:.2f}")
        st.caption(f"Fees: ${today_fees:.2f} | Limit: ${limit:.2f}")
        
    with risk_cols[2]:
        op = risk_status["open_positions"]
        mx = risk_status["max_positions"]
        st.metric("Global Cap", f"{op} / {mx}")

    # =========================================================================
    # Last Trades (v0.17)
    # =========================================================================
    st.subheader("🏁 Last Trades (Audit)")
    try:
        audits = ctx.persistence.get_latest_audit(10)
        if audits:
            import pandas as pd
            df_audit = pd.DataFrame(audits)
            
            # Format display
            # symbol, net_pnl_usdt, pnl_source, exit_reason, pattern_id
            # Fallback for old records without net_pnl_usdt
            if "net_pnl_usdt" in df_audit.columns:
                df_audit["Net PnL"] = df_audit["net_pnl_usdt"].fillna(df_audit["pnl_usdt"])
            else:
                df_audit["Net PnL"] = df_audit["pnl_usdt"]
            
            # Upgraded Indicator
            def _fmt_source(row):
                src = row.get("pnl_source", "UNKNOWN")
                upg = row.get("audit_upgraded", 0)
                if upg:
                    return f"{src} 🛠️"
                return src
                
            df_audit["Source"] = df_audit.apply(_fmt_source, axis=1)
            
            # Fee Display
            def _fmt_fee(row):
                native = row.get("fee_native", 0)
                asset = row.get("fee_asset", "USDT")
                if native == 0: return "0"
                return f"{native:.4f} {asset}"
                
            df_audit["Fee (Native)"] = df_audit.apply(_fmt_fee, axis=1)
                
            cols_audit = ["close_ts", "symbol", "Net PnL", "Source", "Fee (Native)", "exit_reason", "pattern_id"]
            # Available cols
            cols_audit = [c for c in cols_audit if c in df_audit.columns]
            
            st.dataframe(
                df_audit[cols_audit].style.format({
                    "Net PnL": "{:.2f}"
                }),
                use_container_width=True
            )
        else:
            st.info("No closed trades in audit yet.")
    except Exception as e:
        st.error(f"Audit Error: {e}")
    # =========================================================================
    # Time Sync (v0.13)
    # =========================================================================
    st.subheader("🕒 Time Sync")
    
    # We need to fetch status from API to be accurate about BACKEND status?
    # Context in dashboard is local to dashboard.
    # So using ctx.time_sync checks dashboard's sync.
    # But we want to know if Backend is synced.
    # We should query /health/detailed or /time_sync/status?
    # Let's assume dashboard ctx is okay for display or we use API.
    # User instructions implied direct ctx usage in previous tasks ("ctx.portfolio_risk...").
    # If user context is shared (e.g. monolith mode), then it works.
    # If not, it's misleading.
    # Given "ctx = get_context()" usage in dashboard in previous steps, I'll stick to ctx pattern.
    # But for "Refresh", I will try to call API to ensure backend refreshes.
    
    import asyncio
    import requests
    
    async def refresh_sync():
        try:
             requests.post("http://localhost:8000/time_sync/refresh", timeout=2)
             st.success("Sync signal sent!")
        except Exception as e:
             st.error(f"Sync failed: {e}")
             
    ts_healthy, ts_details = ctx.time_sync.is_healthy()
    offset = ts_details.get("offset_ms", 0)
    
    ts_cols = st.columns(3)
    with ts_cols[0]:
        st.metric("Health", "OK ✅" if ts_healthy else "BAD ⛔")
    with ts_cols[1]:
        st.metric("Skew (ms)", f"{offset} ms")
    with ts_cols[2]:
        if st.button("Refresh Sync"):
             # Simple fire and forget or call
             try:
                 requests.post("http://localhost:8000/time_sync/refresh", timeout=1)
                 st.toast("Refreshed!")
                 # Also refresh local
                 asyncio.run(ctx.time_sync.refresh())
             except:
                 st.error("API Unreachable")
    
    st.divider()
    
    # =========================================================================
    # Open Positions
    # =========================================================================
    st.subheader("📈 Open Positions")
    
    # helper to fetch positions
    try:
        from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
        persistence = ctx.persistence
        positions = persistence.get_open_positions()
    except Exception as e:
        positions = []
        st.error(f"Failed to load positions: {e}")

    if positions:
        import pandas as pd
        pos_df = pd.DataFrame(positions)
        
        # Format / Select Columns
        # Expecting: symbol, entry_price, qty, notional_usdt, sl_pct, tp_pct, status, protective_status
        display_cols = [
            "symbol", "entry_price", "qty", "notional_usdt", 
            "sl_pct", "tp_pct", "protective_status"
        ]
        
        # Check availability
        final_cols = [c for c in display_cols if c in pos_df.columns]
        
        st.dataframe(
            pos_df[final_cols].style.format({
                "entry_price": "{:.4f}",
                "notional_usdt": "{:.2f}",
                "sl_pct": "{:.2f}%",
                "tp_pct": "{:.2f}%",
            }),
            use_container_width=True
        )
    else:
        st.info("No open positions.")

    # =========================================================================
    # Trade Plans (v0.14)
    # =========================================================================
    st.subheader("📜 Recent Plans")
    
    try:
        plans = ctx.persistence.get_latest_plans(10)
    except:
        plans = []
        
    if plans:
        import pandas as pd
        df_plans = pd.DataFrame(plans)
        
        # v0.16: Extract Pattern Info from reasons
        def _fmt_pattern(row):
            reasons = row.get("reasons", {})
            if not isinstance(reasons, dict): return ""
            pid = reasons.get("pattern_id")
            conf = reasons.get("pattern_confidence")
            if pid:
                return f"{pid} ({conf:.2f})" if conf else pid
            return ""
            
        df_plans["Pattern"] = df_plans.apply(_fmt_pattern, axis=1)
        
        # Display Columns
        cols_p = ["plan_ts", "symbol", "decision", "Pattern", "status", "exec_state", "exec_error", "notional"]
        # Filter available
        cols_p = [c for c in cols_p if c in df_plans.columns]
        
        st.dataframe(
            df_plans[cols_p].style.format({
                "notional": "{:.2f}"
            }),
            use_container_width=True
        )
    else:
        st.info("No trade plans logged yet.")

    st.divider()

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
                df = []
                for c in shortlist:
                    # v0.16 Pattern Display
                    pat_str = str(c.components.get("pattern", 0))
                    if getattr(c, "matched_patterns", None):
                        top = c.matched_patterns[0]
                        pat_str += f" ({top['pattern_id']}:{top['confidence']:.2f})"
                        
                    df.append({
                        "Symbol": c.symbol,
                        "Score": c.score,
                        "Pattern": pat_str,
                        "Trend": c.components.get("trend", 0),
                        "Risk": c.components.get("risk", 0),
                        "Flags": ", ".join(c.flags),
                    })
                
                st.dataframe(pd.DataFrame(df), use_container_width=True)
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
    # Exchange Info / Filters
    # =========================================================================
    with st.expander("🛠️ Exchange Info Cache"):
        status = ctx.exchangeinfo_cache.get_status()
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Symbols**: {status.get('symbols_count')}")
            st.write(f"**Age**: {status.get('age_seconds'):.1f}s")
            st.write(f"**Fresh**: {'✅' if status.get('is_fresh') else '⚠️'}")
            
        with col2:
            if st.button("Refresh Filters"):
                with st.spinner("Fetching from Binance..."):
                    import asyncio
                    # Hack for streaming runner? async?
                    # Streamlit handles async by default in 1.2+?
                    # Or we need asyncio.run if sync.
                    # ctx.exchangeinfo_cache.refresh() is async.
                    # streamlit usually runs in a loop.
                    # We can use ctx.exchangeinfo_cache.refresh() direct if `render_dashboard` is async?
                    # It is not.
                    # asyncio.run() might hit loop issues if already loop.
                    # Streamlit runs in a separate thread.
                    try:
                        asyncio.run(ctx.exchangeinfo_cache.refresh())
                        st.success("Refreshed!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

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


    # =========================================================================
    # Exit Profiles
    # =========================================================================
    with st.expander("🚪 Exit Profiles"):
        st.info("Manage dynamic exit rules (SL/TP/Time).")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Reload Profiles"):
                ctx.exit_profile_loader.check_reload()
                st.success("Exit profiles reloaded.")
                st.rerun()
        
        with col2:
            st.write("Bootstrap / Reset")
            force_reset = st.checkbox("Force Reset (Overwrite w/ Backup)", value=False)
            
            if st.button("Run Bootstrap"):
                with st.spinner("Bootstrapping..."):
                    val_res = ctx.exit_profile_loader.ensure_defaults(force=force_reset)
                    
                    # Emit Telemetry from UI
                    telemetry_data = {"ts": datetime.now().isoformat(), "source": "UI", **val_res}
                    ctx.telemetry.emit_exit_profiles_bootstrap(telemetry_data)
                    
                    if val_res.get("ok"):
                        st.success("Bootstrap Successful")
                        # Reload to reflect changes
                        ctx.exit_profile_loader._load_profiles()
                    else:
                        st.error("Bootstrap Failed")
                        
                    st.json(val_res)
        
        # List loaded
        profiles = list(ctx.exit_profile_loader._profiles.values())
        if profiles:
            st.write(f"**Loaded {len(profiles)} profiles:**")
            # Create simple view
            prof_data = []
            for p in profiles:
                # Format scope
                scope_str = "Global"
                if p.scope.symbol:
                    scope_str = f"Sym:{p.scope.symbol}"
                if p.scope.pattern_id:
                    scope_str += f" Pat:{p.scope.pattern_id}"
                
                # Format rules
                rules_str = ", ".join([r.type for r in p.rules])
                
                prof_data.append({
                    "ID": p.profile_id, 
                    "Priority": p.priority, 
                    "Scope": scope_str,
                    "Rules": rules_str
                })
            
            st.dataframe(prof_data, use_container_width=True)
    # =========================================================================
    # Ops Pack (v0.15)
    # =========================================================================
    st.divider()
    st.subheader("🧭 System Status")
    
    # 1. System Status
    try:
        status = ctx.status_service.get_status(ctx)
        
        # Display key metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Daemon", "RUNNING" if status.daemon.running else "STOPPED")
        with c2:
            st.metric("Time Sync", "OK" if status.time_sync.healthy else f"BAD ({status.time_sync.offset_ms}ms)")
        with c3:
            st.metric("Exchange Info", "FRESH" if status.exchangeinfo.fresh else f"STALE ({status.exchangeinfo.age_s:.1f}s)")
        with c4:
            st.metric("Risk Entry", "ACTIVE" if not status.risk.entry_halted else "HALTED")
            
    except Exception as e:
        st.error(f"Status Error: {e}")

    # 2. Alerts
    st.subheader("🚨 Alerts")
    try:
        alerts = ctx.persistence.get_latest_alerts(20)
        if alerts:
             import pandas as pd
             df_alerts = pd.DataFrame(alerts)
             st.dataframe(df_alerts[["ts", "level", "code", "message"]], use_container_width=True)
        else:
             st.info("No active alerts.")
    except Exception as e:
        st.error(f"Alerts Error: {e}")

    # 3. Incident Bundle Export
    with st.expander("📦 Incident Bundle Export"):
        st.info("Export logs, config, and DB snapshot for debugging.")
        reason = st.text_input("Reason", placeholder="e.g. execution_failure_param_error")
        
        if st.button("Export Bundle"):
            if not reason:
                st.error("Please provide a reason.")
            else:
                with st.spinner("Generating Log Bundle..."):
                    try:
                        path = ctx.incident_bundle.create_bundle(ctx, reason)
                        st.success(f"Bundle Exported: `{path}`")
                    except Exception as e:
                        st.error(f"Export Failed: {e}")

if __name__ == "__main__":
    render_dashboard()
