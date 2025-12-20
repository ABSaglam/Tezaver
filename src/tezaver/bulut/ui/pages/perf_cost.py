# Tezaver Bulut - Perf & Cost UI Page (P13)
"""
Streamlit page for Performance & Cost monitoring and control.
"""
import streamlit as st
import requests
from tezaver.bulut.ui.contracts.panel_guard import guarded_render
from tezaver.bulut.ui.contracts.backend_guard import backend_status, render_backend_offline_banner

# API Base URL (could be centralized in config but using consistent approach with other pages)
API_BASE = "http://localhost:8000" # Local default, should override from ctx

def render_page(ctx=None):
    """Entrypoint for Registry."""
    guarded_render("Perf & Cost", lambda: _render_content(ctx))

def _render_content(ctx=None):
    """
    Render function logic.
    """
    # 1. Backend Guard
    # Use context config if available
    api_base = API_BASE
    if ctx and hasattr(ctx, 'config') and hasattr(ctx.config, 'bulut_api_base_url'):
        api_base = ctx.config.bulut_api_base_url
        
    ok_be, info, err_be = backend_status(api_base)
    if not ok_be:
        render_backend_offline_banner(api_base, err_be)
        return

    st.header("⚡ Perf & Cost Management")
    
    # Check ops token based on st.session_state (standard practice)
    has_token = bool(st.session_state.get("ops_token"))
    if not has_token:
        st.warning("🔒 View Only Mode - Ops Token Required for Actions")

    # 1. Fetch Status
    try:
        res = requests.get(f"{api_base}/perf/status", timeout=5)
        if res.status_code == 200:
            status = res.json()
        else:
            st.error(f"Failed to fetch status: {res.status_code}")
            status = {}
            
        res_overrides = requests.get(f"{api_base}/perf/overrides", timeout=5)
        if res_overrides.status_code == 200:
            overrides = res_overrides.json()
        else:
            overrides = []
            
    except Exception as e:
        # Let guarded_render catch typical crashes, but for internal fetch we might want partial render
        # But for contract mode, let's allow it to bubble if critical?
        # Typically we just show error here.
        st.error(f"API Error: {e}")
        status = {}
        overrides = []

    # 2. Key Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    
    mode = status.get("mode", "UNKNOWN")
    m1.metric("Perf Mode", mode)
    
    budget = status.get("budget_usage_pct", 0)
    m2.metric("Budget Usage", f"{budget:.1f}%")
    
    cycle_ms = status.get("cycle_ms", 0)
    limit_ms = status.get("limit_ms", 15000)
    m3.metric("Cycle Latency", f"{cycle_ms}ms", delta=f"{limit_ms - cycle_ms}ms margin")
    
    rec_count = len(status.get("recommended_overrides", []))
    m4.metric("Recommendations", rec_count)

    st.divider()
    
    # 3. Actions / Controls
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("Evaluate Status")
        if st.button("🔄 Re-Evaluate Now", disabled=not has_token, use_container_width=True):
            r = requests.post(f"{api_base}/perf/evaluate", timeout=5)
            if r.status_code == 200:
                st.success("Evaluation Triggered")
                st.json(r.json())
                st.rerun()
            else:
                st.error(f"Error: {r.text}")

    with c2:
        st.subheader("Force Mode")
        modes = ["ECO", "BALANCED", "PERFORMANCE", "SURVIVAL"]
        cur_idx = modes.index(mode) if mode in modes else 1
        sel_mode = st.selectbox("Select Mode", modes, index=cur_idx, key="perf_mode_sel", disabled=not has_token)
        
        if st.button("⚠️ Force Mode", disabled=not has_token, use_container_width=True):
            r = requests.post(f"{api_base}/perf/force_mode", json={"mode": sel_mode}, timeout=5) 
            if r.status_code == 200:
                st.success(f"Forced to {sel_mode}")
                st.rerun()
            else:
                st.error(f"Error: {r.text}")

    with c3:
        st.subheader("Overrides")
        if st.button("❌ Clear Overrides", disabled=not has_token, use_container_width=True):
             r = requests.post(f"{api_base}/perf/clear_force", timeout=5)
             if r.status_code == 200:
                 st.success("Overrides Cleared")
                 st.rerun()
             else:
                 st.error(f"Error: {r.text}")

    st.divider()

    # 4. Detailed Info
    
    # Recommendations
    st.subheader("🔍 Recommendations")
    recs = status.get("recommended_overrides", [])
    if recs:
        for r in recs:
            st.info(f"👉 {r.get('component')} -> {r.get('action')} ({r.get('reason')})")
    else:
        st.success("No active recommendations (System Healthy)")
        
    # Overrides Table
    st.subheader("⚙️ Active Overrides")
    if overrides:
        st.dataframe(overrides, use_container_width=True)
    else:
        st.caption("No overrides active.")

if __name__ == "__main__":
    st.set_page_config(page_title="Perf & Cost", layout="wide")
    render_page()
