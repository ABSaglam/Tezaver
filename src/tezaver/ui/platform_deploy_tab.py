"""
MX-23003: Approved → Cloud Deploy Wizard

3-4 step flow: Import Strategy → Activate → Tick
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


def run_approved_deploy_flow(
    bus_root: str,
    export_path: str,
    cloud_url: str,
    cloud_token: str,
    activate: bool = True,
    ticks: int = 2,
) -> List[StepResult]:
    """
    Run Approved → Cloud Deploy flow (3-4 steps).
    
    Returns list of StepResult.
    """
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
    
    # Options
    st.subheader("⚙️ Deploy Ayarları")
    
    col1, col2 = st.columns(2)
    with col1:
        activate = st.checkbox("Aktifleştir (ACTIVE)", value=True)
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
    
    # Release Gate / Rehearsal info (if available)
    st.subheader("🚦 Release Gate / Rehearsal")
    col1, col2 = st.columns(2)
    with col1:
        st.info("Release Gate: N/A (ileride)")
    with col2:
        st.info("Rehearsal: N/A (ileride)")
    
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
