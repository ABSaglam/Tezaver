# Tezaver Bulut UI - Backend Guard Contract
import streamlit as st
import requests
from typing import Tuple, Dict, Optional, Any

def backend_status(api_base_url: str) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Check backend connectivity.
    Returns (ok, info_dict, error_msg).
    """
    try:
        # Try detailed health check first, then root, then generic status
        # Contract says: /health/detailed or /status
        
        target = f"{api_base_url}/health/detailed"
        try:
            resp = requests.get(target, timeout=2.0)
            if resp.status_code == 200:
                return True, resp.json(), None
        except requests.exceptions.RequestException:
            pass # Fallback
            
        # Fallback to root or simple status
        target = f"{api_base_url}/"
        resp = requests.get(target, timeout=2.0)
        if resp.status_code == 200:
            return True, resp.json(), None
            
        return False, {}, f"Status code: {resp.status_code}"
        
    except requests.exceptions.ConnectionError:
        return False, {}, "Connection Refused (Is backend running?)"
    except requests.exceptions.Timeout:
        return False, {}, "Connection Timed Out"
    except Exception as e:
        return False, {}, str(e)


def render_backend_offline_banner(api_base_url: str, error: Optional[str] = None):
    """
    Render a standard offline banner at the top of the app.
    """
    st.warning("🚫 Backend offline / erişilemiyor", icon="🚫")
    
    with st.expander("Sorun Giderme / Troubleshooting", expanded=True):
        st.markdown(f"**Target API:** `{api_base_url}`")
        if error:
            st.markdown(f"**Error:** `{error}`")
            
        st.info("Backend sunucusunu başlatmak için terminal komutu:")
        st.code("uvicorn tezaver.bulut.app_backend:app --reload --port 8000", language="bash")
        
        if st.button("🔄 Bağlantıyı Tekrar Dene", type="primary"):
            st.rerun()
