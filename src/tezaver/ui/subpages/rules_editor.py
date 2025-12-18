# Tezaver Bulut - Rules Editor UI
"""
UI for editing configuration rules and profiles (Exit, Sizing).
"""

import streamlit as st
import json
import requests
from tezaver.bulut.core.context import get_context

def render_rules_editor():
    st.title("🎛️ Rules Editor (Kural Editörü)")
    ctx = get_context()
    
    tabs = st.tabs(["🚦 Exit Profiles", "⚖️ Entry Sizing", "🛡️ Risk Groups"])
    
    # --- Exit Profiles ---
    with tabs[0]:
        st.subheader("Exit Profiles (Çıkış Profilleri)")
        profiles = ctx.rules_registry.list_exit_profiles()
        
        col1, col2 = st.columns([1, 3])
        with col1:
             selected_exit = st.selectbox("Select Profile", profiles, key="exit_prof_sel")
             if st.button("🔄 Refresh List", key="ref_exit"):
                 st.rerun()
                 
        with col2:
             if selected_exit:
                 try:
                     content = ctx.rules_registry.read_exit_profile(selected_exit)
                     st.info(f"Editing: {selected_exit}")
                     
                     # JSON Editor
                     txt = st.text_area("JSON Content", value=json.dumps(content, indent=2), height=400, key="exit_json_editor")
                     
                     if st.button("💾 Save Profile", key="save_exit"):
                         try:
                             new_obj = json.loads(txt)
                             ctx.rules_registry.write_exit_profile(selected_exit, new_obj)
                             st.success(f"Saved {selected_exit}")
                         except Exception as e:
                             st.error(f"Save Failed: {e}")
                             
                 except Exception as e:
                     st.error(f"Load Failed: {e}")
    
    # --- Entry Sizing ---
    with tabs[1]:
        st.subheader("Entry Sizing Formulas v1")
        
        # API-based interaction preferred for validation logic, but registry is direct.
        # Use Registry for list/read, API for Bootstrap/Complex actions?
        # Or just use Registry for MVP editor.
        
        sizing_profiles = ctx.rules_registry.list_entry_sizing_profiles()
        
        col1, col2 = st.columns([1, 3])
        with col1:
             if st.button("🚀 Bootstrap Examples", help="Create default examples if missing"):
                 try:
                     # Call API or implement direct? Context has everything.
                     # Let's use direct loader/registry for MVP to avoid HTTP deps in UI if possible (though context has context).
                     # Actually, `app_backend.py` is running, we could call API.
                     # But let's verify if we can just use requests to localhost if API is up?
                     # Standard Streamlit way in this monolithic app seems to be direct service calls usually?
                     # BUT API has `check_mainnet_safety`. We must respect that.
                     # Sizing API calls `check_mainnet_safety(ctx)`.
                     # We can replicate logic or wrap it.
                     pass 
                 except: pass
                 
             selected_sizing = st.selectbox("Select Sizing Profile", sizing_profiles, key="sizing_prof_sel")
             
             new_name = st.text_input("New Profile Name (e.g. eth_aggro.json)")
             if st.button("➕ Create New"):
                 if new_name and new_name.endswith(".json"):
                     # Create empty template
                     template = {
                         "profile_id": new_name.replace(".json", ""),
                         "version": "1.0",
                         "priority": 10,
                         "scope": {"symbol": "ETHUSDT"},
                         "rule": {"type": "fixed_notional", "fixed_notional_usdt": 20},
                         "safety": {"min_notional_usdt": 10}
                     }
                     try:
                         ctx.rules_registry.write_entry_sizing_profile(new_name, template)
                         st.success(f"Created {new_name}")
                         st.rerun()
                     except Exception as e:
                         st.error(f"Create Failed: {e}")
             
        with col2:
             if selected_sizing:
                 try:
                     content = ctx.rules_registry.read_entry_sizing_profile(selected_sizing)
                     
                     # Validation Status indicator
                     # We can use `EntrySizingProfileV1.from_dict` to check valid
                     from tezaver.bulut.schemas.entry_sizing_profile_v1 import EntrySizingProfileV1
                     c_obj = EntrySizingProfileV1.from_dict(content)
                     if c_obj:
                         st.caption("✅ Schema Valid")
                     else:
                         st.caption("❌ Schema Invalid")
                         
                     txt = st.text_area("JSON Config", value=json.dumps(content, indent=2), height=500, key="sizing_json")
                     
                     if st.button("💾 Apply Sizing Profile", key="save_sizing"):
                         # Check Mainnet Safety
                         # Helper
                         block = False
                         if ctx.config.mode == "REAL_MAINNET" and ctx.state.execution_armed:
                             if getattr(ctx.config, "entry_sizing_edit_block_on_mainnet_armed", True):
                                 st.error("🔒 BLOCKED: Cannot edit Sizing Rules while MAINNET ARMED.")
                                 block = True
                        
                         if not block:
                             try:
                                 new_obj = json.loads(txt)
                                 # Validate Schema
                                 if not EntrySizingProfileV1.from_dict(new_obj):
                                     st.error("Invalid Schema: Rejected")
                                 else:
                                     ctx.rules_registry.write_entry_sizing_profile(selected_sizing, new_obj)
                                     st.success(f"Saved & Applied {selected_sizing}")
                                     # Hot reload trigger? Loader watches file, so it should pick up.
                                     # Or force reload
                                     ctx.entry_sizing_loader.load_all(force=True)
                             except Exception as e:
                                 st.error(f"Save Failed: {e}")
                                 
                 except Exception as e:
                     st.error(f"Load Error: {e}")

    # --- Risk Groups (Placeholder) ---
    with tabs[2]:
        st.info("Risk Groups editing coming soon.")
