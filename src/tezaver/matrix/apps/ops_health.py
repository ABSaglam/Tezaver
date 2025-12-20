import argparse
import json
from tezaver.matrix.core.ops_health import write_health_snapshot

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", default=".tezaver_matrix")
    args = parser.parse_args()
    
    path = write_health_snapshot(args.home)
    with open(path) as f:
        print(json.dumps(json.load(f), indent=2))
        
if __name__ == "__main__":
    main()
