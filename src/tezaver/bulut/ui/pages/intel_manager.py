# Tezaver Bulut - Intel Manager UI
"""
Intel Manager Page.
Controls for Intel Bundle Lifecycle: Publish, Activate, Rollback.
"""

import streamlit as st
import requests
import json
from datetime import datetime

def render_intel_manager(api_base: str):
    st.header("🧠 Intel Manager")
    
    # Helper API
    def api_get(endpoint):
        try:
            r = requests.get(f"{api_base}{endpoint}")
            r.raise_for_status()
            return True, r.json()
        except Exception as e:
            return False, str(e)
            
    def api_post(endpoint, json_data):
        try:
            r = requests.post(f"{api_base}{endpoint}", json=json_data)
            r.raise_for_status()
            return True, r.json()
        except Exception as e:
            try:
                # Try to get error detail
                err = r.json().get("detail", str(e))
                return False, err
            except:
                return False, str(e)

    # 1. Fetch Data
    ok_active, active_data = api_get("/intel/active")
    ok_list, list_data = api_get("/intel/list?limit=20")
    
    if not ok_active or not ok_list:
        st.error("Failed to load Intel data. Is backend running?")
        return

    active_ptr = active_data.get("active", {})
    published = list_data.get("published", [])
    incoming = list_data.get("incoming", [])

    # 2. Active Bundle Display
    st.subheader("Current Active Intel")
    if active_ptr:
        c1, c2, c3 = st.columns(3)
        c1.metric("Bundle ID", active_ptr.get("bundle_id", "Unknown")[:8] + "...")
        c2.metric("Activated At", active_ptr.get("activated_at", "Unknown").split(".")[0].replace("T", " "))
        c3.code(active_ptr.get("hash", "")[:8], language="text")
        
        with st.expander("Active Pointer Details"):
            st.json(active_ptr)
    else:
        st.warning("No Active Intel found! System may be using legacy/fallback patterns.")
        
    st.divider()
    
    # 3. Incoming (Upload/Publish)
    st.subheader(f"Incoming Bundles ({len(incoming)})")
    if incoming:
        for bundle_id in incoming:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{bundle_id}**")
                if c2.button("🚀 Publish", key=f"pub_{bundle_id}"):
                    ok, res = api_post("/intel/publish", {"bundle_id": bundle_id})
                    if ok:
                        st.success(f"Published {bundle_id}")
                        st.rerun()
                    else:
                        st.error(f"Failed: {res}")
    else:
        st.info("No incoming bundles.")

    st.divider()

    # 4. Published (Activate/Rollback)
    st.subheader(f"Published History ({len(published)})")
    if published:
        # Table Header
        h1, h2, h3, h4 = st.columns([2, 2, 3, 2])
        h1.markdown("**Bundle ID**")
        h2.markdown("**Built At**")
        h3.markdown("**Hash**")
        h4.markdown("**Action**")
        
        for p in published:
            bid = p.get("bundle_id")
            built = p.get("built_at", "").split(".")[0].replace("T", " ")
            bhash = p.get("bundle_hash", "")[:8]
            
            is_active = (active_ptr and active_ptr.get("bundle_id") == bid)
            
            c1, c2, c3, c4 = st.columns([2, 2, 3, 2])
            c1.code(bid[:8])
            c2.caption(built)
            c3.caption(bhash)
            
            with c4:
                if is_active:
                    st.success("ACTIVE")
                else:
                    if st.button("Activate", key=f"act_{bid}"):
                        ok, res = api_post("/intel/activate", {"bundle_id": bid})
                        if ok:
                            st.success(f"Activated {bid}")
                            st.rerun()
                        else:
                            st.error(f"Failed: {res}")
            
            with st.expander(f"Details {bid[:8]}"):
                st.json(p)
    else:
        st.info("No published bundles.")
