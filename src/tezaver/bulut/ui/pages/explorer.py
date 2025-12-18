import streamlit as st
import pandas as pd

def render_explorer(api_base: str = "http://localhost:8000"):
    st.header("🧭 Explorer")
    st.caption("Universe & Ranking Explorer")
    
    # Placeholder for Ranking Table
    st.info("Ranking implementation pending integration.")
    
    # Universe Table (Static List for now?)
    # st.dataframe(universe_df)
