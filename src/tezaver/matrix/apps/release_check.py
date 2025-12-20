import argparse
import sys
import json
from tezaver.matrix.core.release_gate import evaluate_release_gate

def main():
    parser = argparse.ArgumentParser(description="Tezaver Release Validation Gate")
    parser.add_argument("--home", default=".tezaver_matrix")
    parser.add_argument("--candidate-id", required=True)
    
    args = parser.parse_args()
    
    res = evaluate_release_gate(args.home, args.candidate_id)
    
    print(f"Release Gate Check: {args.candidate_id}")
    print(f"Overall: {'PASS' if res['ok'] else 'FAIL'}")
    print("-" * 60)
    print(f"{'Code':<8} {'Name':<25} {'Status':<10} {'Detail'}")
    print("-" * 60)
    
    for c in res["checks"]:
        print(f"{c['code']:<8} {c['name']:<25} {c['status']:<10} {c['detail']}")
        
    print("-" * 60)
    
    sys.exit(0 if res["ok"] else 1)

if __name__ == "__main__":
    main()
