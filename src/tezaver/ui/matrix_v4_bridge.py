"""
Matrix V4 Bridge - Streamlit SIM mode to V4 Panel

This module bridges the Streamlit UI to the V4 Panel server.
IMPORTANT: This module does NOT import any tezaver.matrix.* modules.
"""

import streamlit as st
import json
from urllib.request import urlopen, Request
from urllib.error import URLError

PANEL_URL = "http://localhost:8085"
DEBUG_URL = f"{PANEL_URL}/_debug/build"

def parse_debug_build(json_text: str) -> dict:
    """Parse debug/build JSON response."""
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return {}

def fetch_panel_status(timeout: float = 0.5) -> dict:
    """Fetch panel status from /_debug/build endpoint."""
    try:
        req = Request(DEBUG_URL)
        with urlopen(req, timeout=timeout) as resp:
            return parse_debug_build(resp.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError):
        return {}

def render_matrix_v4_bridge() -> None:
    """Render V4 Panel bridge in Streamlit."""
    st.header("🎛️ Matrix V4 Panel")
    
    st.info(f"""
    **V4 Matrix Panel** artık ayrı bir HTTP sunucusu olarak çalışıyor.
    
    🔗 **Panel URL:** [{PANEL_URL}]({PANEL_URL})
    
    Panel'i başlatmak için:
    ```bash
    PYTHONPATH=$(pwd)/src python3 -m tezaver.matrix.apps.panel_server --home .tezaver_matrix
    ```
    """)
    
    st.divider()
    
    # Try to fetch panel status
    with st.spinner("Panel durumu kontrol ediliyor..."):
        status = fetch_panel_status()
    
    if status:
        st.success("✅ V4 Panel çalışıyor!")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Commit", status.get("commit", "unknown"))
            st.metric("Branch", status.get("branch", "unknown"))
        with col2:
            st.metric("Home", status.get("home", "unknown")[:30] + "...")
            
        counts = status.get("counts", {})
        st.subheader("📊 Data Counts")
        cols = st.columns(6)
        for i, (k, v) in enumerate(counts.items()):
            cols[i % 6].metric(k, v)
            
        st.caption(f"Panel File: {status.get('panel_file', 'unknown')}")
    else:
        st.warning("""
        ⚠️ **V4 Panel çalışmıyor olabilir.**
        
        Panel'i başlatın:
        ```bash
        PYTHONPATH=$(pwd)/src python3 -m tezaver.matrix.apps.panel_server --home .tezaver_matrix
        ```
        
        Sonra bu sayfayı yenileyin.
        """)
    
    st.divider()
    
    # Quick links
    st.subheader("🔗 Hızlı Linkler")
    st.markdown(f"""
    - [Ana Sayfa]({PANEL_URL}/)
    - [Operasyon Merkezi]({PANEL_URL}/ops)
    - [Cloud Runtime]({PANEL_URL}/cloud/runtime)
    - [Cloud Loop]({PANEL_URL}/cloud/loop)
    - [Rehearsal Checklist]({PANEL_URL}/rehearsal)
    - [Alarmlar]({PANEL_URL}/alerts)
    - [Debug Build Info]({PANEL_URL}/_debug/build)
    """)
