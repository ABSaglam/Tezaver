import argparse
import json
import sys
from tezaver.matrix.core.userstream_reconciler import reconcile_stream

def main():
    parser = argparse.ArgumentParser(description="Reconcile User Stream Events")
    parser.add_argument("--home", default=".tezaver_matrix")
    
    args = parser.parse_args()
    
    try:
        res = reconcile_stream(args.home)
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
