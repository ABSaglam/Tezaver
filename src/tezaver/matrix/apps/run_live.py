import argparse
import sys
import os
import json
import time

from tezaver.matrix.core.live_engine import start_live_run, live_step, load_live_state
from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore
from tezaver.matrix.adapters.data_port_json import JsonFileDataPort
from tezaver.matrix.adapters.broker_sim import SimBroker
from tezaver.matrix.adapters.store_run_fs import FileRunStore
from tezaver.matrix.core.trace import TraceIds
from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig

def main():
    parser = argparse.ArgumentParser(description="Matrix Live Runner (MX-8004)")
    parser.add_argument("--candidate-id", required=True, help="Candidate ID")
    parser.add_argument("--bars", required=True, help="Path to bars.json")
    parser.add_argument("--steps", type=int, default=50, help="Number of steps to process")
    parser.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"), help="Matrix Home")
    parser.add_argument("--run-id", help="Resume existing run ID")
    
    args = parser.parse_args()
    
    if args.home:
        os.environ["TEZAVER_MATRIX_HOME"] = args.home
        
    print(f"Live Runner for {args.candidate_id} (Steps: {args.steps})")
    
    # 1. Load Candidate
    c_store = FileCandidateStore(home=args.home)
    try:
        candidate = c_store.load(args.candidate_id)
    except FileNotFoundError:
        print(f"Candidate {args.candidate_id} not found")
        sys.exit(2)
        
    # 2. Setup Components
    data = JsonFileDataPort(args.bars)
    broker = SimBroker()
    store = FileRunStore(args.home)
    
    trace = TraceIds(
        engine_version="v4-live",
        data_fingerprint=f"file:{os.path.basename(args.bars)}",
        config_signature=f"live-cli"
    )
    
    gov_cfg = GovernanceConfig(allowlist=[candidate["symbol"]], max_age_seconds=999999999)
    risk_cfg = RiskGateConfig()
    
    # 3. Determine Run ID (Start vs Resume)
    run_id = args.run_id
    
    if not run_id:
        # Start New
        run_id = start_live_run(
            home=args.home,
            symbol=candidate["symbol"],
            timeframe=candidate["timeframe"],
            candidate_build_ts=candidate["build_ts"],
            trace_ids=trace,
            data=data,
            broker=broker,
            store=store,
            gov_cfg=gov_cfg,
            risk_cfg=risk_cfg
        )
        print(f"Started New Run: {run_id}")
    else:
        # Verify Exists
        state = load_live_state(args.home, run_id)
        if not state:
            print(f"Run {run_id} state not found for resume.")
            sys.exit(2)
        print(f"Resuming Run: {run_id} (Cursor: {state['cursor']})")
        
    # 4. Step
    summary = live_step(
        home=args.home,
        run_id=run_id,
        steps=args.steps,
        symbol=candidate["symbol"],
        timeframe=candidate["timeframe"],
        trace_ids=trace,
        data=data,
        broker=broker,
        store=store,
        gov_cfg=gov_cfg,
        risk_cfg=risk_cfg,
        candidate_id=args.candidate_id
    )
    
    print(f"Run ID: {summary['run_id']}")
    print(f"Cursor: {summary['cursor']} / {summary['total_bars']}")
    print(f"Processed: {summary['steps_processed']}")
    print(f"Verdict: {summary['verdict']}")
    print(f"Stage: {summary['stage']}")
    
    if summary['verdict'] == "FAIL":
        sys.exit(2)
    elif summary['verdict'] == "IMPROVE":
        sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
