"""
MX-20007: Panel Connectors - Streamlit UI for Platform

Provides Connectors, Jobs, and Ops pages in Streamlit.
"""

import streamlit as st
import json
import os
from urllib.request import urlopen, Request
from urllib.error import URLError
from typing import Dict, Any, Optional

from tezaver.platform.bus.adapter import FsBusAdapter
from tezaver.platform.jobs.queue import (
    create_job, enqueue_job, list_jobs, Job
)


# ============================================================================
# CONNECTORS PAGE
# ============================================================================

def render_platform_connectors():
    """Render Platform Connectors page."""
    st.header("🔌 Platform Connectors")
    
    st.info("""
    Bu sayfada Mac, Matrix ve Cloud agent'larının bağlantı ayarlarını yapabilirsiniz.
    Şu an FS (dosya sistemi) üzerinden çalışıyoruz.
    """)
    
    # Connector settings
    st.subheader("⚙️ Bağlantı Ayarları")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🍎 Mac Agent")
        mac_url = st.text_input("Base URL", "http://localhost:9001", key="mac_url")
        mac_token = st.text_input("Token", "", type="password", key="mac_token")
        if st.button("Test Mac", key="test_mac"):
            _test_agent_health(mac_url)
            
    with col2:
        st.markdown("### 🎛️ Matrix Agent")
        matrix_url = st.text_input("Base URL", "http://localhost:9002", key="matrix_url")
        matrix_token = st.text_input("Token", "", type="password", key="matrix_token")
        if st.button("Test Matrix", key="test_matrix"):
            _test_agent_health(matrix_url)
            
    with col3:
        st.markdown("### ☁️ Cloud Agent")
        cloud_url = st.text_input("Base URL", "http://localhost:9003", key="cloud_url")
        cloud_token = st.text_input("Token", "", type="password", key="cloud_token")
        if st.button("Test Cloud", key="test_cloud"):
            _test_agent_health(cloud_url)
            
    st.divider()
    
    # Bus settings
    st.subheader("📦 Bus Ayarları")
    bus_root = st.text_input("Bus Root Path", ".tezaver_bus", key="bus_root")
    st.session_state["platform_bus_root"] = bus_root
    
    if st.button("Bus Root Oluştur"):
        os.makedirs(bus_root, exist_ok=True)
        st.success(f"✅ Bus root oluşturuldu: {bus_root}")


def _test_agent_health(base_url: str):
    """Test agent health endpoint."""
    try:
        req = Request(f"{base_url}/health")
        with urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode())
            st.success(f"✅ Bağlı: {data.get('agent', 'unknown')}")
    except Exception as e:
        st.error(f"❌ Bağlantı hatası: {e}")


# ============================================================================
# JOBS PAGE
# ============================================================================

def render_platform_jobs():
    """Render Platform Jobs page."""
    st.header("📋 Job Queue")
    
    bus_root = st.session_state.get("platform_bus_root", ".tezaver_bus")
    bus = FsBusAdapter(bus_root)
    
    # Target selector
    target = st.selectbox("Target Agent", ["mac", "matrix", "cloud"])
    
    # Queue tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📥 Inbox", "⚙️ Processing", "📤 Outbox", "💀 Deadletter", "➕ Create Job"])
    
    with tab1:
        jobs = list_jobs(bus, target, "inbox")
        if jobs:
            for j in jobs:
                with st.expander(f"{j.get('job_type')} - {j.get('job_id')}"):
                    st.json(j)
        else:
            st.info("Inbox boş")
            
    with tab2:
        jobs = list_jobs(bus, target, "processing")
        if jobs:
            for j in jobs:
                with st.expander(f"{j.get('job_type')} - {j.get('job_id')}"):
                    st.json(j)
        else:
            st.info("Processing boş")
            
    with tab3:
        jobs = list_jobs(bus, target, "outbox")
        if jobs:
            for j in jobs:
                with st.expander(f"{j.get('job_id')} - {j.get('status')}"):
                    st.json(j)
        else:
            st.info("Outbox boş")
            
    with tab4:
        jobs = list_jobs(bus, target, "deadletter")
        if jobs:
            for j in jobs:
                with st.expander(f"{j.get('job_id')} - {j.get('deadletter_reason', 'unknown')}"):
                    st.json(j)
        else:
            st.info("Deadletter boş")
            
    with tab5:
        st.subheader("➕ Yeni Job Oluştur")
        
        job_types = {
            "mac": ["MAC_BUILD_CANDIDATE"],
            "matrix": ["MATRIX_IMPORT_CANDIDATE", "MATRIX_RUN_SNIPER", "MATRIX_RUN_WAR", "MATRIX_APPROVE_EXPORT"],
            "cloud": ["CLOUD_IMPORT_STRATEGY", "CLOUD_RUNTIME_TICK", "CLOUD_PAUSE", "CLOUD_RESUME"],
        }
        
        job_type = st.selectbox("Job Type", job_types.get(target, []))
        payload_str = st.text_area("Payload (JSON)", "{}")
        priority = st.slider("Priority", 1, 100, 50)
        
        if st.button("Create Job"):
            try:
                payload = json.loads(payload_str)
                job = create_job(job_type, target, payload, priority)
                enqueue_job(bus, job)
                st.success(f"✅ Job oluşturuldu: {job.job_id}")
            except Exception as e:
                st.error(f"Hata: {e}")


# ============================================================================
# OPS PAGE (MX-24002: Single Pane Dashboard)
# ============================================================================

def render_platform_ops():
    """Render Platform Ops single-pane dashboard."""
    st.header("📊 Ops Control Center")
    
    bus_root = st.session_state.get("platform_bus_root", ".tezaver_bus")
    from tezaver.platform.bus.adapter import create_bus_adapter
    bus = create_bus_adapter(bus_root)
    
    # -------------------------------------------------------------------------
    # 1. Agent Health Cards
    # -------------------------------------------------------------------------
    st.subheader("🏥 Agent Health")
    
    col1, col2, col3 = st.columns(3)
    
    agents = [
        ("🍎 Mac", "http://127.0.0.1:9001", "mac"),
        ("🎛️ Matrix", "http://127.0.0.1:9002", "matrix"),
        ("☁️ Cloud", "http://127.0.0.1:9003", "cloud"),
    ]
    
    for col, (icon, url, name) in zip([col1, col2, col3], agents):
        with col:
            health = _fetch_agent_health(url)
            _render_health_card(icon, health, url)
            
    st.divider()
    
    # -------------------------------------------------------------------------
    # 2. Cloud Runtime Summary
    # -------------------------------------------------------------------------
    st.subheader("☁️ Cloud Runtime")
    
    col_a, col_b, col_c, col_d = st.columns(4)
    
    with col_a:
        paused = _get_cloud_paused(bus)
        if paused:
            st.error("🔴 PAUSED")
        else:
            st.success("🟢 RUNNING")
            
    with col_b:
        strat_count = _count_active_strategies(bus)
        st.metric("Active Strategies", strat_count)
        
    with col_c:
        events = bus.tail_events("cloud", 20)
        tick_events = [e for e in events if e.get("kind") == "RUNTIME_TICK"]
        last_tick = tick_events[0].get("ts", "-") if tick_events else "-"
        st.metric("Last Tick", last_tick if last_tick == "-" else _format_ts(last_tick))
        
    with col_d:
        total_ticks = len([e for e in bus.tail_events("cloud", 100) if e.get("kind") == "RUNTIME_TICK"])
        st.metric("Recent Ticks", total_ticks)
        
    st.divider()
    
    # -------------------------------------------------------------------------
    # 3. SLO Mini Metrics
    # -------------------------------------------------------------------------
    st.subheader("📈 SLO Metrics (Son 100 Event)")
    
    col_1, col_2, col_3, col_4, col_5 = st.columns(5)
    
    all_events = _merge_all_events(bus, 100)
    
    with col_1:
        gaps = len([e for e in all_events if "GAP" in e.get("kind", "")])
        st.metric("🔴 GAP", gaps)
        
    with col_2:
        blocks = len([e for e in all_events if "BLOCK" in e.get("kind", "")])
        st.metric("🟠 BLOCK", blocks)
        
    with col_3:
        fails = len([e for e in all_events if "FAIL" in e.get("kind", "")])
        st.metric("❌ FAIL", fails)
        
    with col_4:
        ticks = len([e for e in all_events if "TICK" in e.get("kind", "")])
        st.metric("✅ TICK", ticks)
        
    with col_5:
        complete = len([e for e in all_events if "COMPLETED" in e.get("kind", "") or "JOB_OK" in e.get("kind", "")])
        st.metric("✅ OK", complete)
        
    st.divider()
    
    # -------------------------------------------------------------------------
    # 4. Alerts Widget
    # -------------------------------------------------------------------------
    with st.expander("🚨 Alerts (Beta)", expanded=False):
        alerts = _get_alerts(bus)
        if alerts:
            for alert in alerts:
                severity = alert.get("severity", "INFO")
                color = "red" if severity == "CRIT" else "orange" if severity == "WARN" else "blue"
                st.markdown(f":{color}[{severity}] {alert.get('message', alert.get('kind', 'Unknown'))}")
            if st.button("✓ Acknowledge All"):
                _ack_all_alerts(bus)
                st.success("Alerts acknowledged")
        else:
            st.info("No active alerts")
            
    st.divider()
    
    # -------------------------------------------------------------------------
    # 5. Unified Event Timeline
    # -------------------------------------------------------------------------
    st.subheader("📜 Unified Event Timeline")
    
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        stream_filter = st.selectbox("Stream", ["all", "mac", "matrix", "cloud"])
    with col_filter2:
        type_filter = st.text_input("Type contains", "")
        
    # Merge events from all streams
    events = _merge_all_events(bus, 200)
    
    # Apply filters
    if stream_filter != "all":
        events = [e for e in events if e.get("_stream") == stream_filter]
    if type_filter:
        events = [e for e in events if type_filter.lower() in e.get("kind", "").lower()]
        
    # Display
    st.text(f"Showing {len(events)} events")
    
    for e in events[:50]:
        ts = e.get("ts", "-")
        stream = e.get("_stream", "?")
        kind = e.get("kind", "?")
        job_id = e.get("job_id", "")[:10] if e.get("job_id") else ""
        
        # Severity color
        if "FAIL" in kind or "BLOCK" in kind or "GAP" in kind:
            color = "red"
        elif "WARN" in kind or "DEADLETTER" in kind:
            color = "orange"
        else:
            color = "green"
            
        st.markdown(f":{color}[{_format_ts(ts)}] **{stream}** | {kind} | {job_id}")


def _fetch_agent_health(url: str) -> Dict:
    """Fetch agent health."""
    try:
        req = Request(f"{url}/health")
        with urlopen(req, timeout=2) as resp:
            return json.loads(resp.read().decode())
    except:
        return {"status": "unhealthy", "error": "Connection failed"}


def _render_health_card(icon: str, health: Dict, url: str):
    """Render single health card."""
    st.markdown(f"**{icon}**")
    
    status = health.get("status", "unknown")
    if status == "healthy":
        st.success(f"✅ {status}")
    else:
        st.error(f"❌ {status}")
        
    bus_type = health.get("bus_type", "?")
    bus_root = health.get("bus_root", "?")
    if len(bus_root) > 20:
        bus_root = "..." + bus_root[-17:]
        
    st.text(f"bus: {bus_type} | {bus_root}")


def _format_ts(ts) -> str:
    """Format timestamp for display."""
    if isinstance(ts, int):
        from datetime import datetime
        try:
            return datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        except:
            return str(ts)
    return str(ts)


def _get_cloud_paused(bus) -> bool:
    """Check if cloud runtime is paused."""
    try:
        gr = bus.get_json("cloud_runtime/global_risk.json")
        if gr:
            return gr.get("paused", False)
    except:
        pass
    return False


def _count_active_strategies(bus) -> int:
    """Count active strategies in registry."""
    try:
        items = bus.list("cloud_registry/strategies")
        return len([i for i in items if not i.endswith(".ndjson")])
    except:
        return 0


def _merge_all_events(bus, n: int) -> list:
    """Merge events from all streams, sorted by ts."""
    all_events = []
    
    for stream in ["mac", "matrix", "cloud"]:
        events = bus.tail_events(stream, n)
        for e in events:
            e["_stream"] = stream
        all_events.extend(events)
        
    # Sort by ts (newest first)
    all_events.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return all_events[:n]


def _get_alerts(bus) -> list:
    """Get active alerts from events."""
    events = _merge_all_events(bus, 50)
    alerts = []
    
    for e in events:
        kind = e.get("kind", "")
        if "FAIL" in kind or "BLOCK" in kind or "GAP" in kind or "KILL" in kind:
            severity = "CRIT" if "BLOCK" in kind or "KILL" in kind else "WARN"
            alerts.append({
                "severity": severity,
                "message": f"{e.get('_stream', '?')}: {kind}",
                "ts": e.get("ts"),
            })
            
    return alerts[:10]  # Top 10


def _ack_all_alerts(bus):
    """Acknowledge all alerts (write to bus)."""
    import time
    bus.put_json("artifacts/panel/acks.json", {
        "acked_at": int(time.time()),
        "count": 0,
    })


# ============================================================================
# MAIN TAB INTEGRATION
# ============================================================================

def render_platform_tab():
    """Main entry point for Platform tab in Streamlit."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏗️ Platform")
    
    page = st.sidebar.radio(
        "Platform Sayfa",
        ["Connectors", "Jobs", "Ops", "Golden", "Candidate→Sniper", "Approved→Deploy"],
        label_visibility="collapsed"
    )
    
    if page == "Connectors":
        render_platform_connectors()
    elif page == "Jobs":
        render_platform_jobs()
    elif page == "Ops":
        render_platform_ops()
    elif page == "Golden":
        from tezaver.ui.platform_golden_tab import render_platform_golden
        render_platform_golden()
    elif page == "Candidate→Sniper":
        from tezaver.ui.platform_sniper_tab import render_platform_sniper
        render_platform_sniper()
    elif page == "Approved→Deploy":
        from tezaver.ui.platform_deploy_tab import render_platform_deploy
        render_platform_deploy()
