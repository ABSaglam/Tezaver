# Tezaver Bulut - Replay Lab UI
"""
Replay Lab Page for Command Center.
Allows creating replay bundles and running executing them.
"""
import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime

API_BASE = "http://localhost:8000"

def create_bundle(notes: str):
    try:
        resp = requests.post(f"{API_BASE}/replay/bundle/create", json={"notes": notes})
        if resp.status_code == 200:
            return resp.json().get("bundle_id")
        else:
            st.error(f"Error creating bundle: {resp.text}")
    except Exception as e:
        st.error(f"Req Error: {e}")
    return None

def get_bundles():
    try:
        resp = requests.get(f"{API_BASE}/replay/bundles/latest")
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

def run_replay(bundle_id: str):
    try:
        resp = requests.post(f"{API_BASE}/replay/run", json={"bundle_id": bundle_id})
        if resp.status_code == 200:
            return resp.json()
        else:
            st.error(f"Replay Failed: {resp.text}")
    except Exception as e:
        st.error(f"Req Error: {e}")
    return None

def render_replay_lab_page():
    st.title("▶️ Replay Lab")
    st.caption("Deterministic Trade Cycle Replay & Drift Detection")
    
    col_create, col_list = st.columns([1, 2])
    
    with col_create:
        st.subheader("Capture State")
        with st.form("create_bundle_form"):
            notes = st.text_input("Notes (Optional)", placeholder="e.g. Pre-deploy snapshot")
            if st.form_submit_button("📷 Create Replay Bundle"):
                bid = create_bundle(notes)
                if bid:
                    st.success(f"Bundle Created: {bid[:8]}...")
                    st.rerun()
    
    st.divider()
    
    st.subheader("Replay Bundles")
    bundles = get_bundles()
    
    if bundles:
        # Convert to DF for display
        df = pd.DataFrame(bundles)
        
        # Grid layout
        for i, row in df.iterrows():
            with st.expander(f"{row['created_ts']} | Status: {row['status'] or 'NEW'} | {row['notes']}", expanded=False):
                colA, colB = st.columns(2)
                with colA:
                    st.text(f"ID: {row['bundle_id']}")
                    st.text(f"Cycle: {row['cycle_ts']}")
                
                with colB:
                    if st.button("▶️ Run Replay", key=f"run_{row['bundle_id']}"):
                        with st.spinner("Replaying..."):
                            res = run_replay(row['bundle_id'])
                            if res:
                                st.success(f"Result: {res['status']}")
                                if res.get("drift_details"):
                                    st.json(res["drift_details"])
                                else:
                                    st.caption("No drift detected.")
                                    
                # Show result if exists?
                # We could fetch result via API if needed, but the Run button shows it ephemeral for now.
    else:
        st.info("No bundles found.")

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    render_replay_lab_page()
