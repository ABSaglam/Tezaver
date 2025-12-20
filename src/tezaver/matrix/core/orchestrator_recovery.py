import os
import json
import time
from typing import Dict, List, Set
from tezaver.matrix.core.orchestrator import OrchestratorStore, Job

def recover_orchestrator_state(home: str) -> Dict:
    store = OrchestratorStore(home)
    queue = store.load_queue()
    locks = store.load_locks()
    
    requeued_count = 0
    active_job_ids: Set[str] = set()
    
    # 1. Requeue RUNNING jobs
    new_queue: List[Job] = []
    for job in queue:
        job_obj = job # Job dataclass
        # Actually store.load_queue returns list of dicts in current impl?
        # Let's check OrchestratorStore.load_queue in orchestrator.py
        # It returns List[Job].
        
        if job_obj.status == "RUNNING":
            job_obj.status = "QUEUED"
            requeued_count += 1
            
        if job_obj.status in ("QUEUED", "RUNNING"):
            active_job_ids.add(job_obj.job_id)
            
        new_queue.append(job_obj)
        
    if requeued_count > 0:
        store.save_queue(new_queue)
        
    # 2. Clear Stale Locks
    # Stale: lock.job_id is NOT in active_job_ids
    # Also we can check expiry if we had it, but mostly we care about ownership validity.
    
    new_locks = {}
    stale_removed = 0
    
    for res_key, lock_info in locks.items():
        # lock_info is dict: {job_id, type, timestamp}
        jid = lock_info.get("job_id")
        if jid in active_job_ids:
            new_locks[res_key] = lock_info
        else:
            stale_removed += 1
            
    if stale_removed > 0:
        store.save_locks(new_locks)
        
    return {
        "requeued": requeued_count,
        "stale_locks_removed": stale_removed
    }
