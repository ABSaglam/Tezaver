import streamlit as st
from tezaver.bulut.ui.http_client import call_api
from tezaver.bulut.ui.components.ops_token_box import render_ops_token_box
from tezaver.bulut.core.config import get_config
from tezaver.bulut.ui.contracts.panel_guard import guarded_render
from tezaver.bulut.ui.contracts.backend_guard import backend_status, render_backend_offline_banner

def render_page(ctx=None):
    """Entrypoint for Registry."""
    guarded_render("Komuta Merkezi", _render_content)

def _render_content():
    """Actual content logic."""
    cfg = get_config()
    
    # Backend Guard
    api_base = getattr(cfg, "bulut_api_base_url", "http://localhost:8000")
    ok_be, info, err_be = backend_status(api_base)
    if not ok_be:
        render_backend_offline_banner(api_base, err_be)
        return

    if cfg.deploy_env == "PROD" and not st.session_state.get("ops_token"):
         st.error("⚠️ PRODUCTION MODE: OPS TOKEN MISSING! MUTATIONS LOCKED.")

    st.header("🎮 Command Center")
    
    # Auth Box in Sidebar
    with st.sidebar:
        st.divider()
        render_ops_token_box()

    # 0. Perf & Cost (Short Panel)
    st.subheader("Perf & Cost (Current)")
    ok_perf, perf_status = call_api("GET", "/perf/status")
    if ok_perf:
         # Layout: Mode | Budget | Cycle | Overrides
         p1, p2, p3, p4 = st.columns(4)
         p1.metric("Mode", perf_status.get("mode", "UNKNOWN"))
         p2.metric("Budget", f"{perf_status.get('budget_usage_pct', 0):.0f}%")
         p3.metric("Cycle", f"{perf_status.get('cycle_ms', 0)}ms")
         
         recs = len(perf_status.get("recommended_overrides", []))
         p4.metric("Recs", recs)
         
         if st.button("Open Perf Page", key="btn_open_perf"):
              st.session_state['cloud_nav'] = "Perf & Cost" # Matches registry title or we handle via ID switching if simpler
              st.rerun()
    else:
         st.warning("Perf Status Unavailable")

    st.divider()

    # 1. Operational Commands
    st.subheader("Operations")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🚀 Run Checklist", use_container_width=True):
            ok, res = call_api("POST", "/launch/checklist/run")
            if ok: st.success("Checklist Run")
            else: st.error(f"Checklist Failed: {res}")
            
    with col2:
         if st.button("🛑 Stop Daemon (Disarm)", use_container_width=True):
             ok, res = call_api("POST", "/execution/disarm") # Assumes route exists
             if ok: st.success("Daemon/Execution Stopped")
             else: st.error(f"Stop Failed: {res}")

    with col3:
        if st.button("🔎 Scan Now", use_container_width=True):
             st.info("Triggering scan...")
             call_api("POST", "/ui/scan_now_placeholder") # Placeholder

    st.divider()

    # 1.5 Proof Ladder (v1)
    st.subheader("🪜 Proof Ladder")
    
    # Fetch Status
    ok_pl, pl_data = call_api("GET", "/mainnet/ladder/status")
    if ok_pl:
        # Layout: Current Stage | Cap | Effective Cap | Clean Hours
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Stage", pl_data.get("stage_id", "N/A"))
        c2.metric("Stage Cap", f"${pl_data.get('cap_usdt', 0)}")
        c3.metric("Effective Cap", f"${pl_data.get('effective_cap_usdt', 0)}")
        c4.metric("Clean Hours", f"{pl_data.get('clean_hours', 0):.1f}")
        
        # Details & Check
        if st.expander("Details & Actions", expanded=False):
            st.json(pl_data)
            
            # Actions
            b1, b2 = st.columns(2)
            with b1:
                # Warning if no token
                if not st.session_state.get("ops_token"):
                    st.caption("🔒 Requires Ops Token")
                    
                if st.button("Evaluate Now"):
                    ok_ev, res_ev = call_api("POST", "/mainnet/ladder/evaluate")
                    if ok_ev:
                        if res_ev.get("passed"): st.success("PASSED")
                        else: st.error(f"FAILED: {res_ev.get('reasons')}")
                        st.json(res_ev)
                    else:
                        st.error(f"Error: {res_ev}")
            
            with b2:
                # Advance Button
                next_stage = pl_data.get("next_stage")
                dis = (not next_stage)
                
                # Visual cue for lock
                label = f"Advance to {next_stage or 'Type Max'}"
                if not st.session_state.get("ops_token"):
                    label = f"🔒 {label}"
                    
                if st.button(label, disabled=dis):
                    ok_adv, res_adv = call_api("POST", "/mainnet/ladder/advance")
                    if ok_adv:
                        st.success(res_adv["message"])
                        st.rerun()
                    else:
                        # Error handled by call_api (toast/warning) but we can show details
                        st.error(f"Advance Failed: {res_adv}")
                        
    else:
        st.error(f"Proof Ladder Status Failed: {pl_data}")

    st.divider()

    # 1.6 Strict Timing (P3)
    st.subheader("⏱ Strict Timing")
    
    ok_st, st_status = call_api("GET", "/strict_timing/status")
    if ok_st:
        # KPI Cards
        # last_run: {bar_close_ts, run_ts, ran_at_ms, last_cycle_id}
        last = st_status.get("last_run") or {}
        mode = st_status.get("mode", "UNKNOWN")
        drift_limit = st_status.get("max_drift_ms", 5000)
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Mode", mode)
        
        last_ts = last.get("bar_close_ts", "N/A")
        if last_ts != "N/A":
             # Extract time part
             try: last_ts_disp = last_ts.split("T")[1][:5] # HH:MM
             except: last_ts_disp = last_ts
        else:
             last_ts_disp = "NONE"
             
        k2.metric("Last Close", last_ts_disp)
        
        # We don't have global stats in status endpoint yet (stubbed), but we can query timeline for recent drift
        k3.metric("Limit", f"{drift_limit}ms")
        
        # Table
        with st.expander("Timing History", expanded=False):
            ok_hist, hist = call_api("GET", "/strict_timing/timeline?limit=50")
            if ok_hist and hist:
                # Table: Close TS | Drift | Status
                rows = []
                for h in hist:
                    drift = h.get("drift_ms", 0)
                    status = "OK"
                    if drift > drift_limit: status = "DRIFT_WARN"
                    
                    rows.append({
                        "Close TS": h.get("cycle_ts"),
                        "Drift (ms)": drift,
                        "Status": status,
                        "Deduped": h.get("deduped", False)
                    })
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("No timeline data.")
    else:
        st.error("Strict Timing Service Unreachable")

    st.divider()

    # 1.7 Mainnet Dry-Run (P4)
    st.subheader("🧪 Mainnet Dry-Run")
    
    with st.expander("Control Panel", expanded=False):
        # Config & Start
        dr_col1, dr_col2, dr_col3 = st.columns(3)
        with dr_col1:
            cycles_count = st.number_input("Simulator Cycles (History)", min_value=5, max_value=100, value=20)
        
        with dr_col2:
            if st.button("▶️ Start Dry-Run Simulation", use_container_width=True):
                 ok_start, res_start = call_api("POST", "/dry_run/start", {"cycles": cycles_count})
                 if ok_start: st.success(f"Started: {res_start.get('run_id')}")
                 else: st.error(f"Failed: {res_start}")
                 
        with dr_col3:
             # Refresh Status Button
             if st.button("🔄 Refresh Dry-Run Status"):
                 st.rerun()

        st.divider()
        
        # Status & History
        ok_dr, dr_status = call_api("GET", "/dry_run/status")
        if ok_dr:
            is_running = dr_status.get("running", False)
            st.metric("Running", "YES" if is_running else "NO")
            if is_running:
                 st.info("Simulation in progress... check logs.")
        
        st.caption("Latest Runs")
        ok_runs, runs = call_api("GET", "/dry_run/runs/latest?limit=5")
        if ok_runs and runs:
             dr_rows = []
             for r in runs:
                 s = r.get("summary", {})
                 created = r.get("created_at", "").replace("T", " ")[:16]
                 dr_rows.append({
                     "ID": r.get("run_id"),
                     "Time": created,
                     "Status": r.get("status"),
                     "Cycles": s.get("cycles_processed"),
                     "Opens": s.get("open_positions")
                 })
             st.dataframe(dr_rows, use_container_width=True)
        else:
             st.info("No runs found.")
             
    st.divider()
    
    # 2. Maintenance
    st.subheader("Maintenance")
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        if st.button("⚖️ Reconcile"):
             # POST /reconcile/run
             call_api("POST", "/reconcile/run")
             st.toast("Triggering Reconcile...")
             
    with m2:
        if st.button("💰 Income Sync"):
             # POST /income/sync
             call_api("POST", "/income/sync")
             st.toast("Triggering Income Sync...")

    with m3:
        if st.button("💱 FX Refresh"):
             # POST /fx/refresh
             call_api("POST", "/fx/refresh")
             st.toast("Triggering FX Refresh...")

    with m4:
        if st.button("📥 Export Incident"):
             ok, res = call_api("POST", "/ops/incident/export", {"reason": "manual_ui"})
             if ok:
                 st.success(f"Exported: {res.get('path')}")
             else:
                 st.error(f"Export Failed: {res}")
                 
    st.divider()

    # 3. Forensics Timeline (v1)
    st.subheader("🧾 Cycles Timeline")
    
    # Refresh button
    if st.button("🔄 Refresh Timelines"):
        st.rerun()

    with st.expander("Cycle History (Last 10)", expanded=True):
        ok, data = call_api("GET", "/cycles/timelines?limit=10")
        
        if ok and isinstance(data, list) and len(data) > 0:
             # Header
             h1, h2, h3, h4 = st.columns([1, 3, 3, 2])
             h1.markdown("**#**")
             h2.markdown("**Time**")
             h3.markdown("**Status**")
             h4.markdown("**Data**")
             st.divider()
             
             for t in data:
                 idx = t.get('cycle_index', 'N/A')
                 ts = t.get('cycle_ts', '')
                 # Format TS
                 try:
                     dt = ts.split('.')[0].replace('T', ' ')
                 except: dt = ts
                 
                 stages = t.get('stages', [])
                 
                 # Extract summary
                 sched_stage = next((s for s in stages if s['name'] == 'SCHED'), {})
                 risk_stage = next((s for s in stages if s['name'] == 'RISK'), {})
                 
                 sched_det = sched_stage.get('details', {})
                 missed_n = sched_det.get('missed_n', 0)
                 scanned_n = sched_det.get('scanned_n', 0)
                 halted = risk_stage.get('details', {}).get('halted', False)
                 
                 c1, c2, c3, c4 = st.columns([1, 3, 3, 2])
                 with c1: st.write(f"#{idx}")
                 with c2: st.caption(dt)
                 with c3:
                     if halted:
                         st.error("RISK HALT")
                     elif missed_n > 0:
                         st.warning(f"⚠️ {missed_n} Missed")
                     else:
                         st.success(f"✅ {scanned_n} OK")
                 with c4:
                     # Using unique key for popover based on cycle index
                     with st.popover("JSON", help=f"Cycle {idx} Details"):
                         st.json(t)
                 
                 st.divider()
                 
        elif not ok:
             st.error(f"Failed to load timelines: {data}")
        else:
             st.info("No cycle history found yet.")
             
    # 4. Active Plans Table (v1 Sizing Vis)
    st.subheader("📋 Active Plans")
    
    ok_plans, plans_data = call_api("GET", "/plans/")
    if ok_plans and isinstance(plans_data, list) and len(plans_data) > 0:
        # Show table: Symbol | Decision | Sizing Profile | Notional | Reason
        t_data = []
        for p in plans_data:
            reasons = p.get('reasons', {}) or {}
            sizing_id = reasons.get('sizing_profile_id', p.get('sizing_profile_id', '-'))
            notional = p.get('notional_usdt', 0.0)
            
            t_data.append({
                "Symbol": p.get('symbol'),
                "Decision": p.get('decision'),
                "Profile": sizing_id,
                "Notional": f"{notional:.2f}",
                "Lev": p.get('leverage'),
                "Reason": reasons.get('sizing_explain', '')
            })
        st.dataframe(t_data, use_container_width=True)
    elif not ok_plans:
        st.warning("Could not fetch plans.")
    else:
        st.info("No active plans.")
             
    # 3. Status View (Reuse API summary)
    st.subheader("Backend Status")
    ok, summary = call_api("GET", "/ui/summary")
    if ok:
        st.json(summary)
