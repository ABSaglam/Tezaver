import argparse
import sys
import os
import json
from tezaver.matrix.core.cloud_runtime import cloud_runtime_tick

def main():
    parser = argparse.ArgumentParser(description="Matrix Cloud Runtime (MX-12001)")
    parser.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"))
    parser.add_argument("--ticks", type=int, default=1, help="Number of ticks to process")
    parser.add_argument("--steps", type=int, default=10, help="Max bars per strategy per tick")
    
    args = parser.parse_args()
    
    try:
        res = cloud_runtime_tick(args.home, ticks=args.ticks, steps_per_strategy=args.steps)
        print("CLOUD RUNTIME TICK COMPLETE")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"RUNTIME ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
