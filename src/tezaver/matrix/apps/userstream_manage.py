import argparse
import sys
import json
from tezaver.matrix.core.userstream_manager import UserStreamManager
from tezaver.matrix.core.secrets import load_binance_secrets
from tezaver.matrix.adapters.binance_rest_client import BinanceRestClient

def main():
    parser = argparse.ArgumentParser(description="Manage User Data Stream")
    parser.add_argument("action", choices=["start", "keepalive", "close", "status"])
    parser.add_argument("--home", default=".tezaver_matrix")
    
    args = parser.parse_args()
    
    # Init Dependencies
    secrets = load_binance_secrets(args.home)
    if not secrets["present"]:
        print("Error: Secrets missing.", file=sys.stderr)
        sys.exit(1)
        
    client = BinanceRestClient(secrets["api_key"], secrets["api_secret"], secrets["testnet"])
    mgr = UserStreamManager(client, args.home)
    
    try:
        if args.action == "start":
            key = mgr.start_stream()
            print(json.dumps({"status": "OK", "listenKey": key}))
        elif args.action == "keepalive":
            mgr.keepalive()
            print(json.dumps({"status": "OK"}))
        elif args.action == "close":
            mgr.close()
            print(json.dumps({"status": "OK"}))
        elif args.action == "status":
            print(json.dumps(mgr.get_status(), indent=2))
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
