import argparse
import sys
import os
import json
from tezaver.matrix.core.approved_pool import promote_candidate_from_run
from tezaver.matrix.core.export_package import export_candidate

def main():
    parser = argparse.ArgumentParser(description="Matrix Approved Promote CLI (MX-9001)")
    parser.add_argument("--run-id", required=True, help="Live Run ID to promote from")
    parser.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"))
    parser.add_argument("--export", default="no", choices=["yes", "no"], help="Create export package?")
    
    args = parser.parse_args()
    
    try:
        print(f"Promoting from run: {args.run_id}...")
        res = promote_candidate_from_run(args.home, args.run_id)
        cid = res["candidate_id"]
        print(f"SUCCESS: Candidate {cid} promoted.")
        print(f"Path: {res['approved_path']}")
        
        if args.export == "yes":
            print("Creating Export Package...")
            exp_res = export_candidate(args.home, cid)
            print(f"EXPORT CREATED: {exp_res['export_id']}")
            print(f"Path: {exp_res['export_path']}")
            
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()
