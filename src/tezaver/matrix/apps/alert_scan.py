import argparse
import sys
import json
import os
from tezaver.matrix.adapters.notifier_file import FileNotifier
from tezaver.matrix.core.alert_engine import scan_cloud_events_for_alerts

def main():
    parser = argparse.ArgumentParser(description="Scan Cloud Runtime events and generate alerts")
    parser.add_argument("--home", default=".tezaver_matrix", help="Matrix home directory")
    parser.add_argument("--cloud-run-id", default=None, help="Specific cloud run ID to scan")
    
    args = parser.parse_args()
    
    home = args.home
    notifier = FileNotifier(home)
    
    try:
        res = scan_cloud_events_for_alerts(home, notifier, args.cloud_run_id)
        
        # Output JSON summary to stdout
        print(json.dumps(res, indent=2))
        
        if res.get("error"):
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
