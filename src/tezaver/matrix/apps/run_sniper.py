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

def main():
    parser = argparse.ArgumentParser(description="Matrix Sniper Runner (MX-8002)")
    parser.add_argument("--candidate-id", required=True, help="Candidate ID")
    parser.add_argument("--bars", required=True, help="Path to bars.json")
    parser.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"), help="Matrix Home")
    
    args = parser.parse_args()
    
    # 1. Load Candidate
    # Pass home explicitly if provided, otherwise it defaults to env or default
    c_store = FileCandidateStore(home=args.home)
    # Also set env for other components that might rely on it implicitly (good practice)
    if args.home:
        os.environ["TEZAVER_MATRIX_HOME"] = args.home
        
    candidate = c_store.load(args.candidate_id)
    if not candidate:
        print(f"Candidate not found: {args.candidate_id}")
        sys.exit(2)
        
    # 2. Setup Ports
    # Data:
    if not os.path.exists(args.bars):
        print(f"Bars file not found: {args.bars}")
        sys.exit(2)
    data_port = JsonFileDataPort(args.bars)
    
    # Broker:
    broker_port = SimBroker()
    
    # Store:
    store_port = FileRunStore(args.home)
    
    # 3. Configs
    # Trace
    trace = TraceIds(
        engine_version="v4-dev",
        data_fingerprint=f"bars_{os.path.basename(args.bars)}",
        config_signature="sniper-demo"
    )
    
    # Gov: Allow listing
    gov_cfg = GovernanceConfig(
        allowlist=[candidate.get("symbol")],
        max_age_seconds=999999999 # No staleness check for demo
    )
    
    # Risk
    risk_cfg = RiskGateConfig() # Defaults
    
    # 4. Run Cycle (SNIPER Profile)
    # We need symbol, timeframe from candidate.
    sym = candidate.get("symbol")
    tf = candidate.get("timeframe")
    build_ts = candidate.get("build_ts")
    
    if not sym or not tf:
        print("Invalid candidate data")
        sys.exit(2)
        
    print(f"Running SNIPER for {args.candidate_id}...")
    
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
        home=args.home,
        run_profile="SNIPER"
    )
    
    rid = meta.get("run_id")
    print(f"Run Complete. ID: {rid}")
    
    # 5. Check Verdict
    # Read judge.json
    try:
        jpath = os.path.join(args.home, "runs", rid, "judge.json")
        with open(jpath, "r") as f:
            j = json.load(f)
            verdict = j.get("overall", "UNKNOWN")
            print(f"Verdict: {verdict}")
            
            if verdict == "PASS":
                sys.exit(0)
            elif verdict == "IMPROVE":
                sys.exit(1)
            else:
                sys.exit(2)
    except Exception as e:
        print(f"Error reading verdict: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()
