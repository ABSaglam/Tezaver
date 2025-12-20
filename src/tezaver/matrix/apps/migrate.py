import argparse
import sys
import json
from tezaver.matrix.core.migration_engine import plan_migration, execute_migration

def main():
    parser = argparse.ArgumentParser(description="Tezaver Matrix Migration Tool")
    parser.add_argument("--home", default=".tezaver_matrix")
    parser.add_argument("--mode", choices=["promote_all", "promote_allowlist"], default="promote_all")
    parser.add_argument("--activate", choices=["yes", "no"], default="no")
    parser.add_argument("--allowlist", help="Comma separated list of candidate IDs")
    
    args = parser.parse_args()
    
    policy = {
        "mode": args.mode.upper(),
        "activate": (args.activate == "yes"),
        "allowlist": args.allowlist.split(",") if args.allowlist else []
    }
    
    print(f"Planning migration with policy: {policy}...")
    plan = plan_migration(args.home, policy)
    item_count = len(plan["items"])
    print(f"Plan created with {item_count} items.")
    
    if item_count == 0:
        print("Nothing to migrate.")
        sys.exit(0)
        
    print("Executing migration...")
    report = execute_migration(args.home, plan)
    
    print(json.dumps(report, indent=2))
    
    if report["fail"] > 0:
        sys.exit(2)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
