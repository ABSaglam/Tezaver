import streamlit as st
import pandas as pd
import requests
from tezaver.bulut.ui.contracts.panel_guard import guarded_render
from tezaver.bulut.ui.contracts.backend_guard import backend_status, render_backend_offline_banner

def render_page(ctx=None):
    """Entrypoint for Registry."""
    guarded_render("Seyir Defteri", lambda: _render_content(ctx))

def _render_content(ctx=None):
    """Actual content logic."""
    api_base = "http://localhost:8000"
    if ctx and hasattr(ctx, 'config') and hasattr(ctx.config, 'bulut_api_base_url'):
        api_base = ctx.config.bulut_api_base_url
        
    ok_be, info, err_be = backend_status(api_base)
    if not ok_be:
        render_backend_offline_banner(api_base, err_be)
        return

    st.header("📔 Journal")

    def get_audit():
        try:
            resp = requests.get(f"{api_base}/ui/audit/latest", params={"limit": 50})
            return resp.json() if resp.status_code == 200 else []
        except: return []

    st.subheader("Recent Audits")
    audit_data = get_audit()
    if audit_data:
        df = pd.DataFrame(audit_data)
        st.dataframe(df)
    else:
        st.info("No audit logs found.")
        
    st.divider()
    st.subheader("Income Summary")
    # Call /income/today
    try:
        res = requests.get(f"{api_base}/ui/income/today").json()
        st.json(res)
    except:
        st.error("Income fetch failed")
