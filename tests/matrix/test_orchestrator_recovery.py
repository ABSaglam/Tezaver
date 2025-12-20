import os
import json
import pytest
from tezaver.matrix.core.orchestrator import OrchestratorStore, Job
from tezaver.matrix.core.orchestrator_recovery import recover_orchestrator_state

def test_orchestrator_recovery(tmp_path):
    home = str(tmp_path)
    store = OrchestratorStore(home)
    
    # Setup
    j1 = Job(job_id="J1", type="TEST", priority=10, status="RUNNING", payload={})
    j2 = Job(job_id="J2", type="TEST", priority=10, status="QUEUED", payload={})
    store.save_queue([j1, j2])
    
    locks = {
        "R1": {"job_id": "J1", "type": "TEST", "ts": 100},
        "R2": {"job_id": "GHOST", "type": "TEST", "ts": 100} # Ghost job (not in queue)
    }
    store.save_locks(locks)
    
    # Recover
    rep = recover_orchestrator_state(home)
    
    assert rep["requeued"] == 1
    assert rep["stale_locks_removed"] == 1
    
    # Verify State
    q = store.load_queue()
    assert q[0].job_id == "J1"
    assert q[0].status == "QUEUED" # Was RUNNING
    
    l = store.load_locks()
    assert "R1" in l # J1 is still active (queued)
    assert "R2" not in l # Ghost removed
