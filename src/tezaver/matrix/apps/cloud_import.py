import argparse
import sys
import os
import json
from tezaver.matrix.core.cloud_import import import_export_package

def main():
    parser = argparse.ArgumentParser(description="Matrix Cloud Import CLI (MX-9003)")
    parser.add_argument("--export-path", required=True, help="Path to exported package dir (EXPORT_...)")
    parser.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"))
    parser.add_argument("--activate", default="no", choices=["yes", "no"], help="Activate on import?")
    
    args = parser.parse_args()
    
    activate = (args.activate == "yes")
    
    try:
        print(f"Importing from: {args.export_path}...")
        res = import_export_package(args.home, args.export_path, activate)
        
        print(f"SUCCESS: Strategy Imported.")
        print(f"ID: {res['strategy_id']}")
        print(f"Status: {res['status']}")
        print(f"Path: {res['target_path']}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()
