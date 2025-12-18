import streamlit as st
from tezaver.bulut.ui.http_client import call_api
from tezaver.bulut.ui.components.ops_token_box import render_ops_token_box

def render_command_center(api_base: str = "http://localhost:8000"):
    st.header("🎮 Command Center")
    
    # Auth Box in Sidebar
    with st.sidebar:
        st.divider()
        render_ops_token_box()

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
    else:
        st.error("Backend unreachable. Start `uvicorn`?")
