# Tezaver Bulut - Daily Ops UI Page (P12)
"""
Streamlit page for Day-2 Operations dashboard.
"""
import streamlit as st
import requests
from datetime import datetime

# API Base URL
API_BASE = "http://localhost:8000"


def render_daily_ops_page():
    """Render the Daily Ops dashboard page."""
    st.header("📅 Daily Ops Dashboard")
    
    # Row 1: Today and Yesterday Reports
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Bugün")
        try:
            res = requests.get(f"{API_BASE}/ops/daily/today", timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data.get("date"):
                    st.metric("Net PnL", f"${data.get('net_pnl', 0):.2f}")
                    st.metric("Trades", data.get("trades_count", 0))
                    st.metric("Alerts", data.get("alerts_count", 0))
                    st.metric("Kill Switch Events", data.get("kill_switch_events", 0))
                    st.metric("Recovery Runs", data.get("recovery_runs", 0))
                else:
                    st.info("Bugün için rapor henüz yok")
        except Exception as e:
            st.error(f"API hatası: {e}")
    
    with col2:
        st.subheader("📊 Dün")
        try:
            res = requests.get(f"{API_BASE}/ops/daily/yesterday", timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data.get("date"):
                    st.metric("Net PnL", f"${data.get('net_pnl', 0):.2f}")
                    st.metric("Trades", data.get("trades_count", 0))
                    st.metric("Alerts", data.get("alerts_count", 0))
                else:
                    st.info("Dün için rapor yok")
        except Exception:
            st.warning("Dün raporu yüklenemedi")
    
    st.divider()
    
    # Row 2: Actions
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Bugün Raporu Oluştur", use_container_width=True):
            try:
                res = requests.post(f"{API_BASE}/ops/daily/compute", timeout=10)
                if res.status_code == 200:
                    st.success("Rapor oluşturuldu!")
                    st.rerun()
                else:
                    st.error(f"Hata: {res.status_code}")
            except Exception as e:
                st.error(f"API hatası: {e}")
    
    with col2:
        if st.button("🏥 Health Check Çalıştır", use_container_width=True):
            try:
                res = requests.post(f"{API_BASE}/ops/daily/health/run", timeout=10)
                if res.status_code == 200:
                    result = res.json()
                    if result.get("result", {}).get("healthy"):
                        st.success("✅ Sistem sağlıklı")
                    else:
                        st.warning("⚠️ Anomaliler tespit edildi")
                    st.rerun()
                else:
                    st.error(f"Hata: {res.status_code}")
            except Exception as e:
                st.error(f"API hatası: {e}")
    
    with col3:
        # Health status
        try:
            res = requests.get(f"{API_BASE}/ops/daily/health/status", timeout=5)
            if res.status_code == 200:
                data = res.json()
                last_check = data.get("last_check_ts")
                if last_check:
                    st.info(f"Son kontrol: {last_check[:19]}")
                else:
                    st.info("Henüz kontrol yapılmadı")
        except Exception:
            pass
    
    st.divider()
    
    # Row 3: Health Checks Timeline
    with st.expander("🏥 Health Checks Timeline", expanded=False):
        try:
            res = requests.get(f"{API_BASE}/ops/daily/health/checks?limit=20", timeout=5)
            if res.status_code == 200:
                checks = res.json()
                if checks:
                    for check in checks[:10]:
                        status = "✅" if check.get("healthy") else "⚠️"
                        ts = check.get("ts", "")[:19]
                        anomalies = check.get("anomalies", [])
                        if anomalies:
                            st.warning(f"{status} {ts} - {len(anomalies)} anomali")
                        else:
                            st.success(f"{status} {ts} - Sağlıklı")
                else:
                    st.info("Henüz health check kaydı yok")
        except Exception as e:
            st.error(f"Health checks yüklenemedi: {e}")
    
    # Row 4: Top Alerts
    with st.expander("🚨 Top Alerts", expanded=False):
        try:
            res = requests.get(f"{API_BASE}/ops/daily/alerts/top?limit=10", timeout=5)
            if res.status_code == 200:
                alerts = res.json()
                if alerts:
                    for alert in alerts:
                        level = alert.get("level", "INFO")
                        icon = "🔴" if level == "BLOCK" else "🟡" if level == "WARN" else "🔵"
                        msg = alert.get("message", "")[:80]
                        action = alert.get("recommended_action")
                        st.markdown(f"{icon} **{level}**: {msg}")
                        if action:
                            st.caption(f"   → {action}")
                else:
                    st.success("Aktif alert yok")
        except Exception as e:
            st.error(f"Alerts yüklenemedi: {e}")


if __name__ == "__main__":
    render_daily_ops_page()
