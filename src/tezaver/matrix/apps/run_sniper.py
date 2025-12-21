import argparse
import sys
import os
import json
import time

from tezaver.matrix.core.cycle_engine import run_cycle
from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore
from tezaver.matrix.adapters.data_port_json import JsonFileDataPort
from tezaver.matrix.adapters.broker_sim import SimBroker
from tezaver.matrix.adapters.store_run_fs import FileRunStore
from tezaver.matrix.core.trace import TraceIds
from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig

def run_sniper_once(home: str, candidate_id: str, bars_path: str) -> dict:
    home = home or os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix")
    if home: os.environ["TEZAVER_MATRIX_HOME"] = home
    
    # 1. Load Candidate
    c_store = FileCandidateStore(home=home)
    candidate = c_store.load(candidate_id)
    if not candidate:
        return {"error": f"Candidate not found: {candidate_id}", "status": "FAIL"}
        
    if not os.path.exists(bars_path):
        return {"error": f"Bars file not found: {bars_path}", "status": "FAIL"}
        
    # 2. Setup
    data_port = JsonFileDataPort(bars_path)
    broker_port = SimBroker()
    store_port = FileRunStore(home)

    # Risk & Governance Configs (needed for signature)
    gov_cfg = GovernanceConfig(allowlist=[candidate.get("symbol")], max_age_seconds=999999999)
    risk_cfg = RiskGateConfig() # Defaults
    
    # Config Signature (MX-10002)
    from tezaver.matrix.core.config_signature import ConfigSpec, compute_config_signature
    from dataclasses import asdict
    
    cspec = ConfigSpec(
        run_profile="SNIPER",
        symbol=candidate.get("symbol"),
        timeframe=candidate.get("timeframe"),
        risk=asdict(risk_cfg),
        governance=asdict(gov_cfg)
    )
    sig = compute_config_signature(cspec)

    # 3. Configs
    # Trace
    trace = TraceIds(
        engine_version="v4-dev",
        data_fingerprint=f"bars_{os.path.basename(bars_path)}",
        config_signature=sig
    )
    
    sym = candidate.get("symbol")
    tf = candidate.get("timeframe")
    build_ts = candidate.get("build_ts")
    
    if not sym or not tf:
        return {"error": "Invalid candidate data", "status": "FAIL"}
        
    # Run
    meta = run_cycle(
        symbol=sym,
        timeframe=tf,
        candidate_build_ts=build_ts,
        trace_ids=trace,
        data=data_port,
        broker=broker_port,
        store=store_port,
        risk_cfg=risk_cfg,
        gov_cfg=gov_cfg,
        home=home,
        run_profile="SNIPER"
    )
    
    rid = meta.get("run_id")
    
    # Verdict
    try:
        jpath = os.path.join(home, "runs", rid, "judge.json")
        with open(jpath, "r") as f:
            j = json.load(f)
            verdict = j.get("overall", "UNKNOWN")
            
        stage = "UNKNOWN"
        # Optional: check stage from file side effect
        
        return {
            "run_id": rid,
            "verdict": verdict,
            "status": "DONE" if verdict == "PASS" else "FAIL" # Simplified status for job
        }
    except Exception as e:
        return {"run_id": rid, "error": str(e), "status": "FAIL"}
def run_sniper_stub(home: str, candidate_id: str) -> str:
    """
    MXI-1040: Stub Sniper Run implementation.
    TR: Sahte Sniper çalışması (Stub). UI akışını test etmek için kanal üretir.
    """
    import os
    import json
    import time
    from datetime import datetime
    import hashlib
    
    run_id = f"run_sniper_{int(time.time())}"
    run_dir = os.path.join(home, "runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    
    # 1. Telemetry logs (MXI-1040)
    telemetry_path = os.path.join(run_dir, "telemetry.ndjson")
    
    events = [
        {
            "ts": datetime.now().isoformat(),
            "event_type": "RUN_STARTED",
            "run_id": run_id,
            "trace": {"candidate_id": candidate_id, "engine_version": "v4-stub"},
            "payload": {"msg": "Sniper run started from candidate"}
        },
        {
            "ts": datetime.now().isoformat(),
            "event_type": "RUN_FINISHED",
            "run_id": run_id,
            "trace": {"candidate_id": candidate_id},
            "payload": {"verdict": "PASS", "pnl": 0.05}
        },
        {
            "ts": datetime.now().isoformat(),
            "event_type": "REPORT_CREATED",
            "run_id": run_id,
            "trace": {"candidate_id": candidate_id},
            "payload": {"report_path": "judge.json"}
        }
    ]
    
    with open(telemetry_path, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
            
    # 2. Evidence (Kanıtlar)
    judge_data = {
        "run_id": run_id,
        "candidate_id": candidate_id,
        "overall": "PASS",
        "pnl_pct": 5.2,
        "trade_count": 1,
        "msg": "STUB RUN COMPLETE (SUCCESS)"
    }
    with open(os.path.join(run_dir, "judge.json"), "w") as f:
        json.dump(judge_data, f, indent=2)
        
    return run_id

def main():
    parser = argparse.ArgumentParser(description="Matrix Sniper Runner (MX-8002)")
    parser.add_argument("--candidate-id", required=True, help="Candidate ID")
    parser.add_argument("--bars", required=True, help="Path to bars.json")
    parser.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"), help="Matrix Home")
    
    args = parser.parse_args()
    
    res = run_sniper_once(args.home, args.candidate_id, args.bars)
    
    if "error" in res:
        print(f"Error: {res['error']}")
        sys.exit(2)
        
    print(f"Run Complete. ID: {res['run_id']}")
    print(f"Verdict: {res.get('verdict')}")
    
    if res.get('verdict') == "PASS":
        sys.exit(0)
    elif res.get('verdict') == "IMPROVE":
        sys.exit(1)
    else:
        sys.exit(2)

if __name__ == "__main__":
    main()
