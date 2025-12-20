import argparse
import sys
import json
import time
from tezaver.matrix.core.cloud_loop import CloudLoopSupervisor

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    
    # Run
    run_p = subparsers.add_parser("run")
    run_p.add_argument("--home", default=".tezaver_matrix")
    run_p.add_argument("--ticks", type=int, default=10)
    run_p.add_argument("--steps", type=int, default=5)
    run_p.add_argument("--userstream-recv", type=int, default=10)
    run_p.add_argument("--hours", type=int, default=24)
    
    # Once
    once_p = subparsers.add_parser("once")
    once_p.add_argument("--home", default=".tezaver_matrix")
    once_p.add_argument("--steps", type=int, default=5)
    
    # Stop (Just clears flag? We don't have daemon yet)
    # Just manual for now.
    
    args = parser.parse_args()
    
    sup = CloudLoopSupervisor(args.home)
    
    if args.command == "run":
        print(f"Starting Loop: ticks={args.ticks}, steps={args.steps}...")
        res = sup.run_loop(args.ticks, args.steps, args.userstream_recv, args.hours)
        print(json.dumps(res, indent=2))
        
    elif args.command == "once":
        print("Running Single Tick...")
        res = sup.run_loop(1, args.steps, 10, 24)
        print(json.dumps(res, indent=2))
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
