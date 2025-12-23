"""
Matrix V4 Tab - Streamlit Integration for Matrix V4

This module provides the main Matrix V4 UI in Streamlit.
Does NOT import panel_server or legacy matrix modules.
"""

import streamlit as st
import os
import json
import pandas as pd
from pathlib import Path
from tezaver.ui.matrix_v4_context import build_matrix_v4_context

# ============================================================================
# NAVIGATION v1.0 HARDENED — Alt Başlıklar Türkçe + FIX-1/2/3
# ============================================================================

# Main headings for sidebar (9 items) — ORIGINAL LABELS (değişmedi)
# Each item: (key, label, help_text)
MAIN_HEADINGS = [
    ("DASHBOARD", "📊 Dashboard", "Genel sistem durumu, alarmlar ve yayın kontrolleri."),
    ("CANDIDATES", "📋 Candidates", "Strateji adaylarını inceleme ve onay merkezi."),
    ("SNIPER", "🎯 Sniper", "Tekil strateji testleri ve geçmişi."),
    ("WAR", "⚔️ WAR", "Çoklu coin toplu backtest ve risk analizi."),
    ("LIVE", "🟢 LIVE", "Canlı piyasa provası ve simülasyonu."),
    ("EVIDENCE", "🧾 Evidence", "Koşu geçmişi, raporlar ve olay kayıtları."),
    ("OPS", "🛠️ Ops", "Bakım, temizlik ve veri taşıma araçları."),
    ("PLATFORM", "🏗️ Platform", "Registry ve altyapı yönetim paneli."),
    ("CLOUD_LOCKED", "☁️ Cloud 🔒", "Bulut çalışma zamanı ve döngü yönetimi (Yakında)."),
]

# NAV_MAP: Sub-headings per main heading
# Each item: (label_tr, route_key, filter_mode, disabled, help_text)
# filter_mode: None for non-RUNS, "SNIPER"/"WAR"/"LIVE" for filtered RUNS
# disabled: True for CLOUD_LOCKED items
# help_text: Tooltip açıklaması
NAV_MAP = {
    "DASHBOARD": [
        ("Sistem Durumu", "OPS", None, False, "Sistem sağlığı, SLO durumu ve timeline görüntüler."),
        ("Alarmlar", "ALERTS", None, False, "Aktif alarmları listeler ve onaylama (ack) imkanı sağlar."),
        ("Panel Sağlığı", "PANEL_HEALTH", None, False, "Bundle keşfi, import durumu ve hata raporlarını gösterir."),
        ("Yayın Kapısı", "RELEASE", None, False, "Candidate'ın yayına hazır olup olmadığını değerlendirir."),
        ("Prova (Go/No-Go)", "REHEARSAL", None, False, "Canlıya geçiş öncesi kontrol listesi ve Go/No-Go kararı."),
    ],
    "CANDIDATES": [
        ("Adaylar", "CANDIDATES", None, False, "Strateji adaylarını listeler, onaylar veya reddeder."),
    ],
    "SNIPER": [
        ("Sniper", "SNIPER", None, False, "Sniper tekli backtest geçmişi ve sonuçları."),
        ("Koşular (Sniper)", "RUNS", "SNIPER", False, "Sadece Sniper modundaki koşuları filtreler."),
    ],
    "WAR": [
        ("WAR", "WAR", None, False, "Çoklu-coin toplu backtest paneli. Yeni WAR run başlatır."),
        ("Koşular (WAR)", "RUNS", "WAR", False, "Sadece WAR modundaki koşuları filtreler."),
    ],
    "LIVE": [
        ("LIVE", "LIVE", None, False, "Canlı prova modu. Bar-bar simülasyon yapar."),
        ("Koşular (LIVE)", "RUNS", "LIVE", False, "Sadece LIVE modundaki koşuları filtreler."),
    ],
    "EVIDENCE": [
        ("Koşular (Tümü)", "RUNS", None, False, "Tüm modlardaki koşu geçmişini gösterir."),
        ("Raporlar", "REPORTS", None, False, "WAR, LIVE ve Cloud run raporlarını özetler."),
        ("Olaylar (Kanıt Paketleri)", "INCIDENTS", None, False, "Block, exception ve data gap olaylarını listeler."),
        ("📦 Bundles", "BUNDLES", None, False, "ApprovedRallyBundle paketlerini listeler."),
    ],
    "OPS": [
        ("Bakım", "MAINTENANCE", None, False, "Cache temizleme, legacy cleanup ve registry rebuild araçları."),
        ("Taşıma", "MIGRATION", None, False, "Veri taşıma raporlarını gösterir."),
    ],
    "PLATFORM": [
        ("Kayıt Defteri", "REGISTRY", None, False, "Cloud'a kayıtlı stratejileri listeler."),
        ("Platform", "PLATFORM", None, False, "Connector, Job ve Ops yönetim paneli."),
    ],
    "CLOUD_LOCKED": [
        ("Bulut Çalışma Zamanı (Kilitli)", "CLOUD_RUNTIME", None, True, "🔒 Matrix v1.0 FINAL sonrası aktif olacak."),
        ("Kullanıcı Akışı (Kilitli)", "USERSTREAM", None, True, "🔒 Matrix v1.0 FINAL sonrası aktif olacak."),
        ("Bulut Döngüsü (Kilitli)", "LOOP", None, True, "🔒 Matrix v1.0 FINAL sonrası aktif olacak."),
    ],
}

# Legacy alias for backward compatibility
SUB_HEADINGS = {k: [(item[0], item[1], item[2]) for item in v] for k, v in NAV_MAP.items()}


# Legacy categories (for backward compatibility)
CATEGORIES = [
    ("OPS", "🏠 Operasyon", "Sistem sağlığı ve SLO"),
    ("ALERTS", "🔔 Alarmlar", "Aktif alarmlar ve bildirimler"),
    ("CLOUD_RUNTIME", "☁️ Cloud Runtime", "Strateji durumu ve kontrol"),
    ("USERSTREAM", "📡 UserStream", "Binance UserStream yönetimi"),
    ("LOOP", "🔁 Cloud Loop", "Full-cycle döngü yönetimi"),
    ("MIGRATION", "📦 Migration", "Veri taşıma raporları"),
    ("RELEASE", "🚀 Release Gate", "Yayın kontrolü"),
    ("REHEARSAL", "✅ Rehearsal", "Go/No-Go kontrol listesi"),
    ("CANDIDATES", "📋 Candidates", "Strateji adayları"),
    ("SNIPER", "🎯 Sniper", "Sniper run geçmişi"),
    ("RUNS", "▶️ Runs", "Çalıştırma geçmişi"),
    ("WAR", "⚔️ WAR", "Multi-coin backtest"),
    ("LIVE", "🟢 LIVE", "Canlı trading modu"),
    ("REPORTS", "🧾 Reports", "Raporlar ve özet"),
    ("INCIDENTS", "🚨 Incidents", "Kanıt paketleri"),
    ("PANEL_HEALTH", "🏥 Panel Health", "Bundle ve registry sağlık durumu"),
    ("MAINTENANCE", "🔧 Maintenance", "Bakım ve temizlik araçları"),
    ("REGISTRY", "📚 Registry", "Cloud strateji kaydı"),
    ("PLATFORM", "🏗️ Platform", "Connectors, Jobs, Ops"),
]


def render_matrix_v4():
    """
    Main entry point for Matrix V4 Streamlit UI.
    Navigation v1.0 HARDENED: Türkçe labels, FIX-1/2/3, breadcrumb.
    """
    # Default home path
    home = st.session_state.get("matrix_home", ".tezaver_matrix")
    st.session_state["matrix_home"] = home
    
    # Build context
    ctx = build_matrix_v4_context(home)
    counts = ctx["counts"]
    
    # ===== INITIALIZE STATE =====
    if "active_main" not in st.session_state:
        st.session_state["active_main"] = "DASHBOARD"
    if "selected_route_key" not in st.session_state:
        st.session_state["selected_route_key"] = "OPS"
    if "selected_filter_mode" not in st.session_state:
        st.session_state["selected_filter_mode"] = None
    if "last_sub_index_by_main" not in st.session_state:
        st.session_state["last_sub_index_by_main"] = {}
    
    # Helper: Get main heading label
    def get_main_label(main_key: str) -> str:
        for k, label, help in MAIN_HEADINGS:
            if k == main_key:
                return label
        return main_key
    
    # Helper: Get sub item by index with bounds check (FIX-3)
    def get_sub_item_safe(main_key: str, idx: int):
        items = NAV_MAP.get(main_key, [])
        if not items:
            return None
        if idx < 0 or idx >= len(items):
            idx = 0
            st.session_state["last_sub_index_by_main"][main_key] = 0
        return items[idx]
    
    # Helper: Get current sub label for breadcrumb
    def get_current_sub_label() -> str:
        active_main = st.session_state["active_main"]
        items = NAV_MAP.get(active_main, [])
        route_key = st.session_state["selected_route_key"]
        filter_mode = st.session_state["selected_filter_mode"]
        
        for item in items:
            # item: (label_tr, route_key, filter_mode, disabled, help_text)
            if item[1] == route_key and item[2] == filter_mode:
                return item[0]
        return "(Seçim yok)"
    
    # ===== SIDEBAR: 9 Main Headings =====
    for item in MAIN_HEADINGS:
        main_key = item[0]
        main_label = item[1]
        help_text = item[2] if len(item) > 2 else None
        
        is_active = st.session_state["active_main"] == main_key
        btn_type = "primary" if is_active else "secondary"
        
        if st.sidebar.button(main_label, key=f"main_{main_key}", use_container_width=True, type=btn_type, help=help_text):
            st.session_state["active_main"] = main_key
            
            # FIX-3: Bounds check for last_sub_index
            items = NAV_MAP.get(main_key, [])
            if items:
                last_idx = st.session_state["last_sub_index_by_main"].get(main_key, 0)
                if last_idx < 0 or last_idx >= len(items):
                    last_idx = 0
                    st.session_state["last_sub_index_by_main"][main_key] = 0
                
                sub = items[last_idx]
                # FIX-2: Cloud LOCKED items should not change state
                if not sub[3]:  # disabled flag
                    st.session_state["selected_route_key"] = sub[1]
                    # FIX-1: filter_mode only for RUNS
                    if sub[1] == "RUNS":
                        st.session_state["selected_filter_mode"] = sub[2]
                    else:
                        st.session_state["selected_filter_mode"] = None
            st.rerun()
    
    # ===== MAIN CONTENT =====
    
    # Top Banner (compact)
    st.markdown(f"""
    <div style="background:#222; color:#aaa; padding:6px 12px; font-family:monospace; margin-bottom:10px; border-radius:4px; font-size:10px;">
        <b>Build:</b> {ctx['commit'][:8]} | <b>Branch:</b> {ctx['branch']} | 
        candidates={counts['candidates']} runs={counts['runs']} approved={counts['approved']}
    </div>
    """, unsafe_allow_html=True)
    
    # ===== BREADCRUMB =====
    active_main = st.session_state["active_main"]
    main_label = get_main_label(active_main)
    sub_label = get_current_sub_label()
    st.caption(f"📍 Konum: **{main_label}** > {sub_label}")
    
    # ===== SUB-HEADING BAR (in main content) =====
    items = NAV_MAP.get(active_main, [])
    
    if items:
        # Split into rows of 5 for wrapping
        rows = [items[i:i+5] for i in range(0, len(items), 5)]
        
        for row_idx, row in enumerate(rows):
            cols = st.columns(len(row))
            for col_idx, item in enumerate(row):
                # Unpack item: (label_tr, route_key, filter_mode, disabled, help_text)
                label_tr = item[0]
                route_key = item[1]
                filter_mode = item[2]
                disabled = item[3]
                help_text = item[4] if len(item) > 4 else None
                
                with cols[col_idx]:
                    # Unique key
                    unique_key = f"sub_{active_main}_{row_idx}_{col_idx}"
                    
                    # FIX-2: Cloud LOCKED items are disabled and do NOT change state
                    if disabled:
                        st.button(label_tr, key=unique_key, disabled=True, use_container_width=True, help=help_text)
                    else:
                        is_active = (
                            st.session_state["selected_route_key"] == route_key and 
                            st.session_state["selected_filter_mode"] == filter_mode
                        )
                        btn_type = "primary" if is_active else "secondary"
                        
                        if st.button(label_tr, key=unique_key, use_container_width=True, type=btn_type, help=help_text):
                            st.session_state["selected_route_key"] = route_key
                            # FIX-1: filter_mode only for RUNS
                            if route_key == "RUNS":
                                st.session_state["selected_filter_mode"] = filter_mode
                            else:
                                st.session_state["selected_filter_mode"] = None
                            # Track last selected sub for this main
                            global_idx = row_idx * 5 + col_idx
                            st.session_state["last_sub_index_by_main"][active_main] = global_idx
                            st.rerun()
    
    st.divider()
    
    # ===== ROUTE TO PAGE =====
    route_key = st.session_state.get("selected_route_key", "OPS")
    filter_mode = st.session_state.get("selected_filter_mode")
    
    # FIX-1: Ensure filter_mode is None for non-RUNS routes
    if route_key != "RUNS":
        filter_mode = None
        st.session_state["selected_filter_mode"] = None
    
    # Handle LOCKED routes (should not happen due to FIX-2, but safety check)
    if filter_mode == "LOCKED":
        st.warning("🔒 Bu sayfa Matrix v1.0 FINAL sonrası aktif olacak.")
        return
    
    # Render based on route_key
    if route_key == "OPS":
        render_ops(home)
    elif route_key == "ALERTS":
        render_alerts(home)
    elif route_key == "PANEL_HEALTH":
        render_panel_health(home)
    elif route_key == "RELEASE":
        render_release(home)
    elif route_key == "REHEARSAL":
        render_rehearsal(home)
    elif route_key == "CANDIDATES":
        render_candidates(home)
    elif route_key == "SNIPER":
        render_sniper(home)
    elif route_key == "WAR":
        render_war(home)
    elif route_key == "LIVE":
        render_live(home)
    elif route_key == "RUNS":
        render_runs(home)  # filter_mode can be used inside if needed
    elif route_key == "REPORTS":
        render_reports(home)
    elif route_key == "INCIDENTS":
        render_incidents(home)
    elif route_key == "BUNDLES":
        render_bundles(home)
    elif route_key == "MAINTENANCE":
        render_maintenance(home)
    elif route_key == "MIGRATION":
        render_migration(home)
    elif route_key == "REGISTRY":
        render_registry(home)
    elif route_key == "PLATFORM":
        from tezaver.ui.platform_tab import render_platform_tab
        render_platform_tab()
    elif route_key == "CLOUD_RUNTIME":
        render_cloud_runtime(home)
    elif route_key == "USERSTREAM":
        render_userstream(home)
    elif route_key == "LOOP":
        render_loop(home)
    else:
        st.info(f"Route not found: {route_key}")


# ============================================================================
# CATEGORY RENDERERS
# ============================================================================

def render_ops(home: str):
    """Render Ops category."""
    st.subheader("📊 Sistem Sağlığı")
    
    health_path = os.path.join(home, "ops", "health", "latest.json")
    if os.path.exists(health_path):
        with open(health_path) as f:
            health = json.load(f)
        
        overall = health.get("overall", "UNKNOWN")
        color = "green" if overall == "GREEN" else "orange" if overall == "YELLOW" else "red"
        st.metric("Overall Status", overall)
        st.json(health)
    else:
        st.warning("Henüz ops/health/latest.json yok.")
        
    # Timeline
    st.subheader("📜 Timeline (Son 30)")
    timeline_path = os.path.join(home, "ops", "timeline.ndjson")
    if os.path.exists(timeline_path):
        with open(timeline_path) as f:
            lines = f.readlines()[-30:]
        for line in reversed(lines):
            try:
                e = json.loads(line)
                st.text(f"{e.get('ts', '')} | {e.get('event_type', e.get('kind', ''))} | {e.get('title_tr', '')}")
            except:
                pass
    else:
        st.info("Henüz timeline yok.")

def render_alerts(home: str):
    """Render Alerts category."""
    alerts_dir = os.path.join(home, "alerts", "active")
    
    if not os.path.exists(alerts_dir):
        st.info("Aktif alarm yok.")
        return
        
    alerts = []
    for f in os.listdir(alerts_dir):
        if f.endswith(".json"):
            try:
                with open(os.path.join(alerts_dir, f)) as af:
                    alerts.append(json.load(af))
            except:
                pass
                
    if not alerts:
        st.success("✅ Aktif alarm yok.")
        return
        
    st.warning(f"⚠️ {len(alerts)} aktif alarm")
    
    for a in alerts:
        with st.expander(f"{a.get('level', '?')} | {a.get('type', 'UNKNOWN')} | {a.get('alert_id', '')}"):
            st.json(a)
            if st.button(f"Ack {a.get('alert_id', '')}", key=f"ack_{a.get('alert_id')}"):
                # Ack: move to acked directory
                ack_dir = os.path.join(home, "alerts", "acked")
                os.makedirs(ack_dir, exist_ok=True)
                src_path = os.path.join(alerts_dir, f"{a.get('alert_id')}.json")
                dst_path = os.path.join(ack_dir, f"{a.get('alert_id')}.json")
                if os.path.exists(src_path):
                    os.rename(src_path, dst_path)
                    st.success(f"Acked: {a.get('alert_id')}")
                    st.rerun()

def render_cloud_runtime(home: str):
    """Render Cloud Runtime category."""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 State")
        state_path = os.path.join(home, "cloud_runtime", "state.json")
        if os.path.exists(state_path):
            with open(state_path) as f:
                st.json(json.load(f))
        else:
            st.info("state.json yok")
            
    with col2:
        st.subheader("⚙️ Global Risk")
        gr_path = os.path.join(home, "cloud_runtime", "global_risk.json")
        if os.path.exists(gr_path):
            with open(gr_path) as f:
                gr = json.load(f)
            st.json(gr)
            
            paused = gr.get("paused", False)
            if st.button("Toggle Pause" if not paused else "Resume"):
                gr["paused"] = not paused
                with open(gr_path, "w") as f:
                    json.dump(gr, f, indent=2)
                st.rerun()
        else:
            st.info("global_risk.json yok")
            
    st.divider()
    
    st.subheader("🏃 Tick Once")
    ticks = st.number_input("Ticks", min_value=1, max_value=10, value=1)
    if st.button("Run Tick"):
        try:
            from tezaver.matrix.core.cloud_runtime import cloud_runtime_tick
            cloud_runtime_tick(home, ticks=ticks)
            st.success(f"✅ {ticks} tick executed")
        except Exception as e:
            st.error(f"Error: {e}")

def render_userstream(home: str):
    """Render UserStream category."""
    st.subheader("📡 Status")
    
    status_path = os.path.join(home, "cloud_runtime", "userstream", "status.json")
    if os.path.exists(status_path):
        with open(status_path) as f:
            st.json(json.load(f))
    else:
        st.info("UserStream status yok")
        
    st.subheader("📜 Raw Events (Last 20)")
    raw_path = os.path.join(home, "cloud_runtime", "userstream", "raw.ndjson")
    if os.path.exists(raw_path):
        with open(raw_path) as f:
            lines = f.readlines()[-20:]
        for line in reversed(lines):
            st.text(line.strip()[:100])
    else:
        st.info("raw.ndjson yok")

def render_loop(home: str):
    """Render Cloud Loop category."""
    st.subheader("🔁 Loop State")
    
    state_path = os.path.join(home, "cloud_loop", "state.json")
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)
        st.json(state)
    else:
        st.info("cloud_loop/state.json yok")
        
    st.subheader("📜 History (Last 20)")
    hist_path = os.path.join(home, "cloud_loop", "history.ndjson")
    if os.path.exists(hist_path):
        with open(hist_path) as f:
            lines = f.readlines()[-20:]
        for line in reversed(lines):
            try:
                e = json.loads(line)
                st.text(f"{e.get('ts', '')} | {e.get('event_type', e.get('kind', ''))}")
            except:
                pass
    else:
        st.info("history.ndjson yok")
        
    st.divider()
    
    ticks = st.number_input("Loop Ticks", min_value=1, max_value=10, value=3, key="loop_ticks")
    if st.button("Run Loop Once", help="Cloud Loop'u bir cycle için manuel olarak çalıştırır."):
        try:
            from tezaver.matrix.core.cloud_loop import CloudLoopSupervisor
            sup = CloudLoopSupervisor(home)
            res = sup.run_loop(ticks=ticks, steps=1, userstream_recv=1, hours=24)
            st.success(f"✅ Loop completed: {res}")
        except Exception as e:
            st.error(f"Error: {e}")

def render_migration(home: str):
    """Render Migration category."""
    st.subheader("📦 Latest Migration Report")
    
    mig_path = os.path.join(home, "ops", "migration", "latest.json")
    if os.path.exists(mig_path):
        with open(mig_path) as f:
            st.json(json.load(f))
    else:
        st.info("ops/migration/latest.json yok")

def render_release(home: str):
    """Render Release Gate category."""
    st.subheader("🚀 Release Gate Evaluation")
    
    # MX-5260: Safety Check
    from tezaver.matrix.protocols.safety_registry import SafetyProtocolRegistry, SafetyStatus
    try:
        registry = SafetyProtocolRegistry()
        red_protocols = [p for p in registry.protocols if registry.get_overall_for_active(p["mx"]) == SafetyStatus.RED]
        
        if red_protocols:
            st.error("⚠️ CRITICAL: RED Safety Protocols detected. Release Gate is LOCKED.")
            for p in red_protocols:
                st.write(f"- **{p['mx']}**: {p['name']} (Status: RED)")
            st.divider()
    except Exception as e:
        st.warning(f"Safety Registry check skipped: {e}")

    candidate_id = st.text_input("Candidate ID", key="release_cid")
    
    if st.button("Evaluate", help="Seçili aday için yayın kriterlerini (quality, risk, profit) otomatik denetler."):
        if not candidate_id:
            st.warning("Candidate ID gerekli")
        else:
            try:
                from tezaver.matrix.core.release_gate import evaluate_release_gate
                result = evaluate_release_gate(home, candidate_id)
                
                # MX-5260: Override outcome if RED protocols exist
                try:
                    registry = SafetyProtocolRegistry()
                    red_protocols = [p for p in registry.protocols if registry.get_overall_for_active(p["mx"]) == SafetyStatus.RED]
                    if red_protocols:
                        result["ok"] = False
                        result["summary"] = f"BLOCKED by {len(red_protocols)} RED Safety Protocols"
                except: pass

                ok = result.get("ok", False)
                if ok:
                    st.success(f"✅ PASS: {result.get('summary', '')}")
                else:
                    st.error(f"❌ FAIL: {result.get('summary', '')}")
                    # MX-5110: Detail DATA_OK failures
                    for check in result.get("checks", []):
                        if check.get("code") == "DATA_OK" and check.get("status") == "FAIL":
                            st.warning(f"⚠️ DATA_OK FAIL: {check.get('detail', 'Unknown reason')}")
                    
                st.json(result)

                # MX-5190: Release Report Preview
                run_dir = Path(home) / "out" / "matrix_runs" / "war" # Simplified for preview
                # Actually, we should probably look for reports/release_report_v1.json
                # But evaluate_release_gate already gives the latest state.
                # Let's show the report if a run exists for this cid.
                latest_report = None
                runs_folder = Path(home) / "out" / "matrix_runs" / "war"
                if runs_folder.exists():
                    for d in sorted(runs_folder.iterdir(), key=os.path.getmtime, reverse=True):
                        rep_path = d / "reports" / "release_report_v1.json"
                        if rep_path.exists():
                            with open(rep_path) as f:
                                r_data = json.load(f)
                                if r_data.get("run_id") == d.name: # Simple match
                                    latest_report = r_data
                                    break
                
                if latest_report:
                    st.divider()
                    st.subheader("📄 Latest Release Report (Run-scoped)")
                    st.json(latest_report)

                # MX-5270: Safety Certificate Preview
                latest_cert = None
                if runs_folder.exists():
                    for d in sorted(runs_folder.iterdir(), key=os.path.getmtime, reverse=True):
                        cert_path = d / "reports" / "safety_certificate_v1.json"
                        if cert_path.exists():
                            with open(cert_path) as f:
                                latest_cert = json.load(f)
                                latest_cert["_run_id"] = d.name
                                break
                
                if latest_cert:
                    st.divider()
                    st.subheader("🧾 Latest Safety Certificate (Run-scoped)")
                    cert_res = latest_cert.get("results", {})
                    verdict = cert_res.get("verdict", "UNKNOWN")
                    blockers = cert_res.get("blockers", [])
                    warnings = cert_res.get("warnings", [])
                    
                    if verdict == "PASS":
                        st.success(f"✅ SAFETY: ALL GREEN (stage={cert_res.get('active_stage', 'N/A')})")
                    else:
                        st.error(f"❌ SAFETY: BLOCKED ({len(blockers)} blockers)")
                        for b in blockers:
                            st.write(f"- **{b['mx']}**: {b['name']} ({b['reason']})")
                    
                    if warnings:
                        with st.expander(f"⚠️ {len(warnings)} Warnings"):
                            for w in warnings:
                                st.write(f"- **{w['mx']}**: {w['name']}")


            except Exception as e:
                st.error(f"Error: {e}")


def render_rehearsal(home: str):
    """Render Rehearsal category."""
    st.subheader("✅ Rehearsal Checklist")
    
    # Show latest
    rep_path = os.path.join(home, "ops", "rehearsal", "latest.json")
    if os.path.exists(rep_path):
        with open(rep_path) as f:
            rep = json.load(f)
            
        go = rep.get("go", False)
        if go:
            st.success(f"✅ GO: {rep.get('summary', '')}")
        else:
            st.error(f"❌ NO-GO: {rep.get('summary', '')}")
            
        for c in rep.get("checks", []):
            icon = "✅" if c["status"] == "PASS" else "❌"
            st.text(f"{icon} {c['code']}: {c['name']} - {c['detail']}")
    else:
        st.info("Henüz rehearsal yapılmamış")
        
    st.divider()
    
    candidate_id = st.text_input("Candidate ID (optional)", key="rehearsal_cid")
    if st.button("Run Rehearsal", help="Canlıya geçiş öncesi Go/No-Go provasını başlatır."):
        try:
            from tezaver.matrix.core.rehearsal import run_rehearsal, write_latest
            result = run_rehearsal(home, candidate_id if candidate_id else None)
            write_latest(home, result)
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

def render_candidates(home: str):
    """
    MXI-1030: Render Candidates category with detailed table and story view.
    MXI-1040: Sniper Run integration.
    MXI-1500: UI Guard with panel_health diagnostics.
    """
    try:
        _render_candidates_inner(home)
    except Exception as e:
        st.error(f"⚠️ Panel Render Hatası: {e}")
        st.exception(e)
        # Show panel health summary
        try:
            from tezaver.matrix.apps.panel_health import run_health_check
            health = run_health_check()
            st.warning(f"Discovered: {health['discovered_count']}, OK: {health['imported_count']}, Failed: {health['failed_count']}")
            if health['errors']:
                for err in health['errors'][:3]:
                    st.caption(f"❌ {err.get('path')}: {err.get('error')}")
        except:
            pass

def _render_candidates_inner(home: str):
    """Inner implementation of render_candidates."""
    from tezaver.matrix.adapters.bundle_source_local import LocalBundleSource
    from tezaver.matrix.adapters.candidate_registry import CandidateRegistry
    
    # Debug Header (MXI-1500)
    candidates_root = os.environ.get("MATRIX_CANDIDATES_ROOT", "out/matrix_candidates")
    with st.expander("🔧 Debug: Config", expanded=False):
        st.caption(f"Candidates Root: `{candidates_root}`")
        st.caption(f"CWD: `{os.getcwd()}`")
    
    source = LocalBundleSource(base_path=candidates_root)
    registry = CandidateRegistry() # Default path data/matrix/candidates_registry.jsonl
    
    st.subheader("📋 Strategy Candidates (Adaylar)")
    
    # --- Actions bar ---
    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("🔄 Local Tara & Import", use_container_width=True, help="Disk üzerindeki 'out/matrix_candidates' klasörünü tarar ve yeni adayları sisteme kaydeder."):
            from tezaver.matrix.adapters.bundle_source_local import UnsupportedBundleVersion
            import hashlib
            
            bundles = source.discover_bundles()
            imported_count = 0
            failed_count = 0
            
            for bdir in bundles:
                try:
                    manifest, _ = source.load_bundle(bdir)
                    from tezaver.matrix.core.candidate_v1 import generate_candidate_id
                    cid = generate_candidate_id(manifest)
                    # PNL-1110: Use bundle_id as primary key
                    registry.upsert(
                        bundle_id=manifest.bundle_id,
                        symbol=manifest.symbol,
                        tf=manifest.tf,
                        bundle_path=str(bdir),
                        metrics={
                            "trigger_resolve_rate": manifest.metrics.trigger_resolve_rate,
                            "join_coverage": manifest.metrics.join_coverage
                        },
                        candidate_id=cid,
                        fingerprints={
                            "data_fingerprint": manifest.fingerprints.data_fingerprint,
                            "config_signature": manifest.fingerprints.config_signature
                        }
                    )
                    imported_count += 1
                    
                except UnsupportedBundleVersion as e:
                    # MXI-3.1: Register legacy bundle as FAILED_IMPORT
                    legacy_bundle_id = f"legacy_{hashlib.md5(str(bdir).encode()).hexdigest()[:12]}"
                    registry.register(
                        bundle_id=legacy_bundle_id,
                        symbol="UNKNOWN",
                        tf="UNKNOWN",
                        bundle_path=str(bdir),
                        metrics={},
                        status="FAILED_IMPORT",
                        reason="UNSUPPORTED_BUNDLE_VERSION",
                        detected_version=e.detected_version
                    )
                    failed_count += 1
                    
                except Exception as e:
                    # MXI-3.1: Register generic failure
                    fail_bundle_id = f"fail_{hashlib.md5(str(bdir).encode()).hexdigest()[:12]}"
                    registry.register(
                        bundle_id=fail_bundle_id,
                        symbol="UNKNOWN",
                        tf="UNKNOWN",
                        bundle_path=str(bdir),
                        metrics={},
                        status="FAILED_IMPORT",
                        reason=str(e)[:100]
                    )
                    failed_count += 1
                    
            st.rerun()

    # --- Filters ---
    all_cands = registry.list_all()
    if not all_cands:
        st.info("Kayıtlı aday yok. Lütfen 'Local Tara' butonuna basın.")
        return

    df_full = pd.DataFrame(all_cands)
    
    with st.expander("🔍 Filtreler", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        symbols = sorted(df_full["symbol"].unique().tolist())
        tfs = sorted(df_full["tf"].unique().tolist())
        statuses = sorted(df_full["status"].unique().tolist())
        
        sel_sym = f1.multiselect("Sembol", symbols)
        sel_tf = f2.multiselect("TF", tfs)
        sel_stat = f3.multiselect("Durum", statuses)
        hide_legacy = f4.checkbox("Legacy Gizle", value=True, help="FAILED_IMPORT durumundaki eski paketleri gizle")
        
    df = df_full.copy()
    if sel_sym: df = df[df["symbol"].isin(sel_sym)]
    if sel_tf: df = df[df["tf"].isin(sel_tf)]
    if sel_stat: df = df[df["status"].isin(sel_stat)]
    if hide_legacy: df = df[df["status"] != "FAILED_IMPORT"]

    # PNL-1100: Robust columns - ensure all expected columns exist and handle missing values
    expected_cols = ["symbol", "tf", "bundle_id", "resolve_rate", "join_coverage", "status", "reason", "created_at"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = None
    
    # Fill missing numeric values with 0, strings with "N/A"
    df["resolve_rate"] = df["resolve_rate"].fillna(0)
    df["join_coverage"] = df["join_coverage"].fillna(0)
    df["reason"] = df["reason"].fillna("—")
    df["status"] = df["status"].fillna("UNKNOWN")
    
    st.dataframe(
        df[expected_cols].sort_values("created_at", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "resolve_rate": st.column_config.NumberColumn("Resolve Rate", format="%.2f"),
            "join_coverage": st.column_config.NumberColumn("Join Coverage", format="%.2f"),
        }
    )
    
    # --- Detail View ---
    st.divider()
    selected_cid = st.selectbox("Detay İncele (Aday Seç):", df["candidate_id"].tolist())
    
    if selected_cid:
        cand = registry.get(selected_cid)
        if not cand: return
        
        # Load full bundle
        from pathlib import Path
        try:
            m, p = source.load_bundle(Path(cand["bundle_path"]))
        except Exception as e:
            st.error(f"Bundle yüklenemedi: {e}")
            return
            
        # UI-B Layout
        st.header(f"📍 {cand['symbol']} - {cand['tf']}")
        
        # MXI-1030: Warning banner
        if cand["join_coverage"] < 0.80:
            st.warning(f"⚠️ DÜŞÜK JOIN KAPSAMI: %{cand['join_coverage']*100:.1f} (Hedef > %80)")
            
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Resolve Rate", f"%{m.metrics.trigger_resolve_rate*100:.1f}")
        col_m2.metric("Join Coverage", f"%{m.metrics.join_coverage*100:.1f}")
        
        status_color = {
            "APPROVED_FOR_WAR": "green",
            "REJECTED": "red",
            "NEEDS_PATCH": "orange",
            "TESTING": "orange",
            "NEW": "blue"
        }.get(cand["status"], "gray")
        
        col_m3.markdown(f"**Status:** :{status_color}[{cand['status']}]")
        
        # MXI-1300: Lifecycle Box
        with st.container(border=True):
            st.markdown("### 🔄 Candidate Lifecycle")
            from tezaver.matrix.adapters.run_registry import RunRegistry
            run_reg = RunRegistry()
            all_runs = run_reg.list_all()
            # Find last run for this candidate
            cand_runs = [r for r in all_runs if r.get("candidate_id") == selected_cid]
            cand_runs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            last_run = cand_runs[0] if cand_runs else None
            
            l1, l2, l3 = st.columns(3)
            l1.markdown(f"**Current Status:**\n:{status_color}[{cand['status']}]")
            if last_run:
                l2.markdown(f"**Last Verdict:**\n{last_run.get('verdict')}")
                l3.markdown(f"**Last Run ID:**\n`{last_run.get('run_id')}`")
            else:
                l2.markdown("**Last Verdict:**\nNone")
                l3.markdown("**Last Run ID:**\nNone")
        
        with st.expander("📋 Manifest & Metrics Detayı"):
            st.json(m.__dict__ if not hasattr(m, 'dict') else m.dict())
            
        # MXI-1040: Sniper Run Button
        c_btn1, c_btn2, c_btn3 = st.columns(3)
        
        if c_btn1.button("🚀 RUN SNIPER", type="primary", use_container_width=True, help="Seçili aday için Sniper backtestini başlatır."):
            registry.update_status(selected_cid, "TESTING")
            st.info(f"Sniper Run başlatılıyor: {selected_cid}")
            from tezaver.matrix.apps.run_sniper import run_sniper_stub
            run_id = run_sniper_stub(home, selected_cid)
            st.success(f"Sniper Run oluşturuldu: {run_id}")
            
            # MXI-1160: Redirect to RUNS
            st.session_state["matrix_selected_run_id"] = run_id
            st.session_state["matrix_selected_cat"] = "RUNS"
            st.rerun()

        # Approval Process (Onay Süreci)
        if c_btn2.button("✅ APPROVE", use_container_width=True, help="Adayı onayla ve strateji havuzuna hazırla"):
            registry.update_status(selected_cid, "APPROVED")
            st.success(f"Aday ONAYLANDI: {selected_cid}")
            st.rerun()
            
        if c_btn3.button("❌ REJECT", use_container_width=True, help="Adayı reddet"):
            registry.update_status(selected_cid, "REJECTED")
            st.warning(f"Aday REDDEDİLDİ: {selected_cid}")
            st.rerun()

        st.subheader("📖 Rally Stories (V1)")
        for s in p.stories:
            with st.expander(f"🎬 Story: {s.story_id[:8]} | {s.entry.get('trigger')} @ {s.entry.get('entry_price')}"):
                c_s1, c_s2 = st.columns([1, 1])
                with c_s1:
                    st.markdown(f"**Trigger:** {s.entry.get('trigger')}")
                    st.markdown(f"**Source:** {s.entry.get('trigger_source')}")
                    st.markdown(f"**Entry:** {s.entry.get('entry_price')}")
                    st.markdown(f"**Time (UTC):** {s.entry.get('event_time_utc')}")
                with c_s2:
                    st.markdown(f"**Risk (SL %):** %{s.risk.get('stop_loss_pct', 0)}")
                    st.markdown(f"**Support:** {s.entry.get('levels', {}).get('nearest_support')}")
                    st.markdown(f"**Resistance:** {s.entry.get('levels', {}).get('nearest_resistance')}")
                
                # Semantic Layer (Pre-Pattern) - MXI-1170
                if s.pre_pattern:
                    st.divider()
                    st.markdown("### 🎭 Semantic Layer (Anlamsal Katman)")
                    t_pp1, t_pp2, t_pp3 = st.tabs(["🥁 Ritim (Rhythm)", "✨ Ruh (Spirit)", "📜 Mana (Meaning)"])
                    
                    with t_pp1:
                        st.info(s.pre_pattern.rhythm.summary_tr)
                        st.markdown("**Faz Dizilimi:** " + " ➔ ".join([f"`{p}`" for p in s.pre_pattern.rhythm.phase_sequence]))
                        st.json(s.pre_pattern.rhythm.tempo)
                        
                    with t_pp2:
                        st.success(s.pre_pattern.spirit.summary_tr)
                        st.multiselect("Etiketler", s.pre_pattern.spirit.tags, default=s.pre_pattern.spirit.tags, disabled=True)
                        st.warning(f"💡 {s.pre_pattern.spirit.regime_hint_tr}")
                        
                    with t_pp3:
                        st.markdown(f"**Özet:** {s.pre_pattern.meaning.summary_tr}")
                        st.markdown(f"**🎯 Tez (Thesis):** {s.pre_pattern.meaning.thesis_tr}")
                        st.error(f"**🚫 Geçersizlik (Invalidation):** {s.pre_pattern.meaning.invalidation_tr}")
                else:
                    st.caption("Bu hikaye için anlamsal katman verisi bulunmuyor.")

        # MXI-1030: Diagnostics
        diag_path = Path(cand["bundle_path"]) / "join_diagnostics.json"
        if diag_path.exists():
            with open(diag_path, "r") as f:
                diag_data = json.load(f)
            with st.expander("🔍 Join Diagnostics (Tanılama Günlüğü)"):
                st.json(diag_data)

def render_runs(home: str):
    """
    MXI-1160: Render Runs history and detail.
    MXI-1500: UI Guard.
    """
    try:
        _render_runs_inner(home)
    except Exception as e:
        st.error(f"⚠️ Runs Render Hatası: {e}")
        st.exception(e)

def _render_runs_inner(home: str):
    """Inner implementation of render_runs."""
    from tezaver.matrix.adapters.run_registry import RunRegistry
    registry = RunRegistry()
    
    all_runs = registry.list_all()
    if not all_runs:
        st.info("Henüz gerçekleştirilmiş run yok.")
        return
        
    df = pd.DataFrame(all_runs)
    
    # Filter
    with st.expander("🔍 Filtreler"):
        f1, f2 = st.columns(2)
        sel_sym = f1.multiselect("Sembol", df["symbol"].unique())
        sel_verd = f2.multiselect("Verdict", df["verdict"].unique())
        
    if sel_sym: df = df[df["symbol"].isin(sel_sym)]
    if sel_verd: df = df[df["verdict"].isin(sel_verd)]
    
    # List Table
    st.subheader("📜 Run Geçmişi")
    st.dataframe(df.sort_values("created_at", ascending=False), use_container_width=True, hide_index=True)
    
    # Detail Selection
    st.divider()
    
    default_run = st.session_state.get("matrix_selected_run_id", "")
    run_ids = df["run_id"].tolist()
    idx = 0
    if default_run in run_ids:
        idx = run_ids.index(default_run)
        
    selected_rid = st.selectbox("Run Detayı Seç:", run_ids, index=idx)
    if selected_rid:
        st.session_state["matrix_selected_run_id"] = selected_rid
        render_run_detail(home, selected_rid)

def render_run_detail(home: str, run_id: str):
    """
    MXI-1160: Detailed view of a single Sniper Run.
    """
    st.header(f"🏁 Run Detail: {run_id}")
    
    run_dir = os.path.join(home, "runs", run_id)
    if not os.path.exists(run_dir):
        st.error("Run dizini bulunamadı.")
        return
        
    # Columns for high level stats
    j_path = os.path.join(run_dir, "judge.json")
    if os.path.exists(j_path):
        with open(j_path) as f: judge = json.load(f)
        verdict = judge.get("overall", "UNKNOWN")
        v_color = "green" if verdict == "PASS" else "red" if verdict == "FAIL" else "orange"
        st.subheader(f"Verdict: :{v_color}[{verdict}]")
    
    t1, t2, t3, t4 = st.tabs(["🛡️ Gates & Jury", "📊 Scorecard", "📜 Telemetry & Audit", "💰 Trade Audit"])
    
    with t1:
        g_path = os.path.join(run_dir, "gates.json")
        if os.path.exists(g_path):
            with open(g_path) as f: gates = json.load(f)
            for g in gates:
                icon = "✅" if g.get("status") == "PASS" else "❌" if g.get("status") == "FAIL" else "⚠️"
                st.write(f"{icon} **{g.get('name')}**: {g.get('reason','')}")
        else:
            st.info("Gates verisi yok.")
            
    with t2:
        sc_path = os.path.join(run_dir, "scorecard.json")
        if os.path.exists(sc_path):
            with open(sc_path) as f: sc = json.load(f)
            st.json(sc)
            
            # Metrics Breakdown (MXI-1130)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Trades", sc.get("trades_count", 0))
            c2.metric("PnL Raw", f"{sc.get('total_pnl_raw', 0):.2f}")
            c3.metric("Fee Cost", f"{sc.get('fee_cost', 0):.4f}")
        else:
            st.info("Scorecard yok.")
            
    with t3:
        # Last 50 events
        ev_path = os.path.join(run_dir, "events.ndjson")
        if os.path.exists(ev_path):
            with open(ev_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-50:]
            for line in reversed(lines):
                try:
                    e = json.loads(line)
                    st.text(f"{e.get('ts')} | {e.get('event_type')} | {e.get('payload', {}).get('decision','')}")
                except: pass
        else:
            st.info("Events bulunamadı.")

    with t4:
        # MXI-1401: Trade Audit Tab
        sc_path = os.path.join(run_dir, "scorecard.json")
        if os.path.exists(sc_path):
            with open(sc_path) as f: sc = json.load(f)
            audit = sc.get("trade_audit_v2", [])
            if audit:
                st.subheader("🏁 Trade Execution Audit (V2)")
                audit_df = pd.DataFrame(audit)
                # Reorder/Rename columns for better UX
                cols = ["ts", "side", "qty", "limit_price", "fill_price", "fee", "slippage", "notional"]
                st.dataframe(audit_df[cols] if all(c in audit_df.columns for c in cols) else audit_df, use_container_width=True)
            else:
                st.info("İşlem kaydı (audit) bulunamadı.")
        else:
            st.info("Scorecard yok.")

def render_registry(home: str):
    """Render Registry category."""
    st.subheader("📚 Cloud Registry Strategies")
    
    strat_dir = os.path.join(home, "cloud_registry", "strategies")
    if os.path.exists(strat_dir):
        sids = [d for d in os.listdir(strat_dir) if os.path.isdir(os.path.join(strat_dir, d))]
        
        if sids:
            for sid in sids:
                strat_path = os.path.join(strat_dir, sid, "strategy.json")
                if os.path.exists(strat_path):
                    with open(strat_path) as f:
                        s = json.load(f)
                    status = s.get("status_info", {}).get("status", "UNKNOWN")
                    icon = "✅" if status == "ACTIVE" else "⏸️" if status == "PAUSED" else "❓"
                    st.text(f"{icon} {sid}: {s.get('symbol', '?')} / {status}")
        else:
            st.info("Henüz strateji yok")
    else:
        st.info("cloud_registry/strategies klasörü yok")

def render_panel_health(home: str):
    """
    PNL-1030: Panel Health Page.
    Shows bundle discovery/import statistics and errors.
    MX-5260: Integrated Safety Protocol Registry.
    """
    from tezaver.ui.ui_guard import render_data_sources_box
    render_data_sources_box()
    
    st.subheader("🏥 Panel Health Diagnostics")
    
    if st.button("🔄 Refresh Health", type="primary", help="Panel sağlık metriklerini ve bundle durumlarını günceller."):
        st.cache_data.clear()
        st.rerun()
    
    # MX-5260: Safety Protocol Registry Table
    render_safety_protocols(home)
    
    # MX-5110: DataReport Summary
    render_datareport_summary(home)
    
    # MX-5100: Closed-bar Health
    render_closedbar_health(home)
    
    # MX-5210: Data Integrity Health
    render_dataintegrity_summary(home)
    
    # MX-5230: API Health
    render_api_health_summary(home)
    
    # MX-5250: Evidence Manifest
    render_evidence_summary(home)

    # MX-5170: Proof Bundle
    render_proof_bundle_summary(home)

    # MX-5240: Resource Health
    render_resource_summary(home)

    # MX-5130: Idempotency Shield
    render_idempotency_summary(home)

    # MX-5140: Restart Reconcile
    render_restart_reconcile_summary(home)

    # MX-5270: Safety Certificate
    render_safety_certificate_summary(home)


    # MX-5160: Risk Mode
    render_risk_mode_summary(home)

    # MX-5220: Timebase
    render_timebase_summary(home)






    
    try:

        from tezaver.matrix.apps.panel_health import run_health_check
        health = run_health_check()
        
        # Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Discovered", health.get("discovered_count", 0))
        c2.metric("Imported OK", health.get("imported_count", 0))
        c3.metric("Failed", health.get("failed_count", 0))
        c4.metric("Check Time", health.get("check_time", "")[:19])
        
        st.caption(f"**CWD:** `{health.get('cwd')}`")
        st.caption(f"**Candidates Root:** `{health.get('candidates_root')}`")
        
        # Bundles Table
        st.divider()
        st.subheader("📦 Bundle Status")
        bundles = health.get("bundles", [])
        if bundles:
            bundles_df = pd.DataFrame(bundles)
            st.dataframe(bundles_df, use_container_width=True, hide_index=True)
        else:
            st.info("Henüz bundle bulunamadı.")
        
        # Errors
        errors = health.get("errors", [])
        if errors:
            st.divider()
            st.subheader("❌ Hatalar")
            for err in errors:
                st.error(f"**{err.get('path')}**: {err.get('error')}")
        
        # JSON Export
        with st.expander("📄 JSON Export"):
            st.json(health)
        
            
    except Exception as e:
        st.error(f"Health check başarısız: {e}")
        st.exception(e)

def render_safety_protocols(home: str):
    """MX-5260: Render Safety Protocol Registry Table."""
    st.divider()
    st.subheader("🛡️ Safety Protocols (Güvenlik Sağlama)")
    
    from tezaver.matrix.protocols.safety_registry import SafetyProtocolRegistry
    try:
        registry = SafetyProtocolRegistry()
        
        # Find latest run for drift check context
        import os
        from pathlib import Path
        latest_run_dir = None
        runs_root = Path(home) / "out" / "matrix_runs" / "war"
        if runs_root.exists():
            runs = [d for d in runs_root.iterdir() if d.is_dir()]
            if runs:
                latest_run_dir = str(sorted(runs, key=os.path.getmtime, reverse=True)[0])
            
        rows = registry.get_ui_rows(latest_run_dir)
        
        if registry.cloud_locked:
            st.info("☁️ **Cloud Locked:** Bulut çalışma zamanı korumaları şu an için devredışı/deferred.")
            
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )

    except Exception as e:
        st.error(f"Safety Registry yüklenemedi: {e}")
        st.info("PyYAML yüklü mü? `pip install PyYAML` deneyin.")

def render_datareport_summary(home: str):
    """MX-5110: Render DataReport summary in Panel Health."""
    st.divider()
    st.subheader("📊 Latest DataReport (Run-Scoped)")
    
    from tezaver.matrix.core.run_path import get_data_report_path
    
    # Simple logic to find the latest data_report_v1.json across all modes
    found_reports = []
    for mode in ["SNIPER", "WAR", "LIVE"]:
        mode_dir = Path(home) / "out" / "matrix_runs" / mode.lower()
        if mode_dir.exists():
            for rid in os.listdir(mode_dir):
                rp = get_data_report_path(mode, rid, home)
                if rp.exists():
                    found_reports.append({
                        "mode": mode,
                        "run_id": rid,
                        "path": str(rp),
                        "mtime": os.path.getmtime(rp)
                    })
    
    if found_reports:
        found_reports.sort(key=lambda x: x["mtime"], reverse=True)
        latest = found_reports[0]
        try:
            with open(latest["path"]) as f:
                rep = json.load(f)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Latest Run", latest["run_id"][:12])
            c2.metric("Resolve Rate", f"%{rep.get('resolved_rate', 0)*100:.1f}")
            c3.metric("Status", "PASS" if rep.get("ok") else "FAIL")
            
            st.caption(f"**Report Path:** `{latest['path']}`")
            with st.expander("Detaylı Rapor"):
                st.json(rep)
        except Exception as e:
            st.error(f"Rapor okunamadı: {e}")
    else:
        st.info("Henüz kapsamlı (run-scoped) bir DataReport bulunamadı.")

def render_maintenance(home: str):


    """
    PNL-1040: Maintenance Page.
    Provides tools for legacy cleanup, registry rebuild, and cache clear.
    """
    from tezaver.ui.ui_guard import render_data_sources_box
    render_data_sources_box()
    
    st.subheader("🔧 Bakım Araçları")
    
    # Cache Clear
    st.markdown("### 🧹 Cache Temizle")
    if st.button("Clear Streamlit Cache", use_container_width=True):
        st.cache_data.clear()
        st.success("✅ Cache temizlendi.")
        st.rerun()
    
    st.divider()
    
    # Legacy Cleanup
    st.markdown("### 📦 Legacy Bundle Cleanup")
    st.caption("bundle_v0 ve desteklenmeyen paketleri _legacy/ klasörüne taşır.")
    
    candidates_root = os.environ.get("MATRIX_CANDIDATES_ROOT", "out/matrix_candidates")
    legacy_dir = os.path.join(candidates_root, "_legacy")
    
    if st.button("🚮 Move Legacy Bundles to _legacy/", use_container_width=True):
        import shutil
        from pathlib import Path
        
        root = Path(candidates_root)
        moved = 0
        
        for mpath in root.rglob("manifest.json"):
            bundle_dir = mpath.parent
            try:
                with open(mpath) as f:
                    manifest = json.load(f)
                version = manifest.get("bundle_version", "0.0.0")
                if not version.startswith("1.1"):
                    # Move to _legacy
                    dest = Path(legacy_dir) / bundle_dir.relative_to(root)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(bundle_dir), str(dest))
                    moved += 1
            except Exception as e:
                st.warning(f"Hata ({bundle_dir}): {e}")
        
        st.success(f"✅ {moved} legacy bundle taşındı.")
        st.rerun()
    
    st.divider()
    
    # Registry Rebuild
    st.markdown("### 🔁 Registry Rebuild")
    st.caption("Bundle'lardan candidates_registry.jsonl'yi yeniden oluşturur.")
    
    if st.button("🔄 Rebuild Candidates Registry", use_container_width=True, help="Tüm kayıtları siler ve bundle'ları baştan tarayarak registry dosyasını yeniler."):
        from tezaver.matrix.adapters.bundle_source_local import LocalBundleSource, UnsupportedBundleVersion
        from tezaver.matrix.adapters.candidate_registry import CandidateRegistry
        from tezaver.matrix.core.candidate_v1 import generate_candidate_id
        import hashlib
        
        source = LocalBundleSource(base_path=candidates_root)
        registry = CandidateRegistry()
        
        # Clear existing
        registry.candidates = {}
        registry._save_all()
        
        bundles = source.discover_bundles()
        imported = 0
        failed = 0
        
        for bdir in bundles:
            try:
                manifest, _ = source.load_bundle(bdir)
                cid = generate_candidate_id(manifest)
                registry.register(
                    candidate_id=cid,
                    symbol=manifest.symbol,
                    tf=manifest.tf,
                    bundle_id=manifest.bundle_id,
                    bundle_path=str(bdir),
                    metrics={
                        "trigger_resolve_rate": manifest.metrics.trigger_resolve_rate,
                        "join_coverage": manifest.metrics.join_coverage
                    }
                )
                imported += 1
            except UnsupportedBundleVersion as e:
                cid = hashlib.md5(str(bdir).encode()).hexdigest()[:16]
                registry.register(
                    candidate_id=cid,
                    symbol="UNKNOWN",
                    tf="UNKNOWN",
                    bundle_id=str(bdir.name),
                    bundle_path=str(bdir),
                    metrics={},
                    status="FAILED_IMPORT",
                    reason="UNSUPPORTED_BUNDLE_VERSION",
                    detected_version=e.detected_version
                )
                failed += 1
            except Exception as e:
                failed += 1
        
        st.success(f"✅ Registry yeniden oluşturuldu: {imported} OK, {failed} failed.")
        st.rerun()


# ============================================================================
# MX-2040: WAR UI Panel
# ============================================================================

def render_war(home: str):
    """MX-2040: Render WAR panel for multi-coin backtest runs."""
    from tezaver.ui.ui_guard import render_data_sources_box
    render_data_sources_box()
    
    from tezaver.matrix.adapters.war_run_registry import WarRunRegistry
    from tezaver.matrix.apps.war_planner import WarPlanner
    from tezaver.matrix.core.war_engine import WarEngine
    from tezaver.matrix.core.risk_limiter import RiskLimits
    from tezaver.matrix.core.war_judge import WarGates
    
    registry = WarRunRegistry()
    planner = WarPlanner()
    
    # --- W1: Diagnostics Panel ---
    with st.expander("📊 Registry Diagnostics", expanded=False):
        diag = planner.get_diagnostics()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Toplam Aday", diag.candidates_total)
            st.metric("APPROVED_FOR_WAR", diag.approved_for_war_count)
        with col2:
            st.caption("Status Dağılımı")
            for status, count in diag.candidates_by_status.items():
                color = "🟢" if "APPROVED" in status else "🟡" if "NEW" in status else "🔴"
                st.text(f"{color} {status}: {count}")
        with col3:
            st.caption("Semboller")
            for sym in diag.symbols_found[:5]:
                st.text(f"• {sym}")
            st.caption(f"Registry: {diag.registry_path}")
    
    # --- Start New WAR Run ---
    with st.expander("🚀 Start New WAR Run", expanded=False):
        st.caption("APPROVED_FOR_WAR statüsündeki adayları çoklu backtest'e al")
        
        col1, col2 = st.columns(2)
        with col1:
            max_candidates = st.number_input("Max Candidates", 1, 20, 5)
            seed = st.number_input("Seed (Determinism)", 1, 99999, 42)
        with col2:
            max_notional = st.number_input("Max Total Notional", 1000, 1000000, 100000)
            max_positions = st.number_input("Max Concurrent Positions", 1, 20, 5)
        
        if st.button("⚔️ Start WAR Run", type="primary", help="Onaylı adaylar için toplu backtest simülasyonunu başlatır."):
            with st.spinner("WAR run başlatılıyor..."):
                try:
                    plan = planner.generate_plan(max_candidates=max_candidates, seed=seed)
                    
                    engine = WarEngine(
                        plan=plan,
                        risk_limits=RiskLimits(
                            max_total_notional=max_notional,
                            max_concurrent_positions=max_positions
                        ),
                        gates=WarGates(),
                        seed=seed
                    )
                    result = engine.run()
                    
                    # W2: Handle empty plan result
                    if result.get("verdict") == "EMPTY_PLAN":
                        st.warning("⚠️ APPROVED_FOR_WAR statüsünde aday bulunamadı!")
                        st.caption("Diagnostics:")
                        st.json(result.get("diagnostics", {}))
                    else:
                        st.success(f"✅ WAR Run tamamlandı: {result['run_id']}")
                        st.json({
                            "verdict": result["verdict"],
                            "total_trades": result["scorecard"]["total_trades"],
                            "net_pnl": result["scorecard"]["net_pnl"],
                            "scorecard_hash": result["scorecard"]["scorecard_hash"]
                        })
                        # W3: Show lifecycle update
                        st.caption(f"Candidate status güncellendi: {result['verdict']} → otomatik status")
                except Exception as e:
                    st.error(f"WAR Run hatası: {e}")
    
    st.divider()
    
    # --- WAR Runs List ---
    st.subheader("📋 WAR Runs")
    
    all_runs = registry.list_all()
    if not all_runs:
        st.info("Henüz WAR run yok. Yukarıdan yeni bir run başlatın.")
        return
    
    df = pd.DataFrame(all_runs)
    
    # Display columns
    display_cols = ["run_id", "verdict", "started_at"]
    if "scorecard_summary" in df.columns:
        df["trades"] = df["scorecard_summary"].apply(lambda x: x.get("total_trades", 0) if x else 0)
        df["net_pnl"] = df["scorecard_summary"].apply(lambda x: x.get("net_pnl", 0) if x else 0)
        display_cols.extend(["trades", "net_pnl"])
    
    # Add candidate/symbol counts
    if "candidate_ids" in df.columns:
        df["candidates"] = df["candidate_ids"].apply(lambda x: len(x) if x else 0)
        display_cols.append("candidates")
    if "symbols" in df.columns:
        df["symbols_count"] = df["symbols"].apply(lambda x: len(x) if x else 0)
        display_cols.append("symbols_count")
    
    st.dataframe(
        df[display_cols].sort_values("started_at", ascending=False),
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    # --- Run Detail ---
    st.subheader("🔍 Run Detail")
    selected_run_id = st.selectbox("Run Seç:", df["run_id"].tolist())
    
    if selected_run_id:
        run = registry.get(selected_run_id)
        if run:
            col1, col2, col3 = st.columns(3)
            with col1:
                verdict = run.get("verdict", "?")
                color = "🟢" if verdict == "PASS" else "🟡" if verdict == "IMPROVE" else "🔴"
                st.metric("Verdict", f"{color} {verdict}")
            with col2:
                summary = run.get("scorecard_summary", {})
                st.metric("Total Trades", summary.get("total_trades", 0))
            with col3:
                st.metric("Net PnL", f"{summary.get('net_pnl', 0):.2f}")
            
            # Scorecard hash
            st.caption(f"Scorecard Hash: `{summary.get('scorecard_hash', 'N/A')}`")
            
            # Candidates in run
            with st.expander("📋 Candidates"):
                cands = run.get("candidate_ids", [])
                for c in cands:
                    st.text(f"• {c}")
            
            # Symbols in run
            with st.expander("💱 Symbols"):
                syms = run.get("symbols", [])
                for s in syms:
                    st.text(f"• {s}")
            
            # Load full artifacts if available
            artifacts_dir = Path(f"out/matrix_runs/war/{selected_run_id}")
            if artifacts_dir.exists():
                with st.expander("📊 Full Scorecard"):
                    scorecard_path = artifacts_dir / "scorecard.json"
                    if scorecard_path.exists():
                        with open(scorecard_path) as f:
                            sc = json.load(f)
                        st.json(sc)
                
                with st.expander("📜 Telemetry Preview (Son 20)"):
                    tele_path = artifacts_dir / "telemetry.ndjson"
                    if tele_path.exists():
                        with open(tele_path) as f:
                            lines = f.readlines()[-20:]
                        for line in lines:
                            try:
                                e = json.loads(line)
                                st.text(f"{e.get('event_type', e.get('kind', ''))} | {e.get('candidate_id', '')}")
                            except:
                                pass
                
                # MX-5120: Trade Audit Table
                render_trade_audit_table(artifacts_dir)


def render_trade_audit_table(artifacts_dir: Path):
    """MX-5120: Render standard TradeAudit V2 table."""
    audit_path = artifacts_dir / "trade_audit_v2.jsonl"
    if audit_path.exists():
        with st.expander("📈 Trade Audit (Real PnL)", expanded=True):
            try:
                import pandas as pd
                rows = []
                with open(audit_path) as f:
                    for line in f:
                        rows.append(json.loads(line))
                if rows:
                    df = pd.DataFrame(rows)
                    # Use provided columns from prompt
                    cols = ["entry_ts", "exit_ts", "symbol", "side", "qty", "entry_price", "exit_price", "net_pnl", "exit_reason"]
                    present_cols = [c for c in cols if c in df.columns]
                    st.dataframe(df[present_cols], use_container_width=True)
                    
                    st.metric("Net Total PnL", f"${df['net_pnl'].sum():.2f}")
                else:
                    st.info("No trades executed in this run.")
            except Exception as e:
                st.error(f"Audit processing error: {e}")


def render_live(home: str):

    """MX-3040: Render LIVE panel for live trading mode."""
    from tezaver.ui.ui_guard import render_data_sources_box
    render_data_sources_box()
    
    from tezaver.matrix.adapters.live_run_registry import LiveRunRegistry
    from tezaver.matrix.apps.live_planner import LivePlanner
    from tezaver.matrix.core.live_engine import LiveEngine
    from tezaver.matrix.apps.incident_bundle import IncidentBundle
    
    registry = LiveRunRegistry()
    planner = LivePlanner()
    incidents = IncidentBundle()
    
    # --- Diagnostics Panel ---
    with st.expander("📊 Registry Diagnostics", expanded=False):
        diag = planner.get_diagnostics()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Toplam Aday", diag.candidates_total)
            st.metric("APPROVED_FOR_LIVE", diag.approved_for_live_count)
        with col2:
            st.caption("Status Dağılımı")
            for status, count in diag.candidates_by_status.items():
                color = "🟢" if "APPROVED_FOR_LIVE" in status else "🟡" if "APPROVED" in status else "🔴"
                st.text(f"{color} {status}: {count}")
        with col3:
            st.caption("Semboller")
            for sym in diag.symbols_found[:5]:
                st.text(f"• {sym}")
    
    # --- Start New LIVE Run ---
    with st.expander("🚀 Start LIVE Run", expanded=False):
        st.caption("APPROVED_FOR_LIVE adaylarını canlı çalıştır")
        
        col1, col2 = st.columns(2)
        with col1:
            max_candidates = st.number_input("Max Cells", 1, 10, 3, key="live_max")
            safe_mode = st.checkbox("Safe Mode (no new orders)", key="live_safe")
        with col2:
            max_bars = st.number_input("Max Bars (test)", 10, 500, 50, key="live_bars")
        
        if st.button("🟢 Start LIVE Run", type="primary", help="Onaylı adaylar için canlı prova oturumunu başlatır."):
            with st.spinner("LIVE run başlatılıyor..."):
                try:
                    plan = planner.generate_plan(max_candidates=max_candidates)
                    
                    if plan.is_empty:
                        st.warning("⚠️ APPROVED_FOR_LIVE statüsünde aday yok!")
                        st.json(plan.diagnostics.to_dict())
                    else:
                        # Fake bar callback for testing
                        def fake_bar_feed(bar_idx):
                            if bar_idx >= max_bars:
                                return None
                            # Generate fake bars for all symbols
                            return {s: {"close": 40000 + bar_idx * 10, "timestamp": bar_idx} for s in plan.symbols}
                        
                        engine = LiveEngine(plan=plan, safe_mode=safe_mode, bar_callback=fake_bar_feed)
                        result = engine.start(max_bars=max_bars)
                        
                        st.success(f"✅ LIVE Run tamamlandı: {result['run_id']}")
                        st.json({
                            "status": result["status"],
                            "bar_count": result["bar_count"],
                            "trade_count": result["trade_count"],
                            "safe_mode": result["safe_mode"]
                        })
                except Exception as e:
                    st.error(f"LIVE Run hatası: {e}")
    
    st.divider()
    
    # --- LIVE Runs List ---
    st.subheader("📋 LIVE Runs")
    runs = registry.list_all()
    
    if not runs:
        st.info("Henüz LIVE run yok.")
    else:
        df = pd.DataFrame([
            {
                "run_id": r["run_id"][:16] + "...",
                "status": r.get("status", "?"),
                "cells": len(r.get("cells", [])),
                "bars": r.get("bar_count", 0),
                "trades": r.get("trade_count", 0),
                "safe_mode": "✓" if r.get("safe_mode") else "",
                "heartbeat": r.get("last_heartbeat_ts", "")[:19]
            }
            for r in runs
        ])
        st.dataframe(df, use_container_width=True)
    
    st.divider()
    
    # --- Run Detail ---
    st.subheader("🔍 Run Detail")
    run_ids = [r["run_id"] for r in runs]
    
    if run_ids:
        selected_run_id = st.selectbox("Run seçin", run_ids, key="live_run_select")
        run = registry.get(selected_run_id)
        
        if run:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Status", run.get("status", "?"))
                st.metric("Bar Count", run.get("bar_count", 0))
            with col2:
                st.metric("Trade Count", run.get("trade_count", 0))
                st.metric("Incidents", run.get("incident_count", 0))
            
            # Telemetry preview
            with st.expander("📜 Telemetry Preview"):
                artifacts_dir = Path(f"out/matrix_runs/live/{selected_run_id}")
                tele_path = artifacts_dir / "telemetry.ndjson"
                if tele_path.exists():
                    with open(tele_path) as f:
                        lines = f.readlines()[-30:]
                    for line in lines:
                        try:
                            e = json.loads(line)
                            st.text(f"{e.get('event_type', e.get('kind', ''))} | bar={e.get('bar_index', '')}")
                        except:
                            pass
            
            # MX-5120: Trade Audit Table
            render_trade_audit_table(Path(f"out/matrix_runs/live/{selected_run_id}"))

    
    st.divider()
    
    # --- Incidents ---
    st.subheader("⚠️ Incidents")
    inc_list = incidents.list_incidents()
    
    if not inc_list:
        st.success("Incident yok.")
    else:
        for inc in inc_list[:5]:
            st.warning(f"{inc.get('incident_type', '?')} | {inc.get('incident_id', '')} | {inc.get('created_at', '')[:19]}")


def render_sniper(home: str):
    """MX-FINAL-0302: Render Sniper page for sniper runs."""
    from tezaver.ui.ui_guard import render_data_sources_box
    render_data_sources_box()
    
    st.subheader("🎯 Sniper Runs")
    st.caption("Sniper mode run geçmişi ve detayları")
    
    # List sniper runs from runs directory
    runs_dir = Path("out/matrix_runs/sniper")
    
    if not runs_dir.exists():
        st.info("Henüz Sniper run yok.")
        st.caption("Candidates sayfasından Run Sniper ile başlatabilirsiniz.")
        return
    
    runs = sorted(runs_dir.iterdir(), reverse=True)[:20]
    
    if not runs:
        st.info("Henüz Sniper run yok.")
        return
    
    # List runs
    for run_dir in runs:
        if run_dir.is_dir():
            report_path = run_dir / "report.json"
            if report_path.exists():
                with open(report_path) as f:
                    report = json.load(f)
                
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.text(run_dir.name)
                with col2:
                    st.text(f"trades: {report.get('trade_count', '?')}")
                with col3:
                    st.text(report.get('stopped_at', '')[:10] if report.get('stopped_at') else '')


def render_reports(home: str):
    """MX-FINAL: Render Reports page for summaries."""
    from tezaver.ui.ui_guard import render_data_sources_box
    render_data_sources_box()
    
    st.subheader("🧾 Reports")
    st.caption("WAR, LIVE ve Cloud run raporları")
    
    # WAR Reports
    with st.expander("⚔️ WAR Reports", expanded=True):
        war_dir = Path("out/matrix_runs/war")
        if war_dir.exists():
            reports = list(war_dir.glob("*/report.json"))[:5]
            for rp in reports:
                with open(rp) as f:
                    data = json.load(f)
                st.text(f"{rp.parent.name} | verdict: {data.get('verdict', '?')} | trades: {data.get('total_trades', '?')}")
        else:
            st.info("WAR rapor bulunamadı")
    
    # LIVE Reports
    with st.expander("🟢 LIVE Reports", expanded=False):
        live_dir = Path("out/matrix_runs/live")
        if live_dir.exists():
            reports = list(live_dir.glob("*/report.json"))[:5]
            for rp in reports:
                with open(rp) as f:
                    data = json.load(f)
                st.text(f"{rp.parent.name} | bars: {data.get('bar_count', '?')} | trades: {data.get('trade_count', '?')}")
        else:
            st.info("LIVE rapor bulunamadı")
    
    # Cloud Reports
    with st.expander("☁️ Cloud Reports", expanded=False):
        cloud_dir = Path("out/cloud_runs")
        if cloud_dir.exists():
            reports = list(cloud_dir.glob("*/report.json"))[:5]
            for rp in reports:
                with open(rp) as f:
                    data = json.load(f)
                st.text(f"{rp.parent.name} | mode: {data.get('mode', '?')} | trades: {data.get('trade_count', '?')}")
        else:
            st.info("Cloud rapor bulunamadı")


def render_incidents(home: str):
    """MX-FINAL-0401: Render Incidents page for evidence bundles."""
    from tezaver.ui.ui_guard import render_data_sources_box
    render_data_sources_box()
    
    from tezaver.matrix.apps.incident_bundle import IncidentBundle
    
    st.subheader("🚨 Incidents")
    st.caption("Kanıt paketleri (block, exception, data gap, reconcile error)")
    
    bundle = IncidentBundle()
    incidents = bundle.list_incidents()
    
    if not incidents:
        st.success("✅ Aktif incident yok")
        return
    
    for inc in incidents[:10]:
        with st.expander(f"{inc.get('incident_type', '?')} - {inc.get('incident_id', '')}", expanded=False):
            st.json(inc)
            
            # Show telemetry snapshot if exists
            inc_path = Path(f"out/matrix_incidents/live/{inc['incident_id']}")
            tele_path = inc_path / "telemetry_snapshot.ndjson"
            if tele_path.exists():
                st.caption("Telemetry Snapshot (last 10)")
                with open(tele_path) as f:
                    lines = f.readlines()[-10:]
                for line in lines:
                    try:
                        e = json.loads(line)
                        st.text(f"{e.get('event_type', e.get('kind', ''))} | {e.get('ts', '')[:19]}")
                    except:
                        pass

def render_bundles(home: str):
    """MX-4A: Render ApprovedRallyBundle panel for Matrix."""
    st.subheader("📦 ApprovedRallyBundle v1")
    st.caption("Dökümhane tarafından üretilen onaylı paketler")
    
    try:
        from tezaver.matrix.bundles.bundle_loader_v1 import load_all_bundles
        from tezaver.matrix.bundles.bundle_registry import BundleRegistry
        
        # Load bundles
        registry = BundleRegistry()
        bundles = load_all_bundles(registry=registry)
        
        # Show counts
        counts = registry.counts()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total", counts.get("total", 0))
        with col2:
            st.metric("✅ Loaded OK", counts.get("loaded_ok", 0))
        with col3:
            st.metric("❌ Rejected", counts.get("rejected", 0))
        with col4:
            st.metric("📥 Discovered", counts.get("discovered", 0))
        
        if not bundles:
            st.info("Henüz ApprovedRallyBundle yok. Önce ONY'de approve edip Dökümhane'de paketleyin.")
            return
        
        # Build table data
        table_data = []
        for b in bundles:
            if b.manifest:
                table_data.append({
                    "Symbol": b.manifest.symbol,
                    "TF": b.manifest.timeframe,
                    "Event ID": b.manifest.event_id[:30] + "..." if len(b.manifest.event_id) > 30 else b.manifest.event_id,
                    "QC Score": b.manifest.qc_score,
                    "Tier": b.manifest.tier or "UNKNOWN",
                    "Status": b.status,
                    "Reason": b.reject_reason or "-"
                })
            else:
                table_data.append({
                    "Symbol": "-",
                    "TF": "-",
                    "Event ID": "-",
                    "QC Score": "-",
                    "Tier": "-",
                    "Status": b.status,
                    "Reason": b.reject_reason or "-"
                })
        
        if table_data:
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True)
        
    except Exception as e:
        st.error(f"Bundle yükleme hatası: {e}")

def render_closedbar_health(home: str):
    """MX-5100: Render Closed-bar Health status."""

    st.subheader("🛡️ Closed-bar Health")
    
    # Scan latest telemetry for any run to check guard status
    runs_dir = Path(home) / "out" / "matrix_runs"
    latest_event = None
    
    # Check WAR runs first
    war_dir = runs_dir / "war"
    if war_dir.exists():
        for run_path in sorted(war_dir.glob("*"), key=os.path.getmtime, reverse=True):
            tel_path = run_path / "telemetry.ndjson"
            if tel_path.exists():
                with open(tel_path, "r") as f:
                    for line in f:
                        if "LOOKAHEAD_GUARD_OK" in line:
                            latest_event = json.loads(line)
                            break
            if latest_event: break
            
    col1, col2 = st.columns(2)
    if latest_event:
        col1.metric("Guard Status", "ACTIVE ✅")
        col2.metric("Last Proven", latest_event.get("ts", "")[:19])
        st.success(f"Lookahead Guard verified in run {latest_event.get('run_id')}")
    else:
        col1.metric("Guard Status", "WAITING ⏳")
        col2.metric("Last Proven", "N/A")
        st.warning("No guard proof found in recent telemetry.")


def render_dataintegrity_summary(home: str):
    """MX-5210: Render Data Integrity status."""

    st.subheader("📊 Data Integrity Health")
    
    # Scan Latest War Run for Integrity Report
    runs_dir = Path(home) / "out" / "matrix_runs" / "war"
    latest_report = None
    
    if runs_dir.exists():
        run_paths = sorted(runs_dir.glob("*"), key=os.path.getmtime, reverse=True)
        for rp in run_paths:
            integrity_path = rp / "reports" / "data_integrity_v1.json"
            if integrity_path.exists():
                try:
                    with open(integrity_path) as f:
                        data = json.load(f)
                        # data is Map<CandidateId, Report>
                        all_ok = True
                        for rid, rep in data.items():
                            if not rep.get("ok"): all_ok = False
                        latest_report = {"ok": all_ok, "run_id": rp.name, "path": str(integrity_path)}
                        break
                except: pass
                
    if latest_report:
        c1, c2 = st.columns(2)
        if latest_report["ok"]:
            c1.metric("Latest Integrity", "CLEAN ✨")
            st.success(f"Market data verified as consistent in run {latest_report['run_id']}")
        else:
            c1.metric("Latest Integrity", "DIRTY ⚠️")
            st.error(f"Integrity issues detected in {latest_report['run_id']}. Check logs.")
    else:
        st.metric("Latest Integrity", "N/A")
        st.info("No data integrity reports found.")


def render_api_health_summary(home: str):
    """MX-5230: Render API Health status."""

    st.subheader("🔌 API Health")
    
    # Scan Latest Live Run for API Health Report
    runs_dir = Path(home) / "out" / "matrix_runs" / "live"
    latest_report = None
    
    if runs_dir.exists():
        run_paths = sorted(runs_dir.glob("*"), key=os.path.getmtime, reverse=True)
        for rp in run_paths:
            api_path = rp / "reports" / "api_health_v1.json"
            if api_path.exists():
                try:
                    with open(api_path) as f:
                        latest_report = json.load(f)
                        latest_report["run_id"] = rp.name
                        break
                except: pass
                
    if latest_report:
        c1, c2, c3 = st.columns(3)
        state = latest_report.get("circuit_state", "UNKNOWN")
        
        if state == "CLOSED":
            c1.metric("Circuit State", "CLOSED ✅")
        else:
            c1.metric("Circuit State", f"{state} 🚨")
            
        c2.metric("Total Calls", latest_report.get("total_calls", 0))
        c3.metric("Retries", latest_report.get("retries_count", 0))
        
        if latest_report.get("rate_limit_count", 0) > 0:
            st.warning(f"Rate limits hit: {latest_report['rate_limit_count']}")
    else:
        st.metric("API Health", "N/A")
        st.info("No API health reports found.")


def render_evidence_summary(home: str):
    """MX-5250: Render Evidence Manifest status."""

    st.subheader("🛡️ Evidence Manifest")
    
    # Scan Latest War Run for Manifest
    runs_dir = Path(home) / "out" / "matrix_runs" / "war"
    latest_manifest = None
    
    if runs_dir.exists():
        run_paths = sorted(runs_dir.glob("*"), key=os.path.getmtime, reverse=True)
        for rp in run_paths:
            manifest_path = rp / "reports" / "evidence_manifest_v1.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path) as f:
                        latest_manifest = json.load(f)
                        latest_manifest["run_id"] = rp.name
                        break
                except: pass
                
    if latest_manifest:
        col1, col2 = st.columns([1, 2])
        col1.metric("Artifacts", len(latest_manifest.get("artifacts", [])))
        col2.code(latest_manifest.get("manifest_sha256", "N/A"), language="text")
        
        with st.expander("📄 Manifest Artifacts"):
            for art in latest_manifest.get("artifacts", []):
                st.write(f"- `{art['rel_path']}` ({art['bytes']} bytes)")
    else:
        st.metric("Evidence", "N/A")
        st.info("No evidence manifests found.")


def render_resource_summary(home: str):
    """MX-5240: Render Resource Health status."""

    st.subheader("🧯 Resource Health")
    
    # Scan Latest War Run for Resource Report
    runs_dir = Path(home) / "out" / "matrix_runs" / "war"
    latest_report = None
    
    if runs_dir.exists():
        run_paths = sorted(runs_dir.glob("*"), key=os.path.getmtime, reverse=True)
        for rp in run_paths:
            res_path = rp / "reports" / "resource_health_v1.json"
            if res_path.exists():
                try:
                    with open(res_path) as f:
                        latest_report = json.load(f)
                        latest_report["run_id"] = rp.name
                        break
                except: pass
                
    if latest_report:
        c1, c2, c3 = st.columns(3)
        ok = latest_report.get("ok", False)
        metrics = latest_report.get("metrics", {})
        
        if ok:
            c1.metric("Status", "HEALTHY ✅")
        else:
            c1.metric("Status", "TRIPPED 🚨")
            st.error(f"Alerts: {', '.join(latest_report.get('reasons', []))}")
            
        c2.metric("Disk Free", f"{metrics.get('disk_free_mb', 0)} MB")
        c3.metric("RAM (RSS)", f"{metrics.get('rss_mb', 0)} MB")
        
        if not ok:
            st.info(f"Safe mode triggered in run {latest_report['run_id']}")
    else:
        st.metric("Resource Health", "N/A")
        st.info("No resource health reports found.")


def render_idempotency_summary(home: str):
    """MX-5130: Render Idempotency Shield status."""

    st.subheader("🛡️ Idempotency Shield")
    
    # Scan Latest War Run for Idempotency Report
    runs_dir = Path(home) / "out" / "matrix_runs" / "war"
    latest_report = None
    
    if runs_dir.exists():
        run_paths = sorted(runs_dir.glob("*"), key=os.path.getmtime, reverse=True)
        for rp in run_paths:
            idem_path = rp / "reports" / "idempotency_keys_v1.json"
            if idem_path.exists():
                try:
                    with open(idem_path) as f:
                        latest_report = json.load(f)
                        latest_report["run_id"] = rp.name
                        break
                except: pass
                
    if latest_report:
        col1, col2 = st.columns(2)
        summary = latest_report.get("summary", {})
        blocked = summary.get("blocked_count", 0)
        
        if blocked == 0:
            col1.metric("Duplicates Blocked", "0 ✅")
        else:
            col1.metric("Duplicates Blocked", f"{blocked} 🛡️")
            st.warning(f"Detected and blocked {blocked} duplicate orders in {latest_report['run_id']}")
            
        col2.metric("Unique Signal Keys", summary.get("unique_orders_count", 0))
    else:
        st.metric("Idempotency", "N/A")
        st.info("No idempotency reports found.")


def render_restart_reconcile_summary(home: str):
    """MX-5140: Render Restart Reconciliation status."""
    st.subheader("🔄 Restart Reconcile")
    
    # Scan Latest Live Run for Reconcile Report
    runs_dir = Path(home) / "out" / "matrix_runs" / "live"
    latest_report = None
    
    if runs_dir.exists():
        run_paths = sorted(runs_dir.glob("*"), key=os.path.getmtime, reverse=True)
        for rp in run_paths:
            recon_path = rp / "reports" / "restart_reconcile_v1.json"
            if recon_path.exists():
                try:
                    with open(recon_path) as f:
                        latest_report = json.load(f)
                        latest_report["run_id"] = rp.name
                        break
                except: pass
                
    if latest_report:
        col1, col2 = st.columns(2)
        status = latest_report.get("status", "UNKNOWN")
        
        if status == "SUCCESS":
            col1.metric("Status", "CLEAN ✨")
        else:
            col1.metric("Status", f"{status} ⚠️")
            
        actions = latest_report.get("actions_taken", [])
        col2.metric("Actions", len(actions))
        
        if actions:
            with st.expander("📝 Actions Taken"):
                for act in actions:
                    st.write(f"- {act}")
                    
        if latest_report.get("unknown_orders"):
            st.warning(f"Found {len(latest_report['unknown_orders'])} unknown orders on exchange.")
    else:
        st.metric("Restart Reconcile", "N/A")
        st.info("No restart reconciliation reports found.")


def render_risk_mode_summary(home: str):
    """MX-5160: Render Emergency Mode / Risk State."""
    st.subheader("🚨 Emergency Mode")
    
    # Scan Latest Live/War Run for Telemetry or Logic
    runs_dir_live = Path(home) / "out" / "matrix_runs" / "live"
    runs_dir_war = Path(home) / "out" / "matrix_runs" / "war"
    
    # For UI demo, we'll try to find any run and peek at registry or telemetry
    latest_run = None
    if runs_dir_live.exists():
        run_paths = sorted(runs_dir_live.glob("*"), key=os.path.getmtime, reverse=True)
        if run_paths: latest_run = run_paths[0]
        
    if not latest_run and runs_dir_war.exists():
        run_paths = sorted(runs_dir_war.glob("*"), key=os.path.getmtime, reverse=True)
        if run_paths: latest_run = run_paths[0]

    if latest_run:
        # Ideally we'd have a run_mode_v1.json, but for now we look at general status
        col1, col2 = st.columns(2)
        # Placeholder for real state (in v1 we just show if any NEW_ORDER_BLOCKED happened)
        telemetry_path = latest_run / "telemetry.ndjson"
        mode = "NORMAL"
        reasons = []
        
        if telemetry_path.exists():
            try:
                with open(telemetry_path) as f:
                    for line in f:
                        ev = json.loads(line)
                        if ev.get("event_type") == "LIVE_SAFE_MODE_ENABLED":
                            mode = "SAFE_MODE"
                            reasons.append(ev.get("reason", "UNKNOWN"))
                        if ev.get("event_type") == "NEW_ORDER_BLOCKED":
                            mode = "SAFE_MODE"
                            reasons.append(ev.get("reason", "POLICY_ENFORCED"))
            except: pass

        if mode == "NORMAL":
            col1.metric("Current Mode", "NORMAL 🟢")
        elif mode == "SAFE_MODE":
            col1.metric("Current Mode", "SAFE 🟡")
        else:
            col1.metric("Current Mode", "HALTED 🔴")
            
        if reasons:
            st.error(f"Active Block Reasons: {', '.join(set(reasons))}")
    else:
        st.metric("Emergency Mode", "N/A")


def render_timebase_summary(home: str):
    """MX-5220: Render Timebase status."""
    st.subheader("⏱️ Timebase")
    
    # Scan Latest Live Run for Timebase Report
    runs_dir = Path(home) / "out" / "matrix_runs" / "live"
    latest_report = None
    
    if runs_dir.exists():
        run_paths = sorted(runs_dir.glob("*"), key=os.path.getmtime, reverse=True)
        for rp in run_paths:
            report_path = rp / "reports" / "timebase_v1.json"
            if report_path.exists():
                try:
                    with open(report_path) as f:
                        latest_report = json.load(f)
                        latest_report["run_id"] = rp.name
                        break
                except: pass
                
    if latest_report:
        col1, col2, col3 = st.columns(3)
        skew = latest_report.get("exchange_offset_ms", 0)
        
        if abs(skew) < 100:
            col1.metric("Clock Skew", f"{skew}ms ✨")
        else:
            col1.metric("Clock Skew", f"{skew}ms ⚠️")
            
        col2.metric("Monotonic", "OK ✅" if latest_report.get("monotonic_ok") else "FAIL ❌")
        col3.metric("Network", f"{latest_report.get('network_delay_ms', 0)}ms")
        
        st.caption(f"Last sync: {latest_report.get('ts')}")
    else:
        st.metric("Timebase", "N/A")
        st.info("No timebase reports found.")


def render_proof_bundle_summary(home: str):
    """MX-5170: Render Proof Bundle status."""
    st.subheader("📦 Proof Bundle")
    
    # Scan Latest Live Run for Bundle Metadata
    runs_dir = Path(home) / "out" / "matrix_runs" / "live"
    latest_metadata = None
    
    if runs_dir.exists():
        run_paths = sorted(runs_dir.glob("*"), key=os.path.getmtime, reverse=True)
        for rp in run_paths:
            meta_path = rp / "proof_bundle" / "bundle_metadata_v1.json"
            if meta_path.exists():
                try:
                    with open(meta_path) as f:
                        latest_metadata = json.load(f)
                        latest_metadata["run_id"] = rp.name
                        break
                except: pass
                
    if latest_metadata:
        col1, col2 = st.columns(2)
        count = latest_metadata.get("artifact_count", 0)
        size_kb = round(latest_metadata.get("total_bytes", 0) / 1024, 1)
        
        col1.metric("Artifacts", count)
        col2.metric("Bundle Size", f"{size_kb} KB")
        
        bundle_path = latest_metadata.get("bundle_path", "N/A")
        st.code(f"Path: {bundle_path}", language="bash")
        
        st.caption(f"Packaged at: {latest_metadata.get('bundle_ts')}")
    else:
        st.metric("Proof Bundle", "N/A")
        st.info("No proof bundles found. Ensure run is complete.")


def render_safety_certificate_summary(home: str):
    """MX-5270: Render Safety Certificate status badge."""
    st.divider()
    st.subheader("🧾 Safety Certificate")
    
    from pathlib import Path
    import os
    import json
    
    # Scan Latest WAR run for certificate
    runs_dir = Path(home) / "out" / "matrix_runs" / "war"
    latest_cert = None
    
    if runs_dir.exists():
        run_paths = sorted([d for d in runs_dir.iterdir() if d.is_dir()], key=os.path.getmtime, reverse=True)
        for rp in run_paths:
            cert_path = rp / "reports" / "safety_certificate_v1.json"
            if cert_path.exists():
                try:
                    with open(cert_path) as f:
                        latest_cert = json.load(f)
                        latest_cert["_run_id"] = rp.name
                        break
                except: pass
                
    if latest_cert:
        cert_res = latest_cert.get("results", {})
        verdict = cert_res.get("verdict", "UNKNOWN")
        blockers_count = len(cert_res.get("blockers", []))
        active_stage = cert_res.get("active_stage", "N/A")
        
        col1, col2, col3 = st.columns(3)
        
        if verdict == "PASS":
            col1.success(f"✅ ALL GREEN")
        else:
            col1.error(f"❌ BLOCKED")
        
        col2.metric("Blockers", blockers_count)
        col3.metric("Stage", active_stage)
        
        st.caption(f"Run: `{latest_cert.get('_run_id')}` | Generated: {latest_cert.get('ts')}")
    else:
        st.metric("Safety Certificate", "N/A")
        st.info("No safety certificates found. Ensure run is complete.")


