"""
MX-23003+23004: Approved → Cloud Deploy Wizard

Deploy flow with Release Gate and Rehearsal checks.
"""

import streamlit as st
import os
import json
import time
import uuid
from urllib.request import urlopen, Request
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from tezaver.platform.bus.adapter import FsBusAdapter


@dataclass
class StepResult:
    """Result of a pipeline step."""
    name: str
    status: str  # WAITING, RUNNING, OK, FAIL
    message: str = ""
    data: Dict = None


def list_exports(bus: FsBusAdapter, prefix: str = "artifacts/matrix/exports/") -> List[str]:
    """List export artifacts in bus."""
    try:
        items = bus.list(prefix.rstrip("/"))
        return [item for item in items if item.endswith(".json")]
    except:
        return []


def extract_candidate_id_from_export(bus: FsBusAdapter, export_path: str) -> Optional[str]:
    """Extract candidate_id from export artifact."""
    # First try from data
    try:
        export_data = bus.get_json(export_path)
        if export_data and export_data.get("candidate_id"):
            return export_data.get("candidate_id")
    except:
        pass
    # Fallback: parse from filename
    basename = os.path.basename(export_path)
    if basename.endswith(".json"):
        return basename[:-5]
    return None


def enqueue_job(bus: FsBusAdapter, target: str, job_type: str, payload: Dict) -> str:
    """Enqueue a job to bus inbox."""
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job = {
        "job_id": job_id,
        "job_type": job_type,
        "target": target,
        "payload": payload,
        "created_at": int(time.time()),
        "priority": 50,
    }
    
    inbox_path = f"jobs/{target}/inbox/{job_id}.json"
    bus.put_json(inbox_path, job)
    return job_id


def scan_agent(base_url: str, token: str) -> bool:
    """Tell agent to scan inbox."""
    try:
        req = Request(f"{base_url}/control/scan_inbox", method="POST")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_outbox_result(bus: FsBusAdapter, target: str, job_id: str, timeout: float = 5.0) -> Optional[Dict]:
    """Wait for job result in outbox."""
    outbox_path = f"jobs/{target}/outbox/{job_id}.json"
    start = time.time()
    
    while time.time() - start < timeout:
        if bus.exists(outbox_path):
            return bus.get_json(outbox_path)
        time.sleep(0.2)
    return None


def run_release_rehearsal_checks(
    bus: FsBusAdapter,
    candidate_id: str,
    matrix_url: str,
    matrix_token: str,
    mode: str = "PAPER",
) -> Dict[str, Any]:
    """
    Run release gate and rehearsal checks via MatrixAgent.
    
    Returns dict with release_status, rehearsal, fail_codes, details_tr, etc.
    """
    release_result = {"release_status": "N/A", "fail_codes": [], "details_tr": []}
    rehearsal_result = {"rehearsal": "N/A", "fail_codes": [], "details_tr": []}
    
    # Release Check
    try:
        job_id = enqueue_job(bus, "matrix", "MATRIX_RELEASE_CHECK", {
            "candidate_id": candidate_id,
        })
        scan_agent(matrix_url, matrix_token)
        result = get_outbox_result(bus, "matrix", job_id)
        
        if result and result.get("result", {}).get("ok"):
            release_result = {
                "release_status": result["result"].get("release_status", "N/A"),
                "fail_codes": result["result"].get("fail_codes", []),
                "details_tr": result["result"].get("details_tr", []),
            }
    except:
        pass
        
    # Rehearsal Check
    try:
        job_id = enqueue_job(bus, "matrix", "MATRIX_REHEARSAL_CHECK", {
            "candidate_id": candidate_id,
            "mode": mode,
        })
        scan_agent(matrix_url, matrix_token)
        result = get_outbox_result(bus, "matrix", job_id)
        
        if result and result.get("result", {}).get("ok"):
            rehearsal_result = {
                "rehearsal": result["result"].get("rehearsal", "N/A"),
                "fail_codes": result["result"].get("fail_codes", []),
                "details_tr": result["result"].get("details_tr", []),
            }
    except:
        pass
        
    return {
        "release_status": release_result["release_status"],
        "release_fail_codes": release_result["fail_codes"],
        "release_details_tr": release_result["details_tr"],
        "rehearsal": rehearsal_result["rehearsal"],
        "rehearsal_fail_codes": rehearsal_result["fail_codes"],
        "rehearsal_details_tr": rehearsal_result["details_tr"],
    }


def run_approved_deploy_flow(
    bus_root: str,
    export_path: str,
    cloud_url: str,
    cloud_token: str,
    activate: bool = True,
    ticks: int = 2,
) -> List[StepResult]:
    """Run Approved → Cloud Deploy flow (3-4 steps)."""
    bus = FsBusAdapter(bus_root)
    results = []
    
    # Step 1: Cloud Import Strategy
    results.append(StepResult("1. Cloud Import Strategy", "RUNNING"))
    try:
        job_id = enqueue_job(bus, "cloud", "CLOUD_IMPORT_STRATEGY", {
            "export_path": export_path,
        })
        scan_agent(cloud_url, cloud_token)
        result = get_outbox_result(bus, "cloud", job_id)
        
        if result and result.get("result", {}).get("ok"):
            strategy_id = result["result"]["strategy_id"]
            status = result["result"]["status"]
            results[-1] = StepResult("1. Cloud Import Strategy", "OK", f"{strategy_id} ({status})", {
                "strategy_id": strategy_id,
                "status": status,
            })
        else:
            error = result.get("result", {}).get("error_code", "Unknown") if result else "No response"
            results[-1] = StepResult("1. Cloud Import Strategy", "FAIL", error)
            return results
    except Exception as e:
        results[-1] = StepResult("1. Cloud Import Strategy", "FAIL", str(e))
        return results
        
    # Step 2: Cloud Activate (if requested)
    if activate:
        results.append(StepResult("2. Cloud Activate", "RUNNING"))
        try:
            job_id = enqueue_job(bus, "cloud", "CLOUD_SET_STATUS", {
                "strategy_id": strategy_id,
                "status": "ACTIVE",
            })
            scan_agent(cloud_url, cloud_token)
            result = get_outbox_result(bus, "cloud", job_id)
            
            if result and result.get("result", {}).get("ok"):
                results[-1] = StepResult("2. Cloud Activate", "OK", f"{strategy_id} → ACTIVE", {
                    "strategy_id": strategy_id,
                    "status": "ACTIVE",
                })
            else:
                error = result.get("result", {}).get("error_code", "Unknown") if result else "No response"
                results[-1] = StepResult("2. Cloud Activate", "FAIL", error)
                return results
        except Exception as e:
            results[-1] = StepResult("2. Cloud Activate", "FAIL", str(e))
            return results
            
    # Step 3: Cloud Tick
    step_num = 3 if activate else 2
    results.append(StepResult(f"{step_num}. Cloud Tick (x{ticks})", "RUNNING"))
    try:
        job_id = enqueue_job(bus, "cloud", "CLOUD_RUNTIME_TICK", {
            "ticks": ticks,
        })
        scan_agent(cloud_url, cloud_token)
        result = get_outbox_result(bus, "cloud", job_id)
        
        if result and result.get("result", {}).get("ok"):
            ticks_done = result["result"]["ticks_done"]
            results[-1] = StepResult(f"{step_num}. Cloud Tick (x{ticks})", "OK", f"{ticks_done} ticks done", {
                "ticks_done": ticks_done,
            })
        else:
            error = result.get("result", {}).get("error_code", "Unknown") if result else "No response"
            results[-1] = StepResult(f"{step_num}. Cloud Tick (x{ticks})", "FAIL", error)
            return results
    except Exception as e:
        results[-1] = StepResult(f"{step_num}. Cloud Tick (x{ticks})", "FAIL", str(e))
        return results
        
    return results


def render_platform_deploy():
    """Render Approved → Cloud Deploy Wizard page."""
    st.header("🚀 Approved → Cloud Deploy Wizard")
    st.caption("Export'u Cloud'a deploy et ve çalıştır")
    
    # Get config from session
    bus_root = st.session_state.get("platform_bus_root", ".tezaver_bus")
    matrix_url = st.session_state.get("matrix_url", "http://127.0.0.1:9002")
    matrix_token = st.session_state.get("matrix_token", "MATRIX_TOKEN")
    cloud_url = st.session_state.get("cloud_url", "http://127.0.0.1:9003")
    cloud_token = st.session_state.get("cloud_token", "CLOUD_TOKEN")
    
    bus = FsBusAdapter(bus_root)
    
    # Source selection
    st.subheader("📦 Export Kaynağı")
    
    source_mode = st.radio("Kaynak Seç", ["Bus'tan Seç", "Elle Path Gir"], horizontal=True)
    
    export_path = None
    
    if source_mode == "Bus'tan Seç":
        exports = list_exports(bus)
        if exports:
            export_path = st.selectbox("Export Artifact", exports)
        else:
            st.warning("⚠️ Bus'ta export artifact yok. Önce Matrix Agent ile approve/export çalıştırın.")
    else:
        export_path = st.text_input("Export Path", "artifacts/matrix/exports/")
        
    st.divider()
    
    # Release Gate / Rehearsal Check
    st.subheader("🚦 Release Gate / Rehearsal Check")
    
    candidate_id = None
    gate_info = None
    
    if export_path:
        candidate_id = extract_candidate_id_from_export(bus, export_path)
        
        if candidate_id:
            st.text(f"Candidate ID: {candidate_id}")
            
            col1, col2 = st.columns(2)
            with col1:
                mode = st.selectbox("Rehearsal Mode", ["PAPER", "REAL"])
                
            if st.button("🔍 Gate/Rehearsal Kontrol Et"):
                with st.spinner("Kontrol ediliyor..."):
                    gate_info = run_release_rehearsal_checks(
                        bus, candidate_id, matrix_url, matrix_token, mode
                    )
                    st.session_state["gate_info"] = gate_info
                    
    # Display gate info
    if "gate_info" in st.session_state:
        gate_info = st.session_state["gate_info"]
        
        col1, col2 = st.columns(2)
        
        with col1:
            release_status = gate_info.get("release_status", "N/A")
            if release_status == "PASS":
                st.success(f"✅ Release Gate: **PASS**")
            elif release_status == "FAIL":
                st.error(f"❌ Release Gate: **FAIL**")
                for detail in gate_info.get("release_details_tr", []):
                    st.text(f"  • {detail}")
            else:
                st.info(f"Release Gate: {release_status}")
                
        with col2:
            rehearsal = gate_info.get("rehearsal", "N/A")
            if rehearsal == "GO":
                st.success(f"✅ Rehearsal: **GO**")
            elif rehearsal == "NO_GO":
                st.error(f"❌ Rehearsal: **NO_GO**")
                for detail in gate_info.get("rehearsal_details_tr", []):
                    st.text(f"  • {detail}")
            else:
                st.info(f"Rehearsal: {rehearsal}")
                
    st.divider()
    
    # Options
    st.subheader("⚙️ Deploy Ayarları")
    
    # Block activation if gate fails
    gate_allows_activation = True
    if "gate_info" in st.session_state:
        gate_info = st.session_state["gate_info"]
        if gate_info.get("release_status") == "FAIL" or gate_info.get("rehearsal") == "NO_GO":
            gate_allows_activation = False
    
    col1, col2 = st.columns(2)
    with col1:
        if gate_allows_activation:
            activate = st.checkbox("Aktifleştir (ACTIVE)", value=True)
        else:
            st.warning("⚠️ Gate FAIL/NO_GO - Aktivasyon engellendi")
            activate = False
    with col2:
        ticks = st.number_input("Tick Sayısı", min_value=0, max_value=100, value=2)
        
    st.divider()
    
    # Run button
    if export_path and st.button("🚀 Deploy Çalıştır", type="primary", use_container_width=True):
        with st.spinner("Deploy çalışıyor..."):
            results = run_approved_deploy_flow(
                bus_root,
                export_path,
                cloud_url,
                cloud_token,
                activate=activate,
                ticks=ticks,
            )
            st.session_state["deploy_results"] = results
            
    # Results display
    if "deploy_results" in st.session_state:
        results = st.session_state["deploy_results"]
        
        st.subheader("📊 Sonuçlar")
        
        for r in results:
            icon = "✅" if r.status == "OK" else "❌" if r.status == "FAIL" else "⏳"
            color = "green" if r.status == "OK" else "red" if r.status == "FAIL" else "orange"
            st.markdown(f":{color}[{icon} **{r.name}**] - {r.message}")
            
        # Summary
        ok_count = sum(1 for r in results if r.status == "OK")
        total = len(results)
        if ok_count == total:
            st.success(f"🎉 Deploy tamamlandı! Strateji Cloud'da çalışıyor.")
        else:
            st.warning(f"⚠️ {ok_count}/{total} adım tamamlandı.")
            
        # Artifacts
        st.subheader("📁 Deploy Bilgileri")
        
        for r in results:
            if r.data:
                if "strategy_id" in r.data:
                    st.text(f"Strategy ID: {r.data['strategy_id']}")
                if "status" in r.data:
                    st.text(f"Status: {r.data['status']}")
                if "ticks_done" in r.data:
                    st.text(f"Ticks Done: {r.data['ticks_done']}")
                    
    st.divider()
    
    # Events tail
    st.subheader("📜 Cloud Events")
    
    events_path = os.path.join(bus_root, "events", "cloud.ndjson")
    if os.path.exists(events_path):
        with open(events_path) as f:
            lines = f.readlines()[-10:]
        for line in reversed(lines):
            try:
                e = json.loads(line)
                st.text(f"{e.get('kind', '')} | {e.get('job_id', '')[:12]} | {e.get('strategy_id', '')}")
            except:
                pass
    else:
        st.info("Henüz event yok")
