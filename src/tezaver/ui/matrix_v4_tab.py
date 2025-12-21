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
    ("WAR", "⚔️ WAR", "Multi-coin backtest"),
    ("PANEL_HEALTH", "🏥 Panel Health", "Bundle ve registry sağlık durumu"),
    ("MAINTENANCE", "🔧 Maintenance", "Bakım ve temizlik araçları"),
    ("REGISTRY", "📚 Registry", "Cloud strateji kaydı"),
    ("PLATFORM", "🏗️ Platform", "Connectors, Jobs, Ops"),
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
    
    # MXI-1160: Support programmatic redirect via session state
    if "matrix_selected_cat" not in st.session_state:
        st.session_state["matrix_selected_cat"] = "OPS"
        
    category_labels = {cat[0]: f"{cat[1]}" for cat in CATEGORIES}
    
    # Finding current index
    cat_keys = [c[0] for c in CATEGORIES]
    try:
        current_idx = cat_keys.index(st.session_state["matrix_selected_cat"])
    except:
        current_idx = 0

    selected_cat = st.sidebar.radio(
        "Kategori Seç",
        options=cat_keys,
        index=current_idx,
        format_func=lambda x: category_labels[x],
        label_visibility="collapsed",
        key="matrix_cat_radio"
    )
    # Sync if user manually clicks
    if selected_cat != st.session_state["matrix_selected_cat"]:
        st.session_state["matrix_selected_cat"] = selected_cat
    
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
    elif selected_cat == "WAR":
        render_war(home)
    elif selected_cat == "PANEL_HEALTH":
        render_panel_health(home)
    elif selected_cat == "MAINTENANCE":
        render_maintenance(home)
    elif selected_cat == "REGISTRY":
        render_registry(home)
    elif selected_cat == "PLATFORM":
        from tezaver.ui.platform_tab import render_platform_tab
        render_platform_tab()

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
        if st.button("🔄 Local Tara & Import", use_container_width=True):
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
        
        if c_btn1.button("🚀 RUN SNIPER", type="primary", use_container_width=True):
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
    """
    from tezaver.ui.ui_guard import render_data_sources_box
    render_data_sources_box()
    
    st.subheader("🏥 Panel Health Diagnostics")
    
    if st.button("🔄 Refresh Health", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
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
    
    if st.button("🔄 Rebuild Candidates Registry", use_container_width=True):
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
        
        if st.button("⚔️ Start WAR Run", type="primary"):
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
                                st.text(f"{e.get('kind', '')} | {e.get('candidate_id', '')}")
                            except:
                                pass
