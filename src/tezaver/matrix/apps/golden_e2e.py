import argparse
import sys
import os
import json
from tezaver.matrix.core.golden_e2e import run_golden_e2e

def main():
    parser = argparse.ArgumentParser(description="Matrix Golden E2E Scenario (MX-11001)")
    parser.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"))
    
    args = parser.parse_args()
    
    try:
        res = run_golden_e2e(args.home)
        print("GOLDEN E2E SUCCESS")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"GOLDEN E2E FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
