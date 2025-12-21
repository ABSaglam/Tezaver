import os
import sys
import json
from pathlib import Path

sys.path.append("src")

from tezaver.matrix.adapters.bundle_source_local import LocalBundleSource
from tezaver.matrix.adapters.candidate_registry import CandidateRegistry
from tezaver.matrix.apps.run_sniper import run_sniper_stub
from tezaver.matrix.core.candidate_v1 import generate_candidate_id

def test_sprint3_full_flow():
    home = ".test_matrix_home_s3"
    os.makedirs(home, exist_ok=True)
    
    # 1. Setup Registry
    reg_path = os.path.join(home, "candidates_registry.jsonl")
    if os.path.exists(reg_path): os.remove(reg_path)
    registry = CandidateRegistry(registry_path=reg_path)
    
    # 2. Discover & Register
    source = LocalBundleSource(base_path="out/matrix_candidates")
    bundles = source.discover_bundles()
    if not bundles:
        print("FAIL: No bundles found")
        return
    
    bdir = bundles[0]
    manifest, _ = source.load_bundle(bdir)
    cid = generate_candidate_id(manifest)
    
    print(f"Candidate ID: {cid}")
    registry.register(
        candidate_id=cid,
        symbol=manifest.symbol,
        tf=manifest.tf,
        bundle_id=manifest.bundle_id,
        bundle_path=str(bdir),
        metrics={"trigger_resolve_rate": 0.99, "join_coverage": 0.85},
        status="NEW" # Start with NEW
    )
    
    # 3. Run Sniper
    print("Executing Sniper...")
    run_id = run_sniper_stub(home, cid)
    print(f"Run ID: {run_id}")
    
    # 4. Verify Candidate Lifecycle (MXI-1300)
    # Reload registry to see disk updates
    registry_disk = CandidateRegistry(registry_path=reg_path)
    updated_cand = registry_disk.get(cid)
    print(f"Updated Status: {updated_cand['status']}")
    if updated_cand['status'] in ["APPROVED_FOR_WAR", "NEEDS_PATCH", "REJECTED"]:
        print(f"SUCCESS: Candidate status updated to {updated_cand['status']}")
    else:
        print("FAIL: Candidate status not updated automatically")
        
    # Check status event in ndjson
    run_dir = Path(home) / "runs" / run_id
    with open(run_dir / "events.ndjson") as f:
        events = [json.loads(line) for line in f]
        status_ev = next((e for e in events if e['event_type'] == "CANDIDATE_STATUS_UPDATED"), None)
        if status_ev:
            print("SUCCESS: CANDIDATE_STATUS_UPDATED event found in telemetry.")
        else:
            print("FAIL: Status update event missing in telemetry.")
        
    # 5. Verify Trade Audit & PnL Sanity (MXI-1400)
    run_dir = Path(home) / "runs" / run_id
    with open(run_dir / "scorecard.json") as f:
        sc = json.load(f)
        audit = sc.get("trade_audit_v2", [])
        print(f"Trade Audit count: {len(audit)}")
        if audit:
            print("SUCCESS: TradeAuditV2 exists.")
            print(f"Sample Trade Notional: {audit[0].get('notional')}")
            
    with open(run_dir / "judge.json") as f:
        judge = json.load(f)
        sanity_gate = next((g for g in judge['gates'] if g['name'] == "PNL_SANITY"), None)
        if sanity_gate:
            print(f"SUCCESS: PNL_SANITY Gate found. Status: {sanity_gate['status']}")
        else:
            print("FAIL: PNL_SANITY Gate missing!")

if __name__ == "__main__":
    test_sprint3_full_flow()
