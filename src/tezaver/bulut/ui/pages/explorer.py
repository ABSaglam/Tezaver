import streamlit as st
import pandas as pd
from tezaver.bulut.ui.contracts.panel_guard import guarded_render
from tezaver.bulut.ui.contracts.backend_guard import backend_status, render_backend_offline_banner

def render_page(ctx=None):
    """Entrypoint for Registry."""
    guarded_render("Explorer", lambda: _render_content(ctx))

def _render_content(ctx=None):
    """Actual content logic."""
    # Check backend first
    api_base = "http://localhost:8000"
    if ctx and hasattr(ctx, 'config') and hasattr(ctx.config, 'bulut_api_base_url'):
        api_base = ctx.config.bulut_api_base_url
    
    # Explorer *can* be static, but usually needs backend for data
    ok_be, info, err_be = backend_status(api_base)
    if not ok_be:
        render_backend_offline_banner(api_base, err_be)
        return

    st.header("🧭 Explorer")
    st.caption("Universe & Ranking Explorer")
    
    # Placeholder for Ranking Table
    st.info("Ranking implementation pending integration.")
    
    # Universe Table (Static List for now?)
    # st.dataframe(universe_df)
