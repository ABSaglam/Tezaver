import streamlit as st
import pandas as pd
import requests

def render_journal(api_base: str = "http://localhost:8000"):
    st.header("📔 Journal")

    def get_audit():
        try:
            resp = requests.get(f"{api_base}/ui/audit/latest", params={"limit": 50})
            return resp.json() if resp.status_code == 200 else []
        except: return []

    st.subheader("Recent Audits")
    audit_data = get_audit()
    if audit_data:
        df = pd.DataFrame(audit_data)
        st.dataframe(df)
    else:
        st.info("No audit logs found.")
        
    st.divider()
    st.subheader("Income Summary")
    # Call /income/today
    try:
        res = requests.get(f"{api_base}/ui/income/today").json()
        st.json(res)
    except:
        st.error("Income fetch failed")
