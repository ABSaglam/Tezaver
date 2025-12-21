import os
import json
import pandas as pd
from datetime import datetime
from tezaver.matrix.core.war_engine import WarEngine
from tezaver.matrix.apps.war_planner import WarPlan, WarCell, PlanDiagnostics
from tezaver.matrix.core.judge import judge_run

def pilot_demo():
    print("--- MX-5110 PILOT RUN DEMO ---")
    
    # 1. Setup Dummy Data
    os.makedirs("coin_cells/BTCUSDT/data", exist_ok=True)
    df = pd.DataFrame([
        {"ts": 1700000000 + i*900, "open": 40000+i, "high": 41000+i, "low": 39000+i, "close": 40500+i}
        for i in range(100)
    ])
    df.to_parquet("coin_cells/BTCUSDT/data/history_15m.parquet")
    print("Created dummy data: coin_cells/BTCUSDT/data/history_15m.parquet")
    
    # 2. Create WarPlan
    cell = WarCell(
        symbol="BTCUSDT",
        tf="15m",
        candidate_id="pilot_cand_001",
        bundle_id="bundle_001",
        bundle_path="path/to/bundle",
        data_fingerprint="dummy_fp",
        config_signature="dummy_sig"
    )
    
    plan = WarPlan(
        plan_id="pilot_plan_001",
        created_at=datetime.now().isoformat(),
        cells=[cell],
        symbols=["BTCUSDT"],
        candidate_ids=["pilot_cand_001"],
        config_hash="pilot_hash_123",
        diagnostics=PlanDiagnostics(approved_for_war_count=1, selected_cells_count=1)
    )
    
    # 3. Execution
    engine = WarEngine(plan)
    print(f"Starting WarEngine Pilot Run: {engine.run_id}")
    result = engine.run()
    
    # 4. Verification of Artifacts
    run_dir = result["artifacts_dir"]
    report_path = os.path.join(run_dir, "reports", "data_report_v1.json")
    
    if os.path.exists(report_path):
        print(f"SUCCESS: Found run-scoped report at {report_path}")
        with open(report_path) as f:
            rep = json.load(f)
            print(f"Report JSON: {json.dumps(rep, indent=2)}")
    else:
        print(f"FAILED: Report not found at {report_path}")
        return

    # 5. Judge Gate Check
    print("\nEvaluating Judge Gates for Pilot Run...")
    # Use empty home as get_run_root logic in judge.py/run_path.py handles out/matrix_runs
    scorecard = result["scorecard"]
    judge_res = judge_run(".", engine.run_id, scorecard)
    
    data_gate = next(g for g in judge_res["gates"] if g["name"] == "DATA_OK")
    print(f"DATA_OK Gate Verdict: {data_gate['status']} (Reason: {data_gate['reason']})")
    
    if data_gate['status'] == "PASS":
        print("\n--- PILOT RUN SUCCESSFUL ---")
        print(f"Registry proof run_id: {engine.run_id}")
    else:
        print("\n--- PILOT RUN FAILED GATE ---")

if __name__ == "__main__":
    pilot_demo()
