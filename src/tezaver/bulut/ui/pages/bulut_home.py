"""
Tezaver Bulut - Home Page (Runbook Dashboard)
Aggregates critical system status, quick actions, and alerts.
"""
import streamlit as st
import requests
import pandas as pd
from datetime import datetime

from tezaver.bulut.ui.contracts.panel_guard import guarded_render
from tezaver.bulut.ui.contracts.backend_guard import backend_status, render_backend_offline_banner
from tezaver.bulut.ui.contracts.build_fingerprint import get_build_fingerprint

def render_page(ctx=None):
    """Entrypoint for Registry."""
    guarded_render("Ana Sahne", lambda: _render_content(ctx))

def _render_content(ctx=None):
    """Actual content logic."""
    # --- Build Fingerprint & Dev Tools ---
    fp = get_build_fingerprint()
    with st.expander(f"🛠️ Build: {fp.get('git_head')} | PID: {fp.get('pid')} | {fp.get('build_ts')}", expanded=False):
        st.caption(f"Watcher: {fp.get('watcher_type')}")
        st.markdown("**Reload Hardening Tips:**")
        st.code(f"""# If UI is stale or stuck:
pkill -f "streamlit run"
streamlit cache clear
export STREAMLIT_SERVER_FILE_WATCHER_TYPE=poll
streamlit run src/tezaver/ui/main_panel.py""", language="bash")
        
        if st.button("🧹 Clear Streamlit Cache", use_container_width=True):
             st.cache_data.clear()
             st.cache_resource.clear()
             st.success("Cache Cleared! Reload page.")

    # 1. Backend Check
    api_base = "http://localhost:8000"
    if ctx and hasattr(ctx, 'config') and hasattr(ctx.config, 'bulut_api_base_url'):
        api_base = ctx.config.bulut_api_base_url
        
    ok_be, info, err_be = backend_status(api_base)
    if not ok_be:
        render_backend_offline_banner(api_base, err_be)
        return

    # 2. Fetch Snapshot
    try:
        snap_resp = requests.get(f"{api_base}/runbook/snapshot")
        if snap_resp.status_code == 200:
            snap = snap_resp.json()
        else:
            st.error(f"Snapshot Failed: {snap_resp.status_code}")
            return
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return

    # 3. Header & Timestamp
    c1, c2 = st.columns([3, 1])
    with c1:
        st.header("🌩️ Operasyon Sahnesi")
        st.caption("Tezaver Bulut Runbook Dashboard")
    with c2:
        if st.button("🔄 Yenile", use_container_width=True):
            st.rerun()
        st.caption(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")

    st.markdown("---")

    # 4. Critical Status Grid
    # Metrics: Mode, Autopilot, Budget, Active Alerts
    
    mode_info = snap.get("mode", {})
    pilot_info = snap.get("pilot_meter", {})
    auto_info = snap.get("autopilot", {})
    perf_info = snap.get("perf_cost", {})
    
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        mode_val = mode_info.get("current", "UNKNOWN")
        st.metric("Mode", mode_val, delta="MAINNET" if mode_info.get("is_mainnet") else "SIM")
        
    with m2:
        auto_on = auto_info.get("enabled", False)
        st.metric("Autopilot", "ON" if auto_on else "OFF", delta_color="normal" if auto_on else "off")
        
    with m3:
        committed = pilot_info.get("committed_usdt", 0)
        limit = pilot_info.get("limit_usdt", 50)
        usage = (committed / limit * 100) if limit > 0 else 0
        st.metric("Budget Meter", f"${committed:.1f} / ${limit}", f"{usage:.1f}%")
        
    with m4:
        perf_mode = perf_info.get("mode", "UNKNOWN")
        cycle = perf_info.get("cycle_ms", 0)
        st.metric("Cycle Perf", f"{cycle}ms", perf_mode)

    # 5. Alerts Panel
    st.subheader("🔔 Son Olaylar")
    
    try:
        alerts_resp = requests.get(f"{api_base}/ops/alerts", params={"limit": 10})
        alerts = alerts_resp.json().get("alerts", []) if alerts_resp.status_code == 200 else []
        
        if alerts:
            df = pd.DataFrame(alerts)
            # Pick useful columns if exist
            cols = ["ts", "level", "component", "msg"]
            existing_cols = [c for c in cols if c in df.columns]
            st.dataframe(df[existing_cols], use_container_width=True, hide_index=True)
        else:
            st.info("Temiz. Alarm yok.")
            
    except Exception:
        st.warning("Could not fetch alerts")

    st.markdown("---")

    # 6. Quick Actions (Guarded)
    st.subheader("⚡ Hızlı İşlemler")
    
    ac1, ac2, ac3 = st.columns(3)
    
    with ac1:
        # Navigation shortcuts
        st.markdown("**Git:**")
        if st.button("📅 Daily Ops Panel", use_container_width=True):
             st.session_state['cloud_nav'] = "Günlük Operasyon"
             st.rerun()
        if st.button("🎛️ Command Center", use_container_width=True):
             st.session_state['cloud_nav'] = "Komuta Merkezi"
             st.rerun()

    with ac2:
        # Export Incident - Requires Ops Token
        st.markdown("**Incident:**")
        has_token = bool(st.session_state.get('ops_token'))
        
        if has_token:
            reason = st.text_input("Incident Reason", value="Manual Export")
            if st.button("📦 Export Incident Bundle", type="primary"):
                try:
                    r = requests.post(
                        f"{api_base}/ops/incident/export", 
                        json={"reason": reason},
                        headers={"X-Ops-Token": st.session_state['ops_token']}
                    )
                    if r.status_code == 200:
                        st.success(f"Export Started: {r.json().get('path')}")
                    else:
                        st.error(f"Failed: {r.text}")
                except Exception as e:
                    st.error(str(e))
        else:
            st.button("📦 Export Incident (Locked 🔒)", disabled=True, help="Ops Token only")

    with ac3:
        if st.button("📊 Gelişmiş Raporlar"):
            st.session_state['cloud_nav'] = "Test Raporu" # Redirect trick
            st.rerun()


if __name__ == "__main__":
    render_page()
