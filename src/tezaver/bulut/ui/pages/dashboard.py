# Tezaver Bulut - Streamlit Dashboard
"""
Dashboard page for Bulut UI.
"""

import streamlit as st
from datetime import datetime, timezone
import time

from tezaver.bulut.core.context import get_context, BulutContext


def render_dashboard(ctx: BulutContext):
    """Render main dashboard."""
    st.title("Tezaver Bulut - Dashboard")
    
    # v0.24 Top Banner
    mode = ctx.config.mode
    armed = ctx.execution_service.is_armed()
    
    # v0.28 Status
    c_guard = ctx.constitution_guard.get_current()
    c_ver = c_guard.get('version', '?')
    c_hash = c_guard.get('sha256_short', '?')
    
    b_col1, b_col2, b_col3 = st.columns([1, 1, 2])
    
    if mode == "REAL_MAINNET":
        b_col1.error(f"🚨 MODE: {mode}")
    elif mode == "PAPER":
        b_col1.warning(f"📝 MODE: {mode}")
    else:
        b_col1.info(f"🧪 MODE: {mode}")

    if armed:
         b_col2.error("🔫 ARMED: YES")
    else:
         b_col2.success("🛡️ ARMED: NO")
         
    b_col3.caption(f"📜 {c_ver} ({c_hash})")

    st.divider()
    # v0.24 Launch Checklist Panel
    with st.expander("🚀 Launch Checklist", expanded=(mode=="REAL_MAINNET")):
        c_col1, c_col2 = st.columns([3, 1])
        if c_col2.button("Run Checklist"):
            ctx.launch_checklist.run_checks(ctx)
            st.rerun()
            
        last = ctx.launch_checklist.get_last_result()
        if last:
            if last.get("pass"):
                st.success(f"PASS (Last run: {int(time.time() - last.get('ts', 0))}s ago)")
            else:
                st.error(f"FAIL (Last run: {int(time.time() - last.get('ts', 0))}s ago)")
            
            checks = last.get("checks", [])
            # Table
            c_data = [{"Check": c["name"], "Pass": "✅" if c["pass"] else "❌", "Detail": c["detail"]} for c in checks]
            st.table(c_data)
        else:
            st.info("Checklist not run yet.")


    # v0.25 Config Drift
    with st.expander("🧬 Config Drift"):
        if hasattr(ctx, "persistence"):
            latest = ctx.persistence.get_latest_config_snapshot()
            if latest:
                l_hash = latest["hash"]
                l_ts = latest["ts"]
                l_source = latest["source"]
                
                # Check current vs latest
                curr_snap = ctx.config.to_dict() # raw
                # We need snapshot service to hash properly
                # If we don't have it exposed in ctx, we can't easily check?
                # We added it to context.
                if hasattr(ctx, "config_snapshot"):
                     c_snap = ctx.config_snapshot.snapshot_config(ctx)
                     c_hash = ctx.config_snapshot.hash_config(c_snap)
                     
                     drift = (c_hash != l_hash)
                     
                     d_col1, d_col2 = st.columns(2)
                     d_col1.metric("Current Hash", c_hash[:8], delta="Drift" if drift else "Synced", delta_color="inverse")
                     d_col2.metric("Saved Hash", l_hash[:8])
                     
                     st.caption(f"Last Saved: {l_ts} (Source: {l_source})")
                     
                     if drift:
                         st.error("Configuration has drifted from saved snapshot!")
                     
                     if st.button("📸 Save Snapshot (Golden)"):
                         ctx.drift_guard.check_and_record(source="MANUAL")
                         st.success("Snapshot saved.")
                         st.rerun()
                else:
                    st.warning("Config Snapshot service missing.")
            else:
                st.info("No config snapshot found.")
                if st.button("📸 Take Initial Snapshot"):
                     ctx.drift_guard.check_and_record(source="MANUAL")
                     st.rerun()

                if st.button("📸 Take Initial Snapshot"):
                     ctx.drift_guard.check_and_record(source="MANUAL")
                     st.rerun()

    # v0.26 Migrations
    with st.expander("🧱 Migrations"):
        if hasattr(ctx, "migration_runner"):
             # Check status via dry run
             report = ctx.migration_runner.run_pending(dry_run=True)
             c_ver = report["current_version"]
             t_ver = report["target_version"]
             pending = report.get("plan", [])
             
             m_col1, m_col2 = st.columns(2)
             m_col1.metric("Schema Version", f"v{c_ver}", delta=f"{len(pending)} Pending" if pending else "Up to date")
             m_col2.metric("Target Version", f"v{t_ver}")
             
             if pending:
                 st.warning(f"Pending Migrations: {len(pending)}")
                 for p in pending:
                     st.text(f"v{p['version']}: {p['description']}")
                 
                 if st.button("Run Migrations"):
                     res = ctx.migration_runner.run_pending(dry_run=False)
                     st.success(f"Executed: {res['executed']}")
                     st.rerun()
             else:
                 st.success("All migrations applied.")
        else:
             st.info("Migration runner not available.")

    # Status Overview
    st.subheader("System Status")
    
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
        today_net = risk_status.get("today_trade_net_pnl", risk_status.get("today_net_pnl", 0.0))
        today_income = risk_status.get("today_income", 0.0)
        today_total = risk_status.get("today_total_pnl", today_net)
        limit = risk_status["daily_loss_limit"]
        
        st.metric("Total Daily PnL", f"${today_total:.2f}", f"Trade: ${today_net:.2f}")
        st.caption(f"Income: ${today_income:.2f} | Limit: ${limit:.2f}")
        
    with risk_cols[2]:
        op = risk_status["open_positions"]
        mx = risk_status["max_positions"]
        st.metric("Global Cap", f"{op} / {mx}")

    # =========================================================================
    # Income Details (v0.18)
    # =========================================================================
    if "today_income_breakdown" in risk_status and risk_status["today_income_breakdown"]:
        with st.expander("💰 Income Breakdown (Today)", expanded=False):
            st.json(risk_status["today_income_breakdown"])

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
    # Env Doctor (v0.20)
    # =========================================================================
    st.subheader("🧪 Env Doctor")
    
    # We can fetch report from API or context if local
    # If using API: requests.get 
    # But dashboard "render_dashboard" is sync. "requests" is sync. Good.
    # But we can also use ctx.env_doctor.run_checks(ctx). Dashboard allows direct ctx usage.
    # Let's use direct ctx for speed/simplicity, matching rest of dashboard.
    
    if "env_report" not in st.session_state:
        # Run on first load or button click only? Expensive?
        # Maybe lightweight checks are fast. Doctor checks file rights and imports. Should be <100ms.
        # Let's run only if explicitly requested or on startup?
        # Better: Show "Last Run" and button "Run Diagnostics".
        st.session_state["env_report"] = None

    c1, c2 = st.columns([3, 1])
    with c1:
        if st.session_state["env_report"]:
             rep = st.session_state["env_report"]
             status = rep.get("status", "UNKNOWN")
             color = "green" if status == "OK" else ("orange" if status == "WARN" else "red")
             st.markdown(f"Status: :{color}[{status}]")
             
             if rep.get("errors"):
                 st.error(f"Errors: {len(rep['errors'])}")
                 for e in rep["errors"]:
                     st.markdown(f"- {e}")
             if rep.get("warnings"):
                 st.warning(f"Warnings: {len(rep['warnings'])}")
                 for w in rep["warnings"]:
                     st.markdown(f"- {w}")

             with st.expander("Detailed Report"):
                 st.json(rep)
        else:
            st.info("Run diagnostics to check environment health.")
            
    with c2:
        if st.button("Run Diagnostics"):
            with st.spinner("Checking system..."):
                 st.session_state["env_report"] = ctx.env_doctor.run_checks(ctx)
            st.rerun()



    st.divider()

    # =========================================================================
    # User Data Stream (v0.21)
    # =========================================================================
    st.subheader("📡 User Data Stream")
    uds = ctx.user_data_stream
    
    ucs1, ucs2, ucs3 = st.columns(3)
    
    conn_status = "Connected" if uds.connected else "Disconnected"
    conn_color = "green" if uds.connected else "red"
    ucs1.metric("WS Status", conn_status)
    
    age = int(time.time() - uds.listen_key_created_at) if uds.listen_key_created_at else 0
    ucs2.metric("ListenKey Age", f"{age // 60}m {age % 60}s")
    
    last_evt = int(time.time() - uds.last_event_ts) if uds.last_event_ts else "Never"
    ucs3.metric("Last Event", f"{last_evt}s ago" if isinstance(last_evt, int) else last_evt)
    
    if uds._listen_key:
        st.caption(f"Key: `{uds._listen_key[:8]}...`")
    else:
        st.caption("No ListenKey")



    # =========================================================================
    # State Reducer (v0.22)
    # =========================================================================
    st.subheader("🧩 State Reducer")
    reducer_stats = ctx.state_reducer.get_stats()
    
    r1, r2, r3 = st.columns(3)
    r1.metric("Duplicates", reducer_stats.get("duplicates", 0))
    r2.metric("OOO Ignored", reducer_stats.get("ooo_ignored", 0))
    
    last_r_event = reducer_stats.get("last_event_ts_ago", 0)
    ago_r = int(time.time()*1000 - last_r_event)/1000.0 if last_r_event > 0 else "Never"
    r3.metric("Last Event", f"{ago_r:.1f}s ago" if isinstance(ago_r, float) else ago_r)
    

    
    st.divider()

    # =========================================================================
    # Heartbeats (v0.23)
    # =========================================================================
    st.subheader("💓 Heartbeats")
    if hasattr(ctx, "persistence"):
        hbs = ctx.persistence.get_heartbeats() # dict
        if hbs:
            # Table
            h_data = []
            for name, h in hbs.items():
                last_ms = h.get("last_ms", 0)
                age = (time.time()*1000 - last_ms)/1000.0 if last_ms > 0 else -1
                status = h.get("status", "UNK")
                h_data.append({
                    "Task": name,
                    "Status": status,
                    "Age (s)": f"{age:.1f}" if age >= 0 else "N/A",
                    "Detail": h.get("detail", "")
                })
            st.table(h_data)
        else:
            st.info("No heartbeats recorded.")
    
    st.divider()

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
    # FX Conversion (v0.19)
    # =========================================================================
    with st.expander("💱 FX Conversion Rates"):
        # Fetch rates
        fx_rates = ctx.persistence.get_all_fx_rates()
        if fx_rates:
            st.dataframe(fx_rates, use_container_width=True)
        else:
            st.info("No FX rates cached yet.")
            
        c1, c2 = st.columns(2)
        with c1:
             if st.button("Refresh FX Rates"):
                 with st.spinner("Fetching..."):
                     try:
                         # Use API (cleaner) or ctx (direct)
                         # ctx direct is async. Dashboard is sync wrapper.
                         # Need asyncio run.
                         import asyncio
                         # Just refresh a default list or all known assets?
                         # Dashboard doesn't know assets easily unless we query positions/income.
                         # Let's pass a few majors for demo or allow input?
                         assets_to_refresh = ["BNB", "BTC", "ETH"] # Default common non-usdt
                         
                         # We can iterate ctx.fx_rate_cache.refresh_asset
                         async def _refresh():
                             for a in assets_to_refresh:
                                 await ctx.fx_rate_cache.refresh_asset(a)
                         
                         asyncio.run(_refresh())
                         st.success("Refreshed (BNB, BTC, ETH)")
                         st.rerun()
                     except Exception as e:
                         st.error(f"Error: {e}")
                         
        with c2:
             if st.button("Recompute Today's Conversions"):
                 with st.spinner("Recomputing..."):
                     try:
                         import asyncio
                         # Call recompute service
                         async def _recompute():
                             return await ctx.fx_recompute.recompute_today_utc()
                             
                         stats = asyncio.run(_recompute())
                         st.success(f"Recomputed! Fixed: Income={stats['income_fixed']}, Audit={stats['audit_fixed']}")
                         if stats['missing_rates']:
                             st.warning(f"Missing rates for: {stats['missing_rates']}")
                     except Exception as e:
                         st.error(f"Error: {e}")

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
