"""
Tezaver Bulut UI - Result Card Contract
Standardizes API response display and execution logic.
"""
import streamlit as st
import requests
import json
from dataclasses import dataclass
from typing import Optional, Any, Dict

@dataclass
class ApiResult:
    """Standardized API Result"""
    ok: bool
    status_code: int
    method: str
    url: str
    json_body: Optional[Any] = None
    error_text: Optional[str] = None

def call_api(ctx: Any, method: str, path: str, json_data: dict = None, ops_required: bool = False) -> ApiResult:
    """
    Executes an API call using context configuration.
    Handles Ops Token injection if required.
    """
    api_base = "http://localhost:8000"
    if hasattr(ctx, 'config') and hasattr(ctx.config, 'bulut_api_base_url'):
        api_base = ctx.config.bulut_api_base_url
        
    # Policy: GET is always free (read-only)
    if method.upper() == "GET":
        ops_required = False
        
    url = f"{api_base}{path}"
    headers = {}
    
    # Check Ops Token
    if ops_required:
        token = st.session_state.get('ops_token')
        if not token:
            # Check config as fallback
            if hasattr(ctx, 'config') and getattr(ctx.config, 'ops_token', None):
                token = ctx.config.ops_token
                
        if not token:
            return ApiResult(
                ok=False, 
                status_code=403, 
                method=method, 
                url=url, 
                error_text="LOCKED: Ops Token Required (Session Missing)"
            )
        headers["X-Ops-Token"] = token

    try:
        if method.upper() == "GET":
            resp = requests.get(url, headers=headers, timeout=10)
        elif method.upper() == "POST":
            resp = requests.post(url, json=json_data, headers=headers, timeout=10)
        elif method.upper() == "PUT":
            resp = requests.put(url, json=json_data, headers=headers, timeout=10)
        elif method.upper() == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=10)
        else:
             return ApiResult(False, 0, method, url, error_text=f"Unsupported method {method}")
             
        try:
            j = resp.json()
        except:
            j = None
            
        return ApiResult(
            ok=(200 <= resp.status_code < 300),
            status_code=resp.status_code,
            method=method,
            url=url,
            json_body=j,
            error_text=resp.text if resp.status_code >= 400 else None
        )
            
    except Exception as e:
        return ApiResult(
            ok=False, 
            status_code=503, # Service Unavailable / Client Error
            method=method, 
            url=url, 
            error_text=str(e)
        )

def render_result_card(title: str, result: Optional[ApiResult]):
    """
    Renders the result of an API operation.
    """
    if not result:
        return

    icon = "✅" if result.ok else "❌"
    color = "green" if result.ok else "red"
    
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
             st.markdown(f"**{title}**")
             st.caption(f"`{result.method} {result.url}`")
        with c2:
             st.markdown(f":{color}[**{result.status_code}**] {icon}")
             
        if result.error_text:
            st.error(result.error_text)
            
        if result.json_body:
            with st.expander("Response JSON", expanded=not result.ok):
                st.json(result.json_body)
