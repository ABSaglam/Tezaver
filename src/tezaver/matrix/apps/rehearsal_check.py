import argparse
import sys
import json
from tezaver.matrix.core.rehearsal import run_rehearsal, write_latest

def main():
    parser = argparse.ArgumentParser(description="Tezaver Production Rehearsal Checklist")
    parser.add_argument("--home", default=".tezaver_matrix")
    parser.add_argument("--candidate-id", default=None)
    
    args = parser.parse_args()
    
    report = run_rehearsal(args.home, args.candidate_id)
    write_latest(args.home, report)
    
    print(f"Overall: {report['overall']}")
    if report["fail_codes"]:
        print(f"Fail Codes: {', '.join(report['fail_codes'])}")
    print("-" * 50)
    for c in report["checks"]:
        print(f"{c['code']}: {c['status']} - {c['name']} ({c['detail']})")
        
    sys.exit(0 if report["go"] else 3)

if __name__ == "__main__":
    main()
