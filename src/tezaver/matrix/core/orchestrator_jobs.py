from typing import List, Dict
from tezaver.matrix.apps.run_sniper import run_sniper_once
from tezaver.matrix.apps.run_war import run_war_once
# For Live, we use live_step from live_engine directly?
# But we need adapter to match payload.
from tezaver.matrix.core.live_engine import live_step, start_live_run
from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore
from tezaver.matrix.adapters.data_port_json import JsonFileDataPort
from tezaver.matrix.adapters.broker_sim import SimBroker
from tezaver.matrix.adapters.store_run_fs import FileRunStore
from tezaver.matrix.core.trace import TraceIds
from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig
import os

def resource_locks_for_job(job) -> List[str]:
    p = job.payload
    if job.type == "LIVE_STEP":
        # Lock by Run ID to prevent concurrent steps
        return [f"run:{p.get('run_id')}"]
    elif job.type == "SNIPER":
        # Lock by Candidate ID?
        return [f"candidate:{p.get('candidate_id')}"]
    elif job.type == "WAR":
        # Global WAR lock or session?
        # Lock candidates folder?
        return ["war_global"]
    return []

def execute_job(home: str, job) -> Dict:
    p = job.payload
    
    if job.type == "SNIPER":
        return run_sniper_once(home, p.get("candidate_id"), p.get("bars_path"))
        
    elif job.type == "WAR":
        return run_war_once(home, p.get("candidates_dir"), p.get("bars_dir"), p.get("limit", 0))
        
    elif job.type == "LIVE_STEP":
        # Requires adapter to load components like run_live main does
        run_id = p.get("run_id")
        steps = p.get("steps", 1)
        bars_path = p.get("bars_path")
        candidate_id = p.get("candidate_id", "UNKNOWN")
        
        # We need symbol/tf from run meta if not provided?
        # run_live main loads candidate to get them.
        # But for step, we can load from meta.
        
        # Load meta
        meta_path = os.path.join(home, "runs", run_id, "meta.json")
        if os.path.exists(meta_path):
            import json
            with open(meta_path) as f: meta = json.load(f)
            sym = meta["candidate"]["symbol"]
            tf = meta["candidate"]["timeframe"]
        else:
            # Maybe provided in payload?
            sym = p.get("symbol")
            tf = p.get("timeframe")
            if not sym or not tf:
                raise ValueError("Cannot determine symbol/timeframe for LIVE step (no meta)")

        # Prepare components
        data = JsonFileDataPort(bars_path)
        broker = SimBroker()
        store = FileRunStore(home)
        
        trace = TraceIds(
            engine_version="v4-live",
            data_fingerprint=f"file:{os.path.basename(bars_path)}",
            config_signature="live-orch"
        )
        
        gov_cfg = GovernanceConfig(allowlist=[sym], max_age_seconds=999999999)
        risk_cfg = RiskGateConfig()
        
        summary = live_step(
            home=home,
            run_id=run_id,
            steps=steps,
            symbol=sym,
            timeframe=tf,
            trace_ids=trace,
            data=data,
            broker=broker,
            store=store,
            gov_cfg=gov_cfg,
            risk_cfg=risk_cfg,
            candidate_id=candidate_id
        )
        return summary
        
    raise ValueError(f"Unknown job type: {job.type}")
