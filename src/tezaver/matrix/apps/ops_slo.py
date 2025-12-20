import argparse
import json
import os
from tezaver.matrix.core.ops_slo import write_ops_reports

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", default=".tezaver_matrix")
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()
    
    write_ops_reports(args.home, args.hours)
    
    p = os.path.join(args.home, "ops", "slo", "latest.json")
    with open(p) as f:
        print(json.dumps(json.load(f), indent=2))

if __name__ == "__main__":
    main()
