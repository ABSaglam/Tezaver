"""
MX-23001: Panel Golden Wizard

One-click 7-step pipeline UI for Platform.
Panel does NOT import engine - uses HTTP + Bus only.
"""

import streamlit as st
import os
import json
import time
import uuid
from urllib.request import urlopen, Request
from urllib.error import URLError
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


def run_golden_flow(
    bus_root: str,
    mac_url: str, mac_token: str,
    matrix_url: str, matrix_token: str,
    cloud_url: str, cloud_token: str,
    progress_callback=None,
) -> List[StepResult]:
    """
    Run full Golden E2E 7-step flow.
    
    Returns list of StepResult for each step.
    """
    bus = FsBusAdapter(bus_root)
    results = []
    
    def update(step: StepResult):
        results.append(step)
        if progress_callback:
            progress_callback(results)
    
    # Step 1: Mac Build Candidate
    update(StepResult("1. Mac Build Candidate", "RUNNING"))
    try:
        job_id = enqueue_job(bus, "mac", "MAC_BUILD_CANDIDATE", {
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "params": {"entry": "breakout"},
        })
        scan_agent(mac_url, mac_token)
        result = get_outbox_result(bus, "mac", job_id)
        
        if result and result.get("result", {}).get("ok"):
            candidate_id = result["result"]["candidate_id"]
            artifact_path = result["result"]["artifact_path"]
            results[-1] = StepResult("1. Mac Build Candidate", "OK", f"candidate_id={candidate_id}", {"candidate_id": candidate_id, "artifact_path": artifact_path})
        else:
            results[-1] = StepResult("1. Mac Build Candidate", "FAIL", "No result")
            return results
    except Exception as e:
        results[-1] = StepResult("1. Mac Build Candidate", "FAIL", str(e))
        return results
        
    # Step 2: Matrix Import
    update(StepResult("2. Matrix Import", "RUNNING"))
    try:
        job_id = enqueue_job(bus, "matrix", "MATRIX_IMPORT_CANDIDATE", {
            "artifact_path": artifact_path,
        })
        scan_agent(matrix_url, matrix_token)
        result = get_outbox_result(bus, "matrix", job_id)
        
        if result and result.get("result", {}).get("ok"):
            results[-1] = StepResult("2. Matrix Import", "OK", f"Imported {candidate_id}")
        else:
            results[-1] = StepResult("2. Matrix Import", "FAIL", str(result))
            return results
    except Exception as e:
        results[-1] = StepResult("2. Matrix Import", "FAIL", str(e))
        return results
        
    # Step 3: Matrix Sniper
    update(StepResult("3. Matrix Sniper", "RUNNING"))
    try:
        job_id = enqueue_job(bus, "matrix", "MATRIX_RUN_SNIPER", {
            "candidate_id": candidate_id,
        })
        scan_agent(matrix_url, matrix_token)
        result = get_outbox_result(bus, "matrix", job_id)
        
        if result and result.get("result", {}).get("ok"):
            run_id = result["result"]["run_id"]
            verdict = result["result"]["verdict"]
            results[-1] = StepResult("3. Matrix Sniper", "OK", f"{verdict} - run_id={run_id}", {"run_id": run_id, "verdict": verdict})
        else:
            results[-1] = StepResult("3. Matrix Sniper", "FAIL", str(result))
            return results
    except Exception as e:
        results[-1] = StepResult("3. Matrix Sniper", "FAIL", str(e))
        return results
        
    # Step 4: Matrix Approve Export
    update(StepResult("4. Matrix Approve/Export", "RUNNING"))
    try:
        job_id = enqueue_job(bus, "matrix", "MATRIX_APPROVE_EXPORT", {
            "candidate_id": candidate_id,
            "export": True,
        })
        scan_agent(matrix_url, matrix_token)
        result = get_outbox_result(bus, "matrix", job_id)
        
        if result and result.get("result", {}).get("ok"):
            export_path = result["result"].get("bus_export_path") or result["result"].get("export_path")
            results[-1] = StepResult("4. Matrix Approve/Export", "OK", f"export={export_path}", {"export_path": export_path})
        else:
            results[-1] = StepResult("4. Matrix Approve/Export", "FAIL", str(result))
            return results
    except Exception as e:
        results[-1] = StepResult("4. Matrix Approve/Export", "FAIL", str(e))
        return results
        
    # Step 5: Cloud Import Strategy
    update(StepResult("5. Cloud Import Strategy", "RUNNING"))
    try:
        job_id = enqueue_job(bus, "cloud", "CLOUD_IMPORT_STRATEGY", {
            "export_path": export_path,
        })
        scan_agent(cloud_url, cloud_token)
        result = get_outbox_result(bus, "cloud", job_id)
        
        if result and result.get("result", {}).get("ok"):
            strategy_id = result["result"]["strategy_id"]
            status = result["result"]["status"]
            results[-1] = StepResult("5. Cloud Import Strategy", "OK", f"{strategy_id} ({status})", {"strategy_id": strategy_id, "status": status})
        else:
            results[-1] = StepResult("5. Cloud Import Strategy", "FAIL", str(result))
            return results
    except Exception as e:
        results[-1] = StepResult("5. Cloud Import Strategy", "FAIL", str(e))
        return results
        
    # Step 6: Cloud Set ACTIVE
    update(StepResult("6. Cloud Activate", "RUNNING"))
    try:
        job_id = enqueue_job(bus, "cloud", "CLOUD_SET_STATUS", {
            "strategy_id": strategy_id,
            "status": "ACTIVE",
        })
        scan_agent(cloud_url, cloud_token)
        result = get_outbox_result(bus, "cloud", job_id)
        
        if result and result.get("result", {}).get("ok"):
            results[-1] = StepResult("6. Cloud Activate", "OK", f"{strategy_id} → ACTIVE")
        else:
            results[-1] = StepResult("6. Cloud Activate", "FAIL", str(result))
            return results
    except Exception as e:
        results[-1] = StepResult("6. Cloud Activate", "FAIL", str(e))
        return results
        
    # Step 7: Cloud Tick
    update(StepResult("7. Cloud Tick (x2)", "RUNNING"))
    try:
        job_id = enqueue_job(bus, "cloud", "CLOUD_RUNTIME_TICK", {
            "ticks": 2,
        })
        scan_agent(cloud_url, cloud_token)
        result = get_outbox_result(bus, "cloud", job_id)
        
        if result and result.get("result", {}).get("ok"):
            ticks_done = result["result"]["ticks_done"]
            results[-1] = StepResult("7. Cloud Tick (x2)", "OK", f"{ticks_done} ticks done", {"ticks_done": ticks_done})
        else:
            results[-1] = StepResult("7. Cloud Tick (x2)", "FAIL", str(result))
            return results
    except Exception as e:
        results[-1] = StepResult("7. Cloud Tick (x2)", "FAIL", str(e))
        return results
        
    return results


def render_platform_golden():
    """Render Platform Golden Wizard page."""
    st.header("🏆 Golden E2E Wizard")
    st.caption("Tek tıkla 7 adımlık tam pipeline testi")
    
    # Get config from session
    bus_root = st.session_state.get("platform_bus_root", ".tezaver_bus")
    mac_url = st.session_state.get("mac_url", "http://127.0.0.1:9001")
    mac_token = st.session_state.get("mac_token", "MAC_TOKEN")
    matrix_url = st.session_state.get("matrix_url", "http://127.0.0.1:9002")
    matrix_token = st.session_state.get("matrix_token", "MATRIX_TOKEN")
    cloud_url = st.session_state.get("cloud_url", "http://127.0.0.1:9003")
    cloud_token = st.session_state.get("cloud_token", "CLOUD_TOKEN")
    
    # Config display
    with st.expander("⚙️ Bağlantı Ayarları"):
        st.text(f"Bus Root: {bus_root}")
        st.text(f"Mac: {mac_url}")
        st.text(f"Matrix: {matrix_url}")
        st.text(f"Cloud: {cloud_url}")
        
    st.divider()
    
    # Run button
    if st.button("🚀 Golden E2E Çalıştır", type="primary", use_container_width=True):
        with st.spinner("Pipeline çalışıyor..."):
            results = run_golden_flow(
                bus_root,
                mac_url, mac_token,
                matrix_url, matrix_token,
                cloud_url, cloud_token,
            )
            st.session_state["golden_results"] = results
            
    # Results display
    if "golden_results" in st.session_state:
        results = st.session_state["golden_results"]
        
        st.subheader("📊 Sonuçlar")
        
        for r in results:
            icon = "✅" if r.status == "OK" else "❌" if r.status == "FAIL" else "⏳"
            color = "green" if r.status == "OK" else "red" if r.status == "FAIL" else "orange"
            st.markdown(f":{color}[{icon} **{r.name}**] - {r.message}")
            
        # Summary
        ok_count = sum(1 for r in results if r.status == "OK")
        if ok_count == 7:
            st.success("🎉 Tüm 7 adım başarılı! Pipeline tamam.")
        else:
            st.warning(f"⚠️ {ok_count}/7 adım tamamlandı.")
            
        # Artifacts
        st.subheader("📁 Üretilen Artifact'lar")
        
        for r in results:
            if r.data:
                if "artifact_path" in r.data:
                    st.text(f"Mac Candidate: {r.data['artifact_path']}")
                if "export_path" in r.data:
                    st.text(f"Matrix Export: {r.data['export_path']}")
                if "strategy_id" in r.data:
                    st.text(f"Cloud Strategy: {r.data['strategy_id']} ({r.data.get('status', '')})")
                if "ticks_done" in r.data:
                    st.text(f"Cloud Ticks: {r.data['ticks_done']}")
                    
    st.divider()
    
    # Events tail
    st.subheader("📜 Events Tail")
    
    bus = FsBusAdapter(bus_root)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Mac Events**")
        events_path = os.path.join(bus_root, "events", "mac.ndjson")
        if os.path.exists(events_path):
            with open(events_path) as f:
                lines = f.readlines()[-10:]
            for line in reversed(lines):
                try:
                    e = json.loads(line)
                    st.text(f"{e.get('kind', '')} | {e.get('job_id', '')[:12]}")
                except:
                    pass
        else:
            st.info("Henüz event yok")
            
    with col2:
        st.markdown("**Matrix Events**")
        events_path = os.path.join(bus_root, "events", "matrix.ndjson")
        if os.path.exists(events_path):
            with open(events_path) as f:
                lines = f.readlines()[-10:]
            for line in reversed(lines):
                try:
                    e = json.loads(line)
                    st.text(f"{e.get('kind', '')} | {e.get('job_id', '')[:12]}")
                except:
                    pass
        else:
            st.info("Henüz event yok")
            
    with col3:
        st.markdown("**Cloud Events**")
        events_path = os.path.join(bus_root, "events", "cloud.ndjson")
        if os.path.exists(events_path):
            with open(events_path) as f:
                lines = f.readlines()[-10:]
            for line in reversed(lines):
                try:
                    e = json.loads(line)
                    st.text(f"{e.get('kind', '')} | {e.get('job_id', '')[:12]}")
                except:
                    pass
        else:
            st.info("Henüz event yok")
