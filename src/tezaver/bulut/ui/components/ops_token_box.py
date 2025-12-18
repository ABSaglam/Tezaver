# Tezaver Bulut - Ops Token Box
"""
UI Component for entering Ops Token.
"""

import streamlit as st

def render_ops_token_box():
    """Render Ops Token input in sidebar or top bar."""
    
    # Initialize session state (default empty)
    if "ops_token" not in st.session_state:
        st.session_state["ops_token"] = ""
        
    current = st.session_state["ops_token"]
    
    with st.expander("🛡️ Ops Auth", expanded=False):
        # Determine status (Naive check: is non-empty?)
        # Ideally we verify with backend health check?
        # For now, just unlocked/locked UI state.
        
        status = "Open" if not current else "Key Provided"
        st.caption(f"Status: {status}")
        
        new_token = st.text_input("Ops Token", value=current, type="password", help="Enter TEZAVER_OPS_TOKEN to enable mutations.")
        
        if new_token != current:
            st.session_state["ops_token"] = new_token
            st.rerun()

        if new_token:
            if st.button("Clear Token"):
                st.session_state["ops_token"] = ""
                st.rerun()
