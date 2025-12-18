import streamlit as st
import requests
import json
import difflib
from tezaver.bulut.core.context import get_context

def get_api_base(default="http://localhost:8000"):
    # Allow override via args if wrapped
    return default

def render_rules_editor(api_base: str = "http://localhost:8000"):
    st.header("📝 Rules Editor")
    
    # helper
    def api_call(method, path, data=None):
        try:
            url = f"{api_base}/rules{path}"
            if method == "GET":
                r = requests.get(url, params=data)
            else:
                r = requests.post(url, json=data)
            
            if r.status_code == 409:
                return False, "BLOCKED: System ARMED on MAINNET."
            if r.status_code != 200:
                return False, f"HTTP {r.status_code}: {r.text}"
            return True, r.json()
        except Exception as e:
            return False, str(e)
            
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📜 Allowlists", "⚖️ Groups & Caps", "🚪 Exit Profiles"])
    
    # A) Allowlists
    with tab1:
        st.subheader("Allowlists")
        al_key = st.selectbox("Select File", ["allowlist", "mainnet_allowlist"])
        
        # Load
        if st.button("Load", key="btn_load_al"):
            ok, res = api_call("GET", "/get", {"key": al_key})
            if ok:
                st.session_state[f"content_{al_key}"] = res["content"]
                st.session_state[f"orig_{al_key}"] = res["content"]
            else:
                st.error(res)
                
        content = st.text_area("Content", st.session_state.get(f"content_{al_key}", ""), height=300, key=f"txt_{al_key}")
        
        c1, c2 = st.columns(2)
        if c1.button("Validate", key=f"btn_val_{al_key}"):
            ok, res = api_call("POST", "/validate", {"key": al_key, "content": content})
            if ok and res.get("ok"): st.success("Valid!")
            else: st.error(f"Invalid: {res.get('errors')}")
            
        if c2.button("💾 Apply Rule", key=f"btn_save_{al_key}"):
            ok, res = api_call("POST", "/apply", {"key": al_key, "content": content})
            if ok: st.success("Applied & Reloaded!")
            else: st.error(res)

    # B) Groups
    with tab2:
        st.subheader("Symbol Groups & Caps")
        g_key = st.selectbox("Select File", ["symbol_groups", "group_caps"])
        
        if st.button("Load", key="btn_load_g"):
            ok, res = api_call("GET", "/get", {"key": g_key})
            if ok:
                # Convert string/json to formatted string for editor
                val = res["content"]
                if isinstance(val, str): val = json.loads(val)
                st.session_state[f"content_{g_key}"] = json.dumps(val, indent=2)
            else:
                st.error(res)
                
        content_json = st.text_area("JSON Content", st.session_state.get(f"content_{g_key}", "{}"), height=400, key=f"txt_{g_key}")
        
        c1, c2 = st.columns(2)
        if c1.button("Validate JSON", key=f"btn_val_{g_key}"):
            try:
                js = json.loads(content_json)
                ok, res = api_call("POST", "/validate", {"key": g_key, "content": js})
                if ok and res.get("ok"): st.success("Valid!")
                else: st.error(f"Invalid: {res.get('errors')}")
            except Exception as e:
                st.error(f"JSON Error: {e}")
                
        if c2.button("💾 Apply Rule", key=f"btn_save_{g_key}"):
            try:
                js = json.loads(content_json)
                ok, res = api_call("POST", "/apply", {"key": g_key, "content": js})
                if ok: st.success("Applied!")
                else: st.error(res)
            except Exception as e:
                st.error(f"JSON Error: {e}")

    # C) Exit Profiles
    with tab3:
        st.subheader("Exit Profiles")
        ok, res = api_call("GET", "/exit_profiles")
        profiles = res if ok else []
        
        # New or Edit
        col_list, col_edit = st.columns([1, 3])
        
        with col_list:
            sel_prof = st.radio("Profiles", profiles)
            if st.button("Refresh List"): st.rerun()
            
        with col_edit:
            if sel_prof:
                if st.button(f"Load {sel_prof}"):
                    ok, res = api_call("GET", "/exit_profiles/get", {"name": sel_prof})
                    if ok:
                        st.session_state[f"prof_{sel_prof}"] = json.dumps(res, indent=2)
                        
                prof_content = st.text_area("Profile JSON", st.session_state.get(f"prof_{sel_prof}", ""), height=400)
                
                if st.button("Apply Profile"):
                    ok, res = api_call("POST", "/exit_profiles/apply", {"name": sel_prof, "content": prof_content})
                    if ok: st.success("Applied!")
                    else: st.error(res)
