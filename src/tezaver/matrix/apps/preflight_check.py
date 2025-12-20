import argparse
import sys
import os
import json
from tezaver.matrix.core.preflight import run_preflight

def main():
    parser = argparse.ArgumentParser(description="Matrix Preflight Check (MX-10001)")
    parser.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"))
    
    args = parser.parse_args()
    
    print(f"Running Preflight Checks for: {args.home}...")
    report = run_preflight(args.home)
    
    # Save Report
    if report.get("ok") or os.path.exists(args.home):
        # We try to save even if failed, unless home invalid
        rep_path = os.path.join(args.home, "ops", "preflight", "latest.json")
        os.makedirs(os.path.dirname(rep_path), exist_ok=True)
        with open(rep_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Report saved: {rep_path}")
        
    # Output
    for c in report["checks"]:
        print(f"[{c['status']}] {c['name']}: {c['detail']}")
        
    if report["warnings"]:
        print("\nWARNINGS:")
        for w in report["warnings"]:
            print(f"- {w}")
            
    if report["ok"]:
        print("\nPREFLIGHT PASS")
        sys.exit(0)
    else:
        print("\nPREFLIGHT FAIL")
        sys.exit(2)

if __name__ == "__main__":
    main()
