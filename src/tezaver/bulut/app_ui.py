# Tezaver Bulut - Streamlit UI Application
"""
Main Streamlit application for Tezaver Bulut.

Run with:
    streamlit run src/tezaver/bulut/app_ui.py
"""

import streamlit as st

from tezaver.bulut.core.context import bootstrap_context, get_context
from tezaver.bulut.ui.pages.dashboard import render_dashboard


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Tezaver Bulut",
        page_icon="🌩️",
        layout="wide",
    )
    
    # Bootstrap context on first run
    if "bulut_initialized" not in st.session_state:
        ctx = bootstrap_context()
        ctx.load_pattern_pack()
        st.session_state.bulut_initialized = True
    
    # Sidebar
    with st.sidebar:
        st.title("🌩️ Tezaver Bulut")
        st.caption("Cloud Trading System v0.01")
        
        st.divider()
        
        # Quick status
        ctx = get_context()
        
        if ctx.state.trade_locked:
            st.error(f"🔒 Locked: {ctx.state.trade_lock_reason}")
        else:
            st.success("🟢 Ready to trade")
        
        st.divider()
        
        # Navigation (single page for now)
        page = st.radio(
            "Navigation",
            ["Dashboard"],
            label_visibility="collapsed",
        )
        
        st.divider()
        
        # Reload pattern pack button
        if st.button("🔄 Reload Pattern Pack"):
            if ctx.load_pattern_pack():
                st.success("Pattern pack reloaded!")
            else:
                st.warning("No pattern pack found")
            st.rerun()
    
    # Main content
    if page == "Dashboard":
        render_dashboard()


if __name__ == "__main__":
    main()
