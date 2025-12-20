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
from tezaver.bulut.ui.pages.daily_ops import render_page as render_daily_ops_page


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Tezaver Bulut",
        page_icon="☁️",
        layout="wide"
    )
    
    st.title("☁️ Tezaver Bulut")
    
    # Navigation
    # Navigation
    from tezaver.bulut.ui.contracts.page_registry import Registry
    from tezaver.bulut.ui.register_pages import register_all_pages
    from tezaver.bulut.core.context import get_context

    # Register pages if empty
    if not Registry.list_pages():
        register_all_pages()

    all_pages = Registry.list_pages()
    page_titles = [p.title_tr for p in all_pages]
    
    # Sidebar
    with st.sidebar:
        st.header("Menü")
        # Standard Radio for simple app
        selected_title = st.radio("Git", page_titles, label_visibility="collapsed")
    
    # Main content
    # Find page object
    selected_page = next((p for p in all_pages if p.title_tr == selected_title), None)
    
    if selected_page:
        ctx = get_context()
        
        # --- Ops Token Security Guard ---
        if getattr(selected_page, 'requires_ops_token', False):
             # Check 1: Session State
            has_token = bool(st.session_state.get('ops_token'))
            
            # Check 2: Config/Env (if not in session)
            if not has_token and hasattr(ctx, 'config') and getattr(ctx.config, 'ops_token', None):
                has_token = True

            if not has_token:
                st.error("🔒 Erişim Engellendi (Ops Token Required)")
                st.stop()
                
        selected_page.render_fn(ctx)
    else:
        st.error("Sayfa Yüklenemedi")


if __name__ == "__main__":
    main()
