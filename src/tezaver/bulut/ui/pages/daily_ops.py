"""
Tezaver Bulut - Daily Ops Page
Daily reports, health checks, and summary.
"""
import streamlit as st
import pandas as pd
from tezaver.bulut.ui.contracts.panel_guard import guarded_render
from tezaver.bulut.ui.contracts.backend_guard import backend_status, render_backend_offline_banner
from tezaver.bulut.ui.contracts.result_card import call_api, render_result_card

def render_page(ctx=None):
    """Entrypoint for Registry."""
    guarded_render("Günlük Operasyon", lambda: _render_content(ctx))

def _render_content(ctx=None):
    """Actual content logic."""
    api_base = "http://localhost:8000"
    if ctx and hasattr(ctx, 'config') and hasattr(ctx.config, 'bulut_api_base_url'):
        api_base = ctx.config.bulut_api_base_url
        
    ok_be, info, err_be = backend_status(api_base)
    if not ok_be:
        render_backend_offline_banner(api_base, err_be)
        return

    st.title("📅 Daily Ops")
    
    # READ-ONLY SECTION (Always Free)
    st.subheader("📊 Reports (Read Only)")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Bugün (Today)")
        res = call_api(ctx, "GET", "/ops/daily/today") # ops_required=False (implicit for GET)
        if res.ok and res.json_body:
            st.code(str(res.json_body), language="json")
        else:
            st.info("No Data")
            
    with c2:
        st.caption("Dün (Yesterday)")
        res = call_api(ctx, "GET", "/ops/daily/yesterday")
        if res.ok and res.json_body:
            st.code(str(res.json_body), language="json")
        else:
            st.info("No data available")
            
    st.markdown("---")
    
    # ACTIONS SECTION (Ops Token Required)
    st.subheader("⚡ Operator Actions")
    
    has_token = bool(st.session_state.get('ops_token'))
    if not has_token:
        st.warning("🔒 Ops Token Missing - Actions Locked")
    
    t_act, t_health = st.tabs(["Daily Computations", "Health & Alerts"])
    
    with t_act:
        if st.button("🧮 Compute Daily Report Now", use_container_width=True, disabled=not has_token):
             res = call_api(ctx, "POST", "/ops/daily/compute", ops_required=True)
             render_result_card("Compute Result", res)
        elif not has_token:
             st.caption("🔒 Requires Ops Token")
             
    with t_health:
        if st.button("💉 Run Health Checks Now", use_container_width=True, disabled=not has_token):
             res = call_api(ctx, "POST", "/ops/daily/health/run", ops_required=True)
             render_result_card("Health Run", res)
        elif not has_token:
             st.caption("🔒 Requires Ops Token")
             
        st.markdown("---")
        # READ ONLY CHECK LISTS
        st.caption("Recent Checks (Read Only)")
        res_checks = call_api(ctx, "GET", "/ops/daily/health/checks")
        if res_checks.ok and res_checks.json_body:
             data = res_checks.json_body.get('checks', [])
             if data:
                 st.dataframe(pd.DataFrame(data), use_container_width=True)
             else:
                 st.info("No checks recorded.")
                 
        st.caption("Top Alerts (Read Only)")
        res_alerts = call_api(ctx, "GET", "/ops/daily/alerts/top")
        if res_alerts.ok and res_alerts.json_body:
             alerts = res_alerts.json_body.get('alerts', [])
             if alerts:
                 st.dataframe(pd.DataFrame(alerts), use_container_width=True)
