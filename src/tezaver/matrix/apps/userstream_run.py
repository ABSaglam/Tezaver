import argparse
import sys
import time
from tezaver.matrix.core.userstream_manager import UserStreamManager
from tezaver.matrix.core.userstream_runner import UserStreamRunner
from tezaver.matrix.core.secrets import load_binance_secrets
from tezaver.matrix.adapters.binance_rest_client import BinanceRestClient
from tezaver.matrix.adapters.websocket_optional import WebSocketOptional, HAS_WEBSOCKET

def main():
    parser = argparse.ArgumentParser(description="Run User Data Stream WebSocket")
    parser.add_argument("--home", default=".tezaver_matrix")
    parser.add_argument("--ticks", type=int, default=0, help="Number of loops (0=infinite)")
    
    args = parser.parse_args()
    
    if not HAS_WEBSOCKET:
        print("ERROR: websocket-client library not installed. Cannot run real stream.", file=sys.stderr)
        # We allow running if just testing logic, but prompt implied real capability is optional but CLI should exist.
        # If user wants to run, they need lib.
        sys.exit(1)
        
    secrets = load_binance_secrets(args.home)
    if not secrets["present"]:
        print("Error: Secrets missing.", file=sys.stderr)
        sys.exit(1)
        
    client = BinanceRestClient(secrets["api_key"], secrets["api_secret"], secrets["testnet"])
    mgr = UserStreamManager(client, args.home)
    ws = WebSocketOptional()
    
    runner = UserStreamRunner(ws, mgr, args.home)
    
    print(f"Starting UserStreamRunner... (Home: {args.home})")
    try:
        runner.run(ticks=args.ticks if args.ticks > 0 else None)
    except KeyboardInterrupt:
        print("Stopped by user.")

if __name__ == "__main__":
    main()
