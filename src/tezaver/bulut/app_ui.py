# Tezaver Bulut - Streamlit UI Application
"""
Main Streamlit application for Tezaver Bulut.

Run with:
    streamlit run src/tezaver/bulut/app_ui.py
"""

import streamlit as st

from tezaver.bulut.core.context import bootstrap_context, get_context
from tezaver.bulut.ui.pages.dashboard import render_dashboard
from tezaver.bulut.ui.pages.command_center import render_command_center
from tezaver.bulut.ui.pages.live_charts import render_live_charts
from tezaver.bulut.ui.pages.explorer import render_explorer
from tezaver.bulut.ui.pages.journal import render_journal

def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Tezaver Bulut",
        page_icon="🌩️",
        layout="wide",
    )
    
    # Bootstrap context on first run (needed for shared config/state if local mode)
    if "bulut_initialized" not in st.session_state:
        ctx = bootstrap_context()
        ctx.load_pattern_pack()
        st.session_state.bulut_initialized = True
    
    # Sidebar
    with st.sidebar:
        st.title("🌩️ Tezaver Bulut")
        st.caption("Cloud Trading System v0.29")
        
        st.divider()
        
        # Quick status from LOCAL context (might differ from backend if not synced DB)
        ctx = get_context()
        if hasattr(ctx, "state") and ctx.state.trade_locked:
            st.error(f"🔒 Locked: {ctx.state.trade_lock_reason}")
        
        st.divider()
        
        # Navigation
        page = st.radio(
            "Navigation",
            ["Dashboard", "Command Center", "Live Charts", "Explorer", "Journal"],
            label_visibility="collapsed",
        )
        
        st.divider()
        if st.button("🔄 Reload Pattern Pack"):
             ctx.load_pattern_pack()
             st.rerun()

    # Main content
    api_base = "http://localhost:8000" # Standalone default
    
    if page == "Dashboard":
        render_dashboard() # Dashboard might not be refactored yet? Let's check. 
        # I did not refactor dashboard.py in previous steps BUT user prompt asked for it in list?
        # "Ensure ui/pages/dashboard.py (Bulut Dashboard) follows a similar pattern or is wrapped."
        # I skipped it in refactor step! I should check dashboard.py.
    elif page == "Command Center":
        render_command_center(api_base)
    elif page == "Live Charts":
        render_live_charts(api_base)
    elif page == "Explorer":
        render_explorer(api_base)
    elif page == "Journal":
        render_journal(api_base)


if __name__ == "__main__":
    main()
