
import os
import json
from pathlib import Path
from tezaver.matrix.adapters.candidate_registry import CandidateRegistry

def run_import_pilot2():
    registry = CandidateRegistry()
    root = "out/matrix_candidates/BTCUSDT/15m/bundle_v1"
    
    target_ids = [
        "bundle_v1_1766331393",
        "bundle_v1_1766331396",
        "bundle_v1_1766331399"
    ]
    
    print(f"Starting Import for {len(target_ids)} Pilot-2 bundles...")
    
    for bid in target_ids:
        bdir = os.path.join(root, bid)
        manifest_path = os.path.join(bdir, "manifest.json")
        
        if not os.path.exists(manifest_path):
            print(f"Error: {bid} not found in {root}")
            continue
            
        with open(manifest_path) as f:
            m = json.load(f)
            
        # Register in CandidateRegistry
        # PNL-1110: bundle_id is primary key
        registry.upsert(
            bundle_id=m["bundle_id"],
            symbol=m["symbol"],
            tf=m["tf"],
            bundle_path=str(bdir),
            metrics=m["metrics"],
            fingerprints=m["fingerprints"],
            status="NEW" # Explicitly NEW for pilot start
        )
        print(f"Imported: {m['bundle_id']} (Total Stories: {m['metrics'].get('total_count', 0)})")

if __name__ == "__main__":
    run_import_pilot2()
