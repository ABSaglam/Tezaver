import argparse
import sys
import os
import json
import time
from typing import Dict
from tezaver.matrix.core.orchestrator_recovery import recover_orchestrator_state
from tezaver.matrix.core.live_recovery import recover_live_runs

def run_recovery(home: str) -> Dict:
    print(f"Recovering Orchestrator at {home}...")
    orch = recover_orchestrator_state(home)
    
    print(f"Scanning Live Runs...")
    live = recover_live_runs(home)
    
    report = {
        "ts": int(time.time()),
        "ok": True, # Recovery always "succeeds" in doing its best
        "orchestrator": orch,
        "live": live
    }
    
    # Save Report
    rep_path = os.path.join(home, "ops", "recovery", "latest.json")
    os.makedirs(os.path.dirname(rep_path), exist_ok=True)
    with open(rep_path, "w") as f:
        json.dump(report, f, indent=2)
        
    return report

def main():
    parser = argparse.ArgumentParser(description="Matrix Recovery Tool (MX-10004/5)")
    parser.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"))
    
    args = parser.parse_args()
    
    try:
        rep = run_recovery(args.home)
        print("RECOVERY COMPLETE")
        print(f"Requeued Jobs: {rep['orchestrator']['requeued']}")
        print(f"Stale Locks Removed: {rep['orchestrator']['stale_locks_removed']}")
        print(f"Live Runs Scanned: {rep['live']['runs_scanned']}")
        if rep['live']['warnings']:
            print("WARNINGS:")
            for w in rep['live']['warnings']:
                print(f"- {w}")
                
    except Exception as e:
        print(f"RECOVERY ERROR: {e}")
        # Even if error, it's fail
        sys.exit(2)

if __name__ == "__main__":
    main()
