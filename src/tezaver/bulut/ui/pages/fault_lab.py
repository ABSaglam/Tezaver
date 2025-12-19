# Tezaver Bulut - Fault Lab UI
"""
Fault Lab Page for Command Center.
Allows injecting controlled faults and viewing results.
"""
import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime

# We assume API is available at localhost:8000 (default dev) or env var
API_BASE = "http://localhost:8000"

def get_profiles():
    try:
        resp = requests.get(f"{API_BASE}/fault/profiles")
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

def get_runs():
    try:
        resp = requests.get(f"{API_BASE}/fault/runs")
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

def get_active():
    try:
        resp = requests.get(f"{API_BASE}/fault/active")
        if resp.status_code == 200:
            return resp.json().get("active_profile_id")
    except:
        pass
    return None

def activate_profile(pid):
    try:
        requests.post(f"{API_BASE}/fault/activate", json={"profile_id": pid})
    except:
        pass

def deactivate_profile():
    try:
        requests.post(f"{API_BASE}/fault/deactivate")
    except:
        pass

def render_fault_lab_page():
    st.title("🧪 Fault Lab")
    st.caption("Controlled Chaos Engineering & Fault Injection")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Scenarios")
        profiles = get_profiles()
        active_id = get_active()
        
        if not profiles:
            st.warning("Backend API not reachable or no profiles.")
        
        # Display list
        for p in profiles:
            is_active = (p["id"] == active_id)
            with st.expander(f"{'🔴' if is_active else '⚪'} {p['name']}", expanded=True):
                st.write(p["description"])
                if is_active:
                    if st.button("Stop", key=f"stop_{p['id']}"):
                        deactivate_profile()
                        st.rerun()
                else:
                    if st.button("Inject Fault", key=f"act_{p['id']}"):
                        activate_profile(p["id"])
                        st.rerun()
    
    with col2:
        st.subheader("Injection Run History")
        runs = get_runs()
        
        if runs:
            # Table view
            df = pd.DataFrame(runs)
            # Reorder cols
            if not df.empty:
                df = df[["started_ts", "scenario_name", "result", "notes", "id"]]
                st.dataframe(
                    df, 
                    column_config={
                        "started_ts": "Time",
                        "scenario_name": "Scenario",
                        "result": st.column_config.TextColumn("Result", help="SUCCESS/FAILED/RUNNING"),
                        "notes": "Notes",
                        "id": "Run ID"
                    },
                    hide_index=True,
                    use_container_width=True
                )
        else:
            st.info("No run history yet.")
            
        st.divider()
        st.info("💡 **Hint**: Faults are injected on the next relevant API/WS call. Monitor logs/Ops Panel for system reaction.")

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    render_fault_lab_page()
