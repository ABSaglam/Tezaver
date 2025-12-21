import argparse
import sys
import os
import json
import time
from datetime import datetime

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
    MXI-1100: Real Sniper Run implementation.
    TR: Gerçek Sniper backtest akışı. Stub yerine gerçek motoru çalıştırır.
    """
    from tezaver.matrix.adapters.candidate_registry import CandidateRegistry
    from tezaver.matrix.adapters.bundle_source_local import LocalBundleSource
    from tezaver.matrix.adapters.data_port_parquet import ParquetDataPort
    from tezaver.matrix.adapters.broker_sim import SimBroker
    from tezaver.matrix.adapters.store_run_fs import FileRunStore
    from tezaver.matrix.adapters.run_registry import RunRegistry
    from tezaver.matrix.core.sniper_strategy import SniperStrategy
    from tezaver.matrix.core.cycle_engine import run_cycle
    from tezaver.matrix.core.trace import TraceIds
    from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig
    from pathlib import Path

    registry = CandidateRegistry(registry_path=os.path.join(home, "candidates_registry.jsonl"))
    cand_data = registry.get(candidate_id)
    if not cand_data:
        raise ValueError(f"Candidate not found in registry: {candidate_id}")
    
    source = LocalBundleSource()
    manifest, payload = source.load_bundle(Path(cand_data["bundle_path"]))
    
    # 1. Setup Ports
    # Use standard coin_cells for parquet data
    data_port = ParquetDataPort(base_path="coin_cells")
    broker_port = SimBroker(fee_pct=0.001, slippage_pct=0.0005)
    store_port = FileRunStore(home)
    run_reg = RunRegistry()
    
    # 2. Config & Strategy
    strategy = SniperStrategy(payload)
    risk_cfg = RiskGateConfig()
    gov_cfg = GovernanceConfig(allowlist=[manifest.symbol])
    
    trace = TraceIds(
        engine_version="v4-sniper-real",
        data_fingerprint=manifest.fingerprints.data_fingerprint,
        config_signature=manifest.fingerprints.config_signature
    )
    
    # 3. Execution (Real Cycle)
    run_id = f"run_sniper_{candidate_id[:8]}_{int(time.time())}"
    
    meta = run_cycle(
        symbol=manifest.symbol,
        timeframe=manifest.tf,
        candidate_build_ts=manifest.export_time_utc,
        trace_ids=trace,
        data=data_port,
        broker=broker_port,
        store=store_port,
        risk_cfg=risk_cfg,
        gov_cfg=gov_cfg,
        home=home,
        strategy=strategy,
        run_profile="SNIPER",
        run_id=run_id
    )
    
    # 4. Finalize & Register (MXI-1160, MXI-1300)
    # Re-load judge/scorecard results for registry
    from tezaver.matrix.core.jury import compute_scorecard
    scorecard = compute_scorecard(home, run_id)
    
    judgement_path = Path(home) / "runs" / run_id / "judge.json"
    verdict = "UNKNOWN"
    if judgement_path.exists():
        with open(judgement_path) as f:
            verdict = json.load(f).get("overall", "UNKNOWN")
            
    run_reg.register_run(
        run_id=run_id,
        candidate_id=candidate_id,
        symbol=manifest.symbol,
        tf=manifest.tf,
        scorecard=scorecard,
        verdict=verdict
    )

    # MXI-1300: Lifecycle Status Update Hook
    verdict_to_status = {
        "PASS": "APPROVED_FOR_WAR",
        "IMPROVE": "NEEDS_PATCH",
        "FAIL": "REJECTED"
    }
    new_status = verdict_to_status.get(verdict)
    if new_status:
        registry.update_status(candidate_id, new_status)
        
        # Emit Status Updated Telemetry Event
        status_event = {
            "ts": datetime.now().isoformat(),
            "event_type": "CANDIDATE_STATUS_UPDATED",
            "run_id": run_id,
            "payload": {
                "candidate_id": candidate_id,
                "old_status": cand_data.get("status"),
                "new_status": new_status,
                "verdict": verdict
            }
        }
        events_path = Path(home) / "runs" / run_id / "events.ndjson"
        with open(events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(status_event) + "\n")
    
    # MXI-1150: Telemetry copy (refresh it after adding status update)
    import shutil
    telemetry_path = Path(home) / "runs" / run_id / "telemetry.ndjson"
    if events_path.exists():
        shutil.copy(events_path, telemetry_path)
        
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
