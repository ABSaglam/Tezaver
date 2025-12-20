"""
MX-20002: Job Queue

Provides job claiming, result writing, and deadletter handling.
Uses atomic rename for claim safety on FS.
"""

import os
import json
import time
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
from tezaver.platform.bus.adapter import BusAdapter


@dataclass
class Job:
    """Job schema."""
    job_id: str
    job_type: str
    target: str  # Target agent: mac, matrix, cloud
    payload: Dict[str, Any]
    created_at: int
    priority: int = 50
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'Job':
        return cls(
            job_id=d["job_id"],
            job_type=d["job_type"],
            target=d["target"],
            payload=d.get("payload", {}),
            created_at=d.get("created_at", int(time.time())),
            priority=d.get("priority", 50),
        )


@dataclass
class JobResult:
    """Job result schema."""
    job_id: str
    status: str  # success, error
    result: Dict[str, Any]
    completed_at: int
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


def create_job(
    job_type: str,
    target: str,
    payload: Dict[str, Any],
    priority: int = 50,
) -> Job:
    """Create a new job with generated ID."""
    return Job(
        job_id=f"job_{uuid.uuid4().hex[:12]}",
        job_type=job_type,
        target=target,
        payload=payload,
        created_at=int(time.time()),
        priority=priority,
    )


def enqueue_job(bus: BusAdapter, job: Job) -> str:
    """Add job to inbox queue."""
    path = f"jobs/{job.target}/inbox/{job.job_id}.json"
    bus.put_json(path, job.to_dict())
    return job.job_id


def claim_next_job(bus: BusAdapter, target: str, max_n: int = 1) -> List[Job]:
    """
    Claim next job(s) from inbox.
    
    Uses atomic rename: inbox -> processing.
    Returns list of claimed jobs.
    """
    inbox_prefix = f"jobs/{target}/inbox"
    items = bus.list(inbox_prefix)
    
    claimed = []
    for item in items[:max_n]:
        if not item.endswith(".json"):
            continue
            
        # Get job data
        job_data = bus.get_json(item)
        if not job_data:
            continue
            
        job = Job.from_dict(job_data)
        
        # Atomic move: delete from inbox, write to processing
        processing_path = f"jobs/{target}/processing/{job.job_id}.json"
        bus.put_json(processing_path, job.to_dict())
        bus.delete(item)
        
        claimed.append(job)
        
    return claimed


def write_result(bus: BusAdapter, target: str, job_id: str, result: Dict, status: str = "success") -> None:
    """Write job result to outbox."""
    job_result = JobResult(
        job_id=job_id,
        status=status,
        result=result,
        completed_at=int(time.time()),
    )
    
    # Write to outbox
    outbox_path = f"jobs/{target}/outbox/{job_id}.json"
    bus.put_json(outbox_path, job_result.to_dict())
    
    # Remove from processing
    processing_path = f"jobs/{target}/processing/{job_id}.json"
    bus.delete(processing_path)
    
    # Append to events log
    bus.append_ndjson(f"events/{target}.ndjson", {
        "ts": int(time.time()),
        "kind": "JOB_COMPLETED",
        "job_id": job_id,
        "status": status,
    })


def write_deadletter(bus: BusAdapter, target: str, job_id: str, reason: str) -> None:
    """Move job to deadletter queue."""
    processing_path = f"jobs/{target}/processing/{job_id}.json"
    job_data = bus.get_json(processing_path)
    
    if job_data:
        job_data["deadletter_reason"] = reason
        job_data["deadletter_at"] = int(time.time())
        
        deadletter_path = f"jobs/{target}/deadletter/{job_id}.json"
        bus.put_json(deadletter_path, job_data)
        bus.delete(processing_path)
        
        bus.append_ndjson(f"events/{target}.ndjson", {
            "ts": int(time.time()),
            "kind": "JOB_DEADLETTER",
            "job_id": job_id,
            "reason": reason,
        })


def list_jobs(bus: BusAdapter, target: str, queue: str = "inbox") -> List[Dict]:
    """List jobs in queue (inbox/processing/outbox/deadletter)."""
    prefix = f"jobs/{target}/{queue}"
    items = bus.list(prefix)
    
    jobs = []
    for item in items:
        if item.endswith(".json"):
            data = bus.get_json(item)
            if data:
                jobs.append(data)
                
    return jobs
