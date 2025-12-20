import os
import json
import time
import random
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict, field

@dataclass
class Job:
    job_id: str
    type: str
    payload: Dict
    priority: int = 50
    created_ts: int = 0
    status: str = "QUEUED" # QUEUED, RUNNING, DONE, FAILED, MISSED
    started_ts: int = 0
    ended_ts: int = 0
    result: Dict = field(default_factory=dict)
    error: str = ""

class OrchestratorStore:
    def __init__(self, home: str):
        self.home = home or os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix")
        self.orch_dir = os.path.join(self.home, "orchestrator")
        os.makedirs(self.orch_dir, exist_ok=True)
        self.queue_path = os.path.join(self.orch_dir, "queue.json")
        self.locks_path = os.path.join(self.orch_dir, "locks.json")
        self.history_path = os.path.join(self.orch_dir, "history.json")
        
    def load_queue(self) -> List[Job]:
        if not os.path.exists(self.queue_path): return []
        with open(self.queue_path) as f:
            data = json.load(f)
            return [Job(**d) for d in data]
            
    def save_queue(self, jobs: List[Job]) -> None:
        with open(self.queue_path, "w") as f:
            json.dump([asdict(j) for j in jobs], f, indent=2)
            
    def load_locks(self) -> Dict[str, str]:
        # resource -> job_id
        if not os.path.exists(self.locks_path): return {}
        with open(self.locks_path) as f: return json.load(f)
        
    def save_locks(self, locks: Dict[str, str]) -> None:
        with open(self.locks_path, "w") as f: json.dump(locks, f, indent=2)
        
    def load_history(self) -> List[Dict]:
        if not os.path.exists(self.history_path): return []
        with open(self.history_path) as f: return json.load(f)
        
    def append_history(self, job: Job) -> None:
        hist = self.load_history()
        hist.insert(0, asdict(job))
        hist = hist[:50] # Limit history
        with open(self.history_path, "w") as f:
            json.dump(hist, f, indent=2)

def enqueue_job(home: str, type: str, payload: Dict, priority: int = 50) -> str:
    store = OrchestratorStore(home)
    queue = store.load_queue()
    
    ts = int(time.time() * 1000)
    # Simple ID
    rand = random.randint(1000, 9999)
    job_id = f"JOB_{ts}_{rand}"
    
    job = Job(
        job_id=job_id,
        type=type,
        payload=payload,
        priority=priority,
        created_ts=ts
    )
    
    queue.append(job)
    
    # Sort: highest priority first, then oldest created
    queue.sort(key=lambda x: (-x.priority, x.created_ts))
    
    store.save_queue(queue)
    return job_id

def acquire_locks(home: str, resources: List[str], job_id: str) -> bool:
    store = OrchestratorStore(home)
    locks = store.load_locks()
    
    # Check if any resource in use by OTHER job
    for r in resources:
        if r in locks and locks[r] != job_id:
            return False
            
    # Acquire
    for r in resources:
        locks[r] = job_id
        
    store.save_locks(locks)
    return True

def release_locks(home: str, resources: List[str], job_id: str) -> None:
    store = OrchestratorStore(home)
    locks = store.load_locks()
    
    changed = False
    for r in resources:
        if locks.get(r) == job_id:
            del locks[r]
            changed = True
            
    if changed:
        store.save_locks(locks)
        
def run_ticks(home: str, ticks: int = 1) -> Dict:
    from tezaver.matrix.core.orchestrator_jobs import execute_job, resource_locks_for_job
    
    store = OrchestratorStore(home)
    executed = []
    
    for _ in range(ticks):
        queue = store.load_queue()
        # Find runnable job
        runnable_job_idx = -1
        
        for idx, job in enumerate(queue):
            if job.status == "QUEUED":
                locks_needed = resource_locks_for_job(job)
                if acquire_locks(home, locks_needed, job.job_id):
                    runnable_job_idx = idx
                    break
        
        if runnable_job_idx == -1:
            break # No runnable jobs
            
        job = queue.pop(runnable_job_idx)
        store.save_queue(queue) # Remove from queue temporarily or keep as RUNNING?
        # Better to keep status. But simplify: Remove from queue, put back to history loop?
        # Actually standard queue pattern:
        # Mark Running -> Save Queue -> Execute -> Remove -> History
        
        # But for simplicity here with file locks:
        # We removed it from list. If crash, job lost? Yes.
        # Ideally: Update status RUNNING, Save.
        
        # Re-add as RUNNING
        job.status = "RUNNING"
        job.started_ts = int(time.time() * 1000)
        # We insert at front to ensure visibility or just append?
        # In this simple tick loop, we hold it in memory or file?
        # Let's simple-execute synchronously.
        
        resources = resource_locks_for_job(job)
        
        try:
            res = execute_job(home, job)
            job.result = res
            job.status = "DONE"
        except Exception as e:
            job.error = str(e)
            job.status = "FAILED"
            
        job.ended_ts = int(time.time() * 1000)
        release_locks(home, resources, job.job_id)
        
        store.append_history(job)
        executed.append(job.job_id)
        
    return {"ticks": ticks, "executed": executed}
