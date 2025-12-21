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
# ERROR CODES TR DICT (MX-25001)
# ============================================================================

ERROR_CODES_TR = {
    "OK": "✅ Bağlantı başarılı",
    "AUTH_FAIL": "❌ Token hatalı veya yetkisiz",
    "TIMEOUT": "❌ Servis yanıt vermedi (zaman aşımı)",
    "CONN_REFUSED": "❌ Servise bağlanılamadı (port kapalı)",
    "BAD_URL": "❌ URL hatalı",
    "UNKNOWN": "❌ Bilinmeyen hata",
}


# ============================================================================
# HTTP CLIENT HELPER (MX-25002)
# ============================================================================

def request_with_timeout(
    url: str,
    token: str = "",
    method: str = "GET",
    timeout_s: float = 3.0,
    retries: int = 2,
    backoff: float = 0.2,
) -> Dict[str, Any]:
    """
    HTTP request with timeout and retry.
    TR: Zaman aşımı ve tekrar deneme destekli HTTP istek.
    
    Returns: {"ok": bool, "data": dict, "error_code": str}
    """
    import time
    from urllib.error import URLError, HTTPError
    
    last_error = "UNKNOWN"
    
    for attempt in range(retries + 1):
        try:
            req = Request(url, method=method)
            if token:
                req.add_header("Authorization", f"Bearer {token}")
                
            with urlopen(req, timeout=timeout_s) as resp:
                data = json.loads(resp.read().decode())
                return {"ok": True, "data": data, "error_code": "OK"}
                
        except HTTPError as e:
            if e.code == 401 or e.code == 403:
                return {"ok": False, "data": None, "error_code": "AUTH_FAIL"}
            last_error = f"HTTP_{e.code}"
        except URLError as e:
            reason = str(e.reason).lower()
            if "connection refused" in reason:
                last_error = "CONN_REFUSED"
            elif "timed out" in reason or "timeout" in reason:
                last_error = "TIMEOUT"
            else:
                last_error = "BAD_URL"
        except Exception as e:
            if "timed out" in str(e).lower():
                last_error = "TIMEOUT"
            else:
                last_error = "UNKNOWN"
                
        if attempt < retries:
            time.sleep(backoff * (attempt + 1))
            
    return {"ok": False, "data": None, "error_code": last_error}


# ============================================================================
# CONNECTORS PAGE (MX-25001: Token Safety)
# ============================================================================

def render_platform_connectors():
    """Render Platform Connectors page with token safety."""
    st.header("🔌 Platform Connectors")
    
    st.info("""
    Bu sayfada Mac, Matrix ve Cloud agent'larının bağlantı ayarlarını yapabilirsiniz.
    Token alanları güvenlik için gizlidir. "Göster" ile anlık görüntüleyebilirsiniz.
    """)
    
    # Connector settings
    st.subheader("⚙️ Agent Bağlantı Ayarları")
    
    agents = [
        ("🍎 Mac Agent", "mac", "http://127.0.0.1:9001"),
        ("🎛️ Matrix Agent", "matrix", "http://127.0.0.1:9002"),
        ("☁️ Cloud Agent", "cloud", "http://127.0.0.1:9003"),
    ]
    
    col1, col2, col3 = st.columns(3)
    
    for col, (label, name, default_url) in zip([col1, col2, col3], agents):
        with col:
            _render_agent_connector(label, name, default_url)
            
    st.divider()
    
    # Bus settings
    st.subheader("📦 Bus Ayarları")
    
    bus_root = st.text_input(
        "Bus Root Path (FS veya S3)",
        ".tezaver_bus",
        key="bus_root",
        help="FS: '.tezaver_bus' veya S3: 's3://bucket/prefix'"
    )
    st.session_state["platform_bus_root"] = bus_root
    
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📁 Bus Root Oluştur", help="Veri yolu (Bus) için gerekli klasör yapısını disk üzerinde hazırlar."):
            if not bus_root.startswith("s3://"):
                os.makedirs(bus_root, exist_ok=True)
                st.success(f"✅ Bus root oluşturuldu: {bus_root}")
            else:
                st.info("S3 bucket zaten mevcut olmalı")
    with col_b:
        if bus_root.startswith("s3://"):
            st.info("🪣 S3 Mode")
        else:
            st.info("📁 FS Mode")


def _render_agent_connector(label: str, name: str, default_url: str):
    """Render single agent connector card."""
    st.markdown(f"### {label}")
    
    url_key = f"{name}_url"
    token_key = f"{name}_token"
    show_key = f"{name}_show_token"
    
    # Initialize session state if not exists (before widget creation)
    if url_key not in st.session_state:
        st.session_state[url_key] = default_url
    if token_key not in st.session_state:
        st.session_state[token_key] = ""
    
    # URL - uses session state via key
    url = st.text_input("Base URL", key=url_key)
    
    # Token with mask toggle
    show_token = st.checkbox("🔓 Token göster", key=show_key, value=False)
    token_type = "default" if show_token else "password"
    token = st.text_input(
        "Token (Gizli anahtar)",
        type=token_type,
        key=token_key,
        help="Agent için güvenlik tokeni. Loglama YASAK."
    )
    
    # Test Connection - uses session state values
    if st.button(f"🔌 Bağlantıyı Test Et", key=f"test_{name}", help="Seçili Agent URL'sine health check isteği göndererek bağlantıyı doğrular."):
        _test_agent_connection(st.session_state[url_key], st.session_state[token_key])


def _test_agent_connection(base_url: str, token: str):
    """Test agent connection with detailed error."""
    result = request_with_timeout(f"{base_url}/health", token, timeout_s=3.0, retries=1)
    
    if result["ok"]:
        data = result["data"]
        agent_name = data.get("agent", "?")
        bus_type = data.get("bus_type", "?")
        api_version = data.get("api_version", "?")
        st.success(f"✅ Bağlı: {agent_name} | bus:{bus_type} | api:v{api_version}")
    else:
        error_code = result["error_code"]
        tr_msg = ERROR_CODES_TR.get(error_code, ERROR_CODES_TR["UNKNOWN"])
        st.error(f"{tr_msg} ({error_code})")


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
        
        if st.button("Create Job", help="Yeni bir işi (Build, Import, Sniper vb.) kuyruğa ekler."):
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
    
    # Version Banner (MX-26001)
    from tezaver.version import __version__, build_commit
    st.caption(f"🏷️ Tezaver v{__version__} | Commit: {build_commit()} | TR: Sürüm bilgisi")
    
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
            if st.button("✓ Acknowledge All", help="Tüm aktif alarmları okundu olarak işaretler."):
                _ack_all_alerts(bus)
                st.success("Alerts acknowledged")
        else:
            st.info("No active alerts")
            
    # -------------------------------------------------------------------------
    # 4.5 Backup Button (MX-25004)
    # -------------------------------------------------------------------------
    with st.expander("📦 Backup / Export", expanded=False):
        st.caption("TR: Tek tuşla sistem fotoğrafı al - inceleme ve ispat paketi")
        
        if st.button("📦 Backup Al", type="primary", help="Sistemin anlık dosya ve veri durumunu yedekler (Zip/Manifest)."):
            import time
            ts = int(time.time())
            
            if bus_root.startswith("s3://"):
                out_path = f"backups/BACKUP_{ts}.manifest.json"
            else:
                out_path = f"backups/BACKUP_{ts}.zip"
                
            from tezaver.platform.cli.bus_backup_cli import run_backup
            result = run_backup(bus_root, out_path)
            
            if result["ok"]:
                st.success(f"✅ Yedek alındı: {result['output_path']}")
                st.text(f"Dosya sayısı: {result.get('files_count') or result.get('keys_count')}")
            else:
                st.error(f"❌ Hata: {result.get('error')}")
            
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
        
    st.divider()
    
    # -------------------------------------------------------------------------
    # 6. Smoke Reports Viewer (MX-26001)
    # -------------------------------------------------------------------------
    with st.expander("🧪 Smoke Reports", expanded=False):
        st.caption("TR: Duman testi raporları - tezaver-smoke CLI ile oluşturulur")
        
        smoke_reports = _list_smoke_reports()
        
        if smoke_reports:
            for report_path in smoke_reports[:5]:
                report = _load_smoke_report(report_path)
                if report:
                    overall = report.get("overall", "?")
                    version = report.get("tezaver_version", "?")
                    ts = report.get("smoke_ts", "?")
                    
                    icon = "✅" if overall == "PASS" else "❌"
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.markdown(f"{icon} **{overall}** | v{version} | ts:{ts}")
                    with col_b:
                        if st.button("📋", key=f"show_{ts}"):
                            st.json(report)
        else:
            st.info("Henüz smoke raporu yok. tezaver-smoke kullanın.")


def _fetch_agent_health(url: str) -> Dict:
    """Fetch agent health."""
    try:
        req = Request(f"{url}/health")
        with urlopen(req, timeout=2) as resp:
            return json.loads(resp.read().decode())
    except:
        return {"status": "unhealthy", "error": "Connection failed"}


def _render_health_card(icon: str, health: Dict, url: str):
    """Render single health card with version colors."""
    st.markdown(f"**{icon}**")
    
    status = health.get("status", "unknown")
    if status == "healthy":
        st.success(f"✅ {status}")
    else:
        st.error(f"❌ {status}")
        
    # Version compatibility colors (MX-25003)
    api_version = health.get("api_version", "?")
    platform_version = health.get("platform_version", "?")
    
    expected_api = "1"
    if api_version == expected_api:
        version_color = "green"
        version_status = "uyumlu"
    elif api_version == "?":
        version_color = "orange"
        version_status = "bilinmiyor"
    else:
        version_color = "red"
        version_status = "UYUMSUZ"
        
    st.markdown(f"API: :{version_color}[v{api_version}] ({version_status})")
    
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


def _list_smoke_reports() -> list:
    """List smoke reports from smoke_reports directory."""
    import glob
    reports = glob.glob("smoke_reports/SMOKE_*.json")
    # Sort by timestamp in filename (newest first)
    reports.sort(reverse=True)
    return reports


def _load_smoke_report(path: str) -> dict:
    """Load smoke report from file."""
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return None


# ============================================================================
# MAIN TAB INTEGRATION
# ============================================================================


# ============================================================================
# MAIN TAB INTEGRATION — HARDENED (NAV v1.0 Style)
# ============================================================================

PLATFORM_PAGES = [
    ("Connectors", "🔌 Connectors", "Agent'ların bağlantı ve token ayarları."),
    ("Jobs", "📋 Jobs", "İş kuyruğu yönetimi ve durum takibi."),
    ("Ops", "📊 Ops Dashboard", "Sistem sağlığı, SLO metrikleri ve yedekleme merkezi."),
    ("Golden", "🏆 Golden", "Onaylanmış strateji paketleri (Orijinal adaylar)."),
    ("Candidate→Sniper", "🎯 Sniper Export", "Adayları test için Sniper moduna aktarır."),
    ("Approved→Deploy", "🚀 Deploy", "Onaylı stratejileri canlıya (Loop) taşır."),
]

def render_platform_tab():
    """Main entry point for Platform tab in Streamlit."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏗️ Platform Menü")
    
    # Initialize state
    if "platform_selected_page" not in st.session_state:
        st.session_state["platform_selected_page"] = "Connectors"
    
    # Render Sidebar Buttons
    for page_key, label, help_text in PLATFORM_PAGES:
        is_active = st.session_state["platform_selected_page"] == page_key
        btn_type = "primary" if is_active else "secondary"
        
        if st.sidebar.button(label, key=f"plat_nav_{page_key}", use_container_width=True, type=btn_type, help=help_text):
            st.session_state["platform_selected_page"] = page_key
            st.rerun()
    
    page = st.session_state["platform_selected_page"]
    
    st.caption(f"📍 Konum: **Platform** > {page}")
    st.divider()
    
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
