"""
Tezaver Bulut - Command Center Pro
Professional operator controls for system management.
"""
import streamlit as st
from tezaver.bulut.ui.contracts.panel_guard import guarded_render
from tezaver.bulut.ui.contracts.backend_guard import backend_status, render_backend_offline_banner
from tezaver.bulut.ui.contracts.result_card import call_api, render_result_card

def render_page(ctx=None):
    """Entrypoint for Registry."""
    guarded_render("Komuta Merkezi", lambda: _render_content(ctx))

def _render_content(ctx=None):
    """Main Content."""
    api_base = "http://localhost:8000"
    if ctx and hasattr(ctx, 'config') and hasattr(ctx.config, 'bulut_api_base_url'):
        api_base = ctx.config.bulut_api_base_url
        
    ok_be, info, err_be = backend_status(api_base)
    if not ok_be:
        render_backend_offline_banner(api_base, err_be)
        return

    st.title("🎛️ Command Center Pro")
    st.caption("Advanced System Control & Safety Interventions")

    # Layout: 3 Columns for main areas
    t1, t2, t3 = st.tabs(["⚡ Core Controls", "🛡️ Safety & Recovery", "🚀 Mainnet Ops"])
    
    # --- CORE CONTROLS ---
    with t1:
        st.subheader("System Daemon")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            if st.button("▶️ Start Daemon", key="cmd_start", use_container_width=True):
                res = call_api(ctx, "POST", "/ops/daemon/start", ops_required=True)
                st.session_state['last_cmd_res'] = ("Start Daemon", res)
                
        with c2:
            if st.button("⏹️ Stop Daemon", key="cmd_stop", use_container_width=True):
                 res = call_api(ctx, "POST", "/ops/daemon/stop", ops_required=True)
                 st.session_state['last_cmd_res'] = ("Stop Daemon", res)
                 
        with c3:
            # GET is free
            if st.button("ℹ️ Status", key="cmd_status", use_container_width=True):
                 res = call_api(ctx, "GET", "/ops/daemon/status")
                 st.session_state['last_cmd_res'] = ("Daemon Status", res)
                 
        st.markdown("---")
        st.subheader("Scanner & Incident")
        c4, c5 = st.columns(2)
        with c4:
             if st.button("📡 Trigger Scan", key="cmd_scan", use_container_width=True):
                 res = call_api(ctx, "POST", "/ops/scan/trigger", ops_required=True)
                 st.session_state['last_cmd_res'] = ("Trigger Scan", res)
                 
        with c5:
             if st.button("📦 Export Incident", key="cmd_inc", use_container_width=True):
                 res = call_api(ctx, "POST", "/ops/incident/export", json_data={"reason":"Command Center"}, ops_required=True)
                 st.session_state['last_cmd_res'] = ("Export Incident", res)

    # --- SAFETY ---
    with t2:
        st.error("⚠️ DANGER ZONE: Emergency Controls")
        
        col_kill, col_rec = st.columns(2)
        
        with col_kill:
            st.markdown("**Kill Switch (Acil Durdurma)**")
            if st.button("🛑 HALT TRADING", type="primary", use_container_width=True):
                 res = call_api(ctx, "POST", "/ops/kill_switch/halt", ops_required=True)
                 st.session_state['last_cmd_res'] = ("HALT TRADING", res)
                 
            if st.button("🛡️ SAFE MODE (Reduce Only)", use_container_width=True):
                 res = call_api(ctx, "POST", "/ops/kill_switch/safe", ops_required=True)
                 st.session_state['last_cmd_res'] = ("SAFE MODE", res)
                 
            if st.button("🧘 RESUME NORMAL", use_container_width=True):
                 res = call_api(ctx, "POST", "/ops/kill_switch/resume", ops_required=True)
                 st.session_state['last_cmd_res'] = ("RESUME", res)
                 
        with col_rec:
            st.markdown("**Recovery (Yeniden Başlatma)**")
            if st.button("🚑 Run Recovery Analysis", use_container_width=True):
                 res = call_api(ctx, "POST", "/ops/recovery/run", ops_required=True)
                 st.session_state['last_cmd_res'] = ("Recovery Run", res)
            
            # GET is free
            if st.button("ℹ️ Recovery Status", use_container_width=True):
                 res = call_api(ctx, "GET", "/ops/recovery/status")
                 st.session_state['last_cmd_res'] = ("Recovery Status", res)

    # --- MAINNET OPS ---
    with t3:
        st.subheader("Autopilot & Expansion")
        
        c_auto, c_pilot = st.columns(2)
        
        with c_auto:
             st.markdown("**Autopilot**")
             if st.button("🟢 Enable Autopilot", use_container_width=True):
                  res = call_api(ctx, "POST", "/ops/autopilot/enable", ops_required=True)
                  st.session_state['last_cmd_res'] = ("Enable Autopilot", res)
                  
             if st.button("🔴 Disable Autopilot", use_container_width=True):
                  res = call_api(ctx, "POST", "/ops/autopilot/disable", ops_required=True)
                  st.session_state['last_cmd_res'] = ("Disable Autopilot", res)
                  
        with c_pilot:
             st.markdown("**Expansion Policy**")
             if st.button("🔼 Step Up Tier", use_container_width=True):
                  res = call_api(ctx, "POST", "/ops/expansion/step_up", ops_required=True)
                  st.session_state['last_cmd_res'] = ("Step Up Tier", res)
             
             tier_in = st.number_input("Set Tier", min_value=0, max_value=5, step=1)
             if st.button("Set Tier", use_container_width=True):
                  res = call_api(ctx, "POST", "/ops/expansion/set_tier", json_data={"tier": tier_in}, ops_required=True)
                  st.session_state['last_cmd_res'] = ("Set Tier", res)

    st.markdown("---")
    
    # Result Viewer (Persistent)
    if 'last_cmd_res' in st.session_state:
        title, res = st.session_state['last_cmd_res']
        st.subheader("📡 Son İşlem Sonucu")
        render_result_card(title, res)
