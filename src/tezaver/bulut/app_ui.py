# Tezaver Bulut - Streamlit UI Application
"""
Main Streamlit application for Tezaver Bulut.

Run with:
    streamlit run src/tezaver/bulut/app_ui.py
"""

import sys
from pathlib import Path

# --- BOOTSTRAP PYTHONPATH ---
src_path = Path(__file__).resolve().parents[2]  # src/tezaver/bulut/app_ui.py -> src
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import streamlit as st

from tezaver.bulut.ui.pages.dashboard import render_dashboard
from tezaver.bulut.ui.pages.command_center import render_command_center
from tezaver.bulut.ui.pages.live_charts import render_live_charts
from tezaver.bulut.ui.pages.explorer import render_explorer
from tezaver.bulut.ui.pages.rules_editor import render_rules_editor
from tezaver.bulut.ui.pages.daily_ops import render_daily_ops_page


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Tezaver Bulut",
        page_icon="☁️",
        layout="wide"
    )
    
    st.title("☁️ Tezaver Bulut")
    
    # Navigation
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Navigation",
            ["Dashboard", "Command Center", "Daily Ops", "Live Charts", "Explorer", "Rules Editor"],
            label_visibility="collapsed",
        )
    
    # Main content
    api_base = "http://localhost:8000"
    
    if page == "Dashboard":
        render_dashboard() 
    elif page == "Command Center":
        render_command_center(api_base)
    elif page == "Daily Ops":
        render_daily_ops_page()
    elif page == "Live Charts":
        render_live_charts(api_base)
    elif page == "Explorer":
        render_explorer(api_base)
    elif page == "Rules Editor":
        render_rules_editor(api_base)


if __name__ == "__main__":
    main()
