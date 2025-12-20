"""
Matrix V4 Tab - Streamlit Integration for Matrix V4

This module provides the main Matrix V4 UI in Streamlit.
Does NOT import panel_server or legacy matrix modules.
"""

import streamlit as st
import os
import json
from tezaver.ui.matrix_v4_context import build_matrix_v4_context

# Categories
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
    ("RUNS", "▶️ Runs", "Çalıştırma geçmişi"),
    ("REGISTRY", "📚 Registry", "Cloud strateji kaydı"),
]

def render_matrix_v4():
    """Main entry point for Matrix V4 Streamlit UI."""
    
    # Sidebar: Home selection
    st.sidebar.header("🎛️ Matrix V4")
    
    home = st.sidebar.text_input(
        "Home Path",
        value=st.session_state.get("matrix_home", ".tezaver_matrix"),
        key="matrix_home_input"
    )
    st.session_state["matrix_home"] = home
    
    # Build context
    ctx = build_matrix_v4_context(home)
    
    # Sidebar: Category selection
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Kategoriler")
    
    category_labels = {cat[0]: f"{cat[1]}" for cat in CATEGORIES}
    selected_cat = st.sidebar.radio(
        "Kategori Seç",
        options=[c[0] for c in CATEGORIES],
        format_func=lambda x: category_labels[x],
        label_visibility="collapsed"
    )
    
    # Top Banner
    counts = ctx["counts"]
    st.markdown(f"""
    <div style="background:#333; color:#fff; padding:12px; font-family:monospace; margin-bottom:20px; border-radius:5px;">
        <b>Build:</b> {ctx['commit']} | <b>Branch:</b> {ctx['branch']} | <b>Home:</b> {ctx['home']}<br/>
        <small>candidates={counts['candidates']} runs={counts['runs']} alerts={counts['alerts_active']} 
        approved={counts['approved']} exports={counts['exports']} strategies={counts['strategies']}</small>
    </div>
    """, unsafe_allow_html=True)
    
    # Category Title
    cat_info = next((c for c in CATEGORIES if c[0] == selected_cat), None)
    if cat_info:
        st.header(f"{cat_info[1]}")
        st.caption(cat_info[2])
    
    st.divider()
    
    # Render selected category
    if selected_cat == "OPS":
        render_ops(home)
    elif selected_cat == "ALERTS":
        render_alerts(home)
    elif selected_cat == "CLOUD_RUNTIME":
        render_cloud_runtime(home)
    elif selected_cat == "USERSTREAM":
        render_userstream(home)
    elif selected_cat == "LOOP":
        render_loop(home)
    elif selected_cat == "MIGRATION":
        render_migration(home)
    elif selected_cat == "RELEASE":
        render_release(home)
    elif selected_cat == "REHEARSAL":
        render_rehearsal(home)
    elif selected_cat == "CANDIDATES":
        render_candidates(home)
    elif selected_cat == "RUNS":
        render_runs(home)
    elif selected_cat == "REGISTRY":
        render_registry(home)

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
                st.text(f"{e.get('ts', '')} | {e.get('kind', '')} | {e.get('title_tr', '')}")
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
                st.text(f"{e.get('ts', '')} | {e.get('kind', '')}")
            except:
                pass
    else:
        st.info("history.ndjson yok")
        
    st.divider()
    
    ticks = st.number_input("Loop Ticks", min_value=1, max_value=10, value=3, key="loop_ticks")
    if st.button("Run Loop Once"):
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
    
    candidate_id = st.text_input("Candidate ID", key="release_cid")
    
    if st.button("Evaluate"):
        if not candidate_id:
            st.warning("Candidate ID gerekli")
        else:
            try:
                from tezaver.matrix.core.release_gate import evaluate_release_gate
                result = evaluate_release_gate(home, candidate_id)
                
                ok = result.get("ok", False)
                if ok:
                    st.success(f"✅ PASS: {result.get('summary', '')}")
                else:
                    st.error(f"❌ FAIL: {result.get('summary', '')}")
                    
                st.json(result)
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
    if st.button("Run Rehearsal"):
        try:
            from tezaver.matrix.core.rehearsal import run_rehearsal, write_latest
            result = run_rehearsal(home, candidate_id if candidate_id else None)
            write_latest(home, result)
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

def render_candidates(home: str):
    """Render Candidates category."""
    st.subheader("📋 Candidates")
    
    cand_dir = os.path.join(home, "candidates")
    if os.path.exists(cand_dir):
        cids = [d for d in os.listdir(cand_dir) if os.path.isdir(os.path.join(cand_dir, d))]
        
        if cids:
            for cid in cids:
                manifest_path = os.path.join(cand_dir, cid, "manifest.json")
                if os.path.exists(manifest_path):
                    with open(manifest_path) as f:
                        m = json.load(f)
                    st.text(f"📁 {cid}: {m.get('symbol', '?')} / {m.get('timeframe', '?')}")
        else:
            st.info("Henüz candidate yok")
    else:
        st.info("candidates klasörü yok")

def render_runs(home: str):
    """Render Runs category."""
    st.subheader("▶️ Runs")
    
    runs_dir = os.path.join(home, "runs")
    if os.path.exists(runs_dir):
        rids = [d for d in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, d))]
        
        if rids:
            for rid in rids[:20]:  # Show last 20
                st.text(f"▶️ {rid}")
        else:
            st.info("Henüz run yok")
    else:
        st.info("runs klasörü yok")

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
