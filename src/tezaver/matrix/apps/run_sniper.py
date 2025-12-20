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
    
    trace = TraceIds(
        engine_version="v4-dev",
        data_fingerprint=f"bars_{os.path.basename(bars_path)}",
        config_signature="sniper-demo"
    )
    
    gov_cfg = GovernanceConfig(allowlist=[candidate.get("symbol")], max_age_seconds=999999999)
    risk_cfg = RiskGateConfig()
    
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
