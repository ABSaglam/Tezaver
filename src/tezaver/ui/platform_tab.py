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
# OPS PAGE
# ============================================================================

def render_platform_ops():
    """Render Platform Ops page."""
    st.header("📊 Platform Ops")
    
    bus_root = st.session_state.get("platform_bus_root", ".tezaver_bus")
    
    # Agent health status
    st.subheader("🏥 Agent Durumları")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**🍎 Mac Agent**")
        _show_agent_status("http://localhost:9001")
        
    with col2:
        st.markdown("**🎛️ Matrix Agent**")
        _show_agent_status("http://localhost:9002")
        
    with col3:
        st.markdown("**☁️ Cloud Agent**")
        _show_agent_status("http://localhost:9003")
        
    st.divider()
    
    # Events tail
    st.subheader("📜 Events (Son 30)")
    
    bus = FsBusAdapter(bus_root)
    
    for agent in ["mac", "matrix", "cloud"]:
        events_path = f"events/{agent}.ndjson"
        full_path = os.path.join(bus_root, events_path)
        
        if os.path.exists(full_path):
            with open(full_path) as f:
                lines = f.readlines()[-10:]
            
            if lines:
                st.markdown(f"**{agent.upper()} Events:**")
                for line in reversed(lines):
                    try:
                        e = json.loads(line)
                        st.text(f"{e.get('ts', '')} | {e.get('kind', '')} | {e.get('job_id', '')}")
                    except:
                        pass


def _show_agent_status(base_url: str):
    """Show agent health status."""
    try:
        req = Request(f"{base_url}/health")
        with urlopen(req, timeout=1) as resp:
            data = json.loads(resp.read().decode())
            st.success(f"✅ {data.get('status', 'ok')}")
    except:
        st.error("❌ Bağlantı yok")


# ============================================================================
# MAIN TAB INTEGRATION
# ============================================================================

def render_platform_tab():
    """Main entry point for Platform tab in Streamlit."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏗️ Platform")
    
    page = st.sidebar.radio(
        "Platform Sayfa",
        ["Connectors", "Jobs", "Ops"],
        label_visibility="collapsed"
    )
    
    if page == "Connectors":
        render_platform_connectors()
    elif page == "Jobs":
        render_platform_jobs()
    elif page == "Ops":
        render_platform_ops()
