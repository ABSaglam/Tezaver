"""
MX-23002: Candidate → Sniper Wizard

2-step flow: Import Candidate → Run Sniper
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


def list_candidate_artifacts(bus: FsBusAdapter, prefix: str = "artifacts/mac/candidates/") -> List[str]:
    """List candidate artifacts in bus."""
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


def run_candidate_sniper_flow(
    bus_root: str,
    artifact_path: str,
    matrix_url: str,
    matrix_token: str,
) -> List[StepResult]:
    """
    Run Candidate → Sniper flow (2 steps).
    
    Returns list of StepResult.
    """
    bus = FsBusAdapter(bus_root)
    results = []
    
    # Step 1: Matrix Import
    results.append(StepResult("1. Matrix Import", "RUNNING"))
    try:
        job_id = enqueue_job(bus, "matrix", "MATRIX_IMPORT_CANDIDATE", {
            "artifact_path": artifact_path,
        })
        scan_agent(matrix_url, matrix_token)
        result = get_outbox_result(bus, "matrix", job_id)
        
        if result and result.get("result", {}).get("ok"):
            candidate_id = result["result"]["candidate_id"]
            results[-1] = StepResult("1. Matrix Import", "OK", f"Imported {candidate_id}", {"candidate_id": candidate_id})
        else:
            error = result.get("result", {}).get("error_detail_tr", "Unknown error") if result else "No response"
            results[-1] = StepResult("1. Matrix Import", "FAIL", error)
            return results
    except Exception as e:
        results[-1] = StepResult("1. Matrix Import", "FAIL", str(e))
        return results
        
    # Step 2: Matrix Sniper
    results.append(StepResult("2. Matrix Sniper", "RUNNING"))
    try:
        job_id = enqueue_job(bus, "matrix", "MATRIX_RUN_SNIPER", {
            "candidate_id": candidate_id,
        })
        scan_agent(matrix_url, matrix_token)
        result = get_outbox_result(bus, "matrix", job_id)
        
        if result and result.get("result", {}).get("ok"):
            run_id = result["result"]["run_id"]
            verdict = result["result"]["verdict"]
            scorecard_path = result["result"].get("scorecard_path")
            results[-1] = StepResult("2. Matrix Sniper", "OK", f"{verdict}", {
                "run_id": run_id,
                "verdict": verdict,
                "scorecard_path": scorecard_path,
            })
        else:
            error = result.get("result", {}).get("error_detail_tr", "Unknown error") if result else "No response"
            results[-1] = StepResult("2. Matrix Sniper", "FAIL", error)
            return results
    except Exception as e:
        results[-1] = StepResult("2. Matrix Sniper", "FAIL", str(e))
        return results
        
    return results


def render_platform_sniper():
    """Render Candidate → Sniper Wizard page."""
    st.header("🎯 Candidate → Sniper Wizard")
    st.caption("Import candidate ve Sniper test çalıştır")
    
    # Get config from session
    bus_root = st.session_state.get("platform_bus_root", ".tezaver_bus")
    matrix_url = st.session_state.get("matrix_url", "http://127.0.0.1:9002")
    matrix_token = st.session_state.get("matrix_token", "MATRIX_TOKEN")
    
    bus = FsBusAdapter(bus_root)
    
    # Source selection
    st.subheader("📦 Candidate Kaynağı")
    
    source_mode = st.radio("Kaynak Seç", ["Bus'tan Seç", "Elle Path Gir"], horizontal=True)
    
    artifact_path = None
    
    if source_mode == "Bus'tan Seç":
        candidates = list_candidate_artifacts(bus)
        if candidates:
            artifact_path = st.selectbox("Candidate Artifact", candidates)
        else:
            st.warning("⚠️ Bus'ta candidate artifact yok. Önce Mac Agent ile candidate oluşturun.")
    else:
        artifact_path = st.text_input("Artifact Path", "artifacts/mac/candidates/")
        
    st.divider()
    
    # Run button
    if artifact_path and st.button("🚀 Import + Sniper Çalıştır", type="primary", use_container_width=True):
        with st.spinner("Flow çalışıyor..."):
            results = run_candidate_sniper_flow(
                bus_root,
                artifact_path,
                matrix_url,
                matrix_token,
            )
            st.session_state["sniper_results"] = results
            
    # Results display
    if "sniper_results" in st.session_state:
        results = st.session_state["sniper_results"]
        
        st.subheader("📊 Sonuçlar")
        
        for r in results:
            icon = "✅" if r.status == "OK" else "❌" if r.status == "FAIL" else "⏳"
            color = "green" if r.status == "OK" else "red" if r.status == "FAIL" else "orange"
            st.markdown(f":{color}[{icon} **{r.name}**] - {r.message}")
            
        # Summary
        ok_count = sum(1 for r in results if r.status == "OK")
        if ok_count == 2:
            # Get verdict
            sniper_result = next((r for r in results if r.data and "verdict" in r.data), None)
            if sniper_result:
                verdict = sniper_result.data["verdict"]
                if verdict == "PASS":
                    st.success(f"🎉 Sniper Test PASS! Candidate onaylandı.")
                else:
                    st.error(f"❌ Sniper Test FAIL! Candidate reddedildi.")
        else:
            st.warning(f"⚠️ {ok_count}/2 adım tamamlandı.")
            
        # Artifacts
        st.subheader("📁 Artifact'lar")
        
        for r in results:
            if r.data:
                if "candidate_id" in r.data:
                    st.text(f"Candidate ID: {r.data['candidate_id']}")
                if "run_id" in r.data:
                    st.text(f"Run ID: {r.data['run_id']}")
                if "scorecard_path" in r.data:
                    st.text(f"Scorecard: {r.data['scorecard_path']}")
                    
    st.divider()
    
    # Events tail
    st.subheader("📜 Matrix Events")
    
    events_path = os.path.join(bus_root, "events", "matrix.ndjson")
    if os.path.exists(events_path):
        with open(events_path) as f:
            lines = f.readlines()[-10:]
        for line in reversed(lines):
            try:
                e = json.loads(line)
                st.text(f"{e.get('kind', '')} | {e.get('job_id', '')[:12]} | {e.get('candidate_id', '')}")
            except:
                pass
    else:
        st.info("Henüz event yok")
