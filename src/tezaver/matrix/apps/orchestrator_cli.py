import argparse
import sys
import os
import json
from tezaver.matrix.core.orchestrator import enqueue_job, run_ticks, OrchestratorStore

def main():
    parser = argparse.ArgumentParser(description="Matrix Orchestrator CLI (MX-8005)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Enqueue
    p_enq = subparsers.add_parser("enqueue", help="Enqueue a job")
    p_enq.add_argument("--type", required=True, choices=["SNIPER", "WAR", "LIVE_STEP"])
    p_enq.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"))
    p_enq.add_argument("--priority", type=int, default=50)
    
    # Payload args (generic mix)
    p_enq.add_argument("--candidate-id", help="Candidate ID (SNIPER/LIVE)")
    p_enq.add_argument("--run-id", help="Run ID (LIVE)")
    p_enq.add_argument("--bars", help="Bars file path")
    p_enq.add_argument("--candidates-dir", help="Candidates dir (WAR)")
    p_enq.add_argument("--bars-dir", help="Bars dir (WAR)")
    p_enq.add_argument("--steps", type=int, default=1, help="Steps (LIVE)")
    p_enq.add_argument("--limit", type=int, default=0, help="Limit (WAR)")
    
    # Run
    p_run = subparsers.add_parser("run", help="Run scheduler ticks")
    p_run.add_argument("--ticks", type=int, default=1)
    p_run.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"))
    
    # Show
    p_show = subparsers.add_parser("show", help="Show queue/locks/history")
    p_show.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"))
    
    args = parser.parse_args()
    
    if args.command == "enqueue":
        payload = {}
        if args.candidate_id: payload["candidate_id"] = args.candidate_id
        if args.run_id: payload["run_id"] = args.run_id
        if args.bars: payload["bars_path"] = os.path.abspath(args.bars)
        if args.candidates_dir: payload["candidates_dir"] = os.path.abspath(args.candidates_dir)
        if args.bars_dir: payload["bars_dir"] = os.path.abspath(args.bars_dir)
        if args.steps: payload["steps"] = args.steps
        if args.limit: payload["limit"] = args.limit
        
        jid = enqueue_job(args.home, args.type, payload, args.priority)
        print(f"Enqueued Job: {jid}")
        
    elif args.command == "run":
        print(f"Running {args.ticks} ticks...")
        res = run_ticks(args.home, args.ticks)
        print(json.dumps(res, indent=2))
        
    elif args.command == "show":
        store = OrchestratorStore(args.home)
        print("=== QUEUE ===")
        print(json.dumps([j.job_id for j in store.load_queue()], indent=2))
        print("\n=== LOCKS ===")
        print(json.dumps(store.load_locks(), indent=2))
        print("\n=== HISTORY (Last 5) ===")
        hist = store.load_history()[:5]
        for h in hist:
            print(f"{h['job_id']} | {h['type']} | {h['status']}")

if __name__ == "__main__":
    main()
