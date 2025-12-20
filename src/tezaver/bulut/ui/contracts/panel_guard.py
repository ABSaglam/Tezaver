# Tezaver Bulut UI - Panel Guard Contract
import streamlit as st
import traceback
from typing import Callable, Optional

def guarded_render(title_tr: str, fn: Callable[[], None], debug: bool = False) -> None:
    """
    Execute a render function safely.
    Catches exceptions and performs a standard 'Error Card' render.
    """
    try:
        fn()
    except Exception as e:
        # Get full traceback
        tb_str = traceback.format_exc()
        
        # Error Card Container
        with st.container(border=True):
            st.error(f"⚠️ {title_tr} yüklenemedi")
            
            # Short error msg
            st.markdown(f"**Hata:** `{str(e)}`")
            
            # Actions
            col1, col2 = st.columns([1, 1])
            with col1:
                # Retry button
                if st.button("🔄 Tekrar Dene", key=f"retry_{title_tr}"):
                    st.rerun()
            
            with col2:
                # API Docs link if applicable
                # Assuming standard port 8000 for now or fetch from config if possible
                # But here we keep it simple as per contract
                st.link_button("📄 API Docs", "http://localhost:8000/docs")
            
            # Debug info (optional or via toggle)
            if debug or st.toggle("Hata Detayını Göster", key=f"debug_{title_tr}"):
                st.code(tb_str, language="python")
