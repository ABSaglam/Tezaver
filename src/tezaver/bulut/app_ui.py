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
from tezaver.bulut.ui.pages.rules_editor import render_rules_editor

def main():
    """Main Streamlit application."""
    # ...
    # Navigation
        page = st.radio(
            "Navigation",
            ["Dashboard", "Command Center", "Live Charts", "Explorer", "Journal", "Rules Editor"],
            label_visibility="collapsed",
        )
    # ...
    # Main content
    api_base = "http://localhost:8000"
    
    if page == "Dashboard":
        render_dashboard() 
    elif page == "Command Center":
        render_command_center(api_base)
    elif page == "Live Charts":
        render_live_charts(api_base)
    elif page == "Explorer":
        render_explorer(api_base)
    elif page == "Journal":
        render_journal(api_base)
    elif page == "Rules Editor":
        render_rules_editor(api_base)


if __name__ == "__main__":
    main()
