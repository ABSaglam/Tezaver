# Tezaver Bulut - UI Http Client
"""
Helper for making API requests from Streamlit UI.
Automatically injects Ops Auth Token from session state.
"""

import streamlit as st
import requests
import json
from typing import Optional, Any, Tuple

API_BASE = "http://127.0.0.1:8000"
OPS_HEADER = "X-TEZAVER-OPS-TOKEN"

def get_api_base() -> str:
    return API_BASE

def call_api(method: str, endpoint: str, json_data: Any = None) -> Tuple[bool, Any]:
    """
    Make an API call with Ops Auth support.
    Returns (success: bool, result: data|error_msg).
    """
    url = f"{API_BASE}{endpoint}"
    headers = {}
    
    # Inject Ops Token if present
    token = st.session_state.get("ops_token")
    if token:
        headers[OPS_HEADER] = token
        
    try:
        if method.upper() == "POST":
            resp = requests.post(url, json=json_data, headers=headers)
        elif method.upper() == "PUT":
            resp = requests.put(url, json=json_data, headers=headers)
        elif method.upper() == "DELETE":
            resp = requests.delete(url, headers=headers)
        else: # GET
            resp = requests.get(url, headers=headers)
            
        if resp.status_code in [401, 403]:
            # Ops Auth Denial
            msg = "🔒 Read-Only Mode. Ops Token required for this action."
            if method.upper() == "GET": 
                msg = "🔒 System Locked. Ops Token required."
            st.warning(msg)
            return False, {"detail": msg, "code": "OPS_AUTH_DENY"}
            
        resp.raise_for_status()
        return True, resp.json()
    except Exception as e:
        return False, str(e)
