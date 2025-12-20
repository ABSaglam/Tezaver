import argparse
import sys
import os
import json
import time
from typing import List, Dict

from tezaver.matrix.core.cycle_engine import run_cycle
from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore
from tezaver.matrix.adapters.data_port_json import JsonFileDataPort
from tezaver.matrix.adapters.broker_sim import SimBroker
from tezaver.matrix.adapters.store_run_fs import FileRunStore
from tezaver.matrix.core.trace import TraceIds
from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig
from tezaver.matrix.ports.candidate_bundle import bundle_from_dict, candidate_id, validate_bundle_dict

def main():
    parser = argparse.ArgumentParser(description="Matrix War Runner (MX-8003)")
    parser.add_argument("--candidates-dir", required=True, help="Directory containing candidate JSONs")
    parser.add_argument("--bars-dir", required=True, help="Directory containing bars JSONs")
    parser.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"), help="Matrix Home")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of candidates (0=all)")
    
    args = parser.parse_args()
    
    if args.home:
        os.environ["TEZAVER_MATRIX_HOME"] = args.home
        
    start_ts = int(time.time())
    session_id = f"WAR_{start_ts}"
    print(f"Starting War Session: {session_id}")
    
    # 1. Prepare Session Dir
    session_dir = os.path.join(args.home, "war_sessions", session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    # 2. List Candidates
    if not os.path.exists(args.candidates_dir):
        print(f"Candidates dir not found: {args.candidates_dir}")
        sys.exit(2)
        
    files = [f for f in os.listdir(args.candidates_dir) if f.endswith(".json")]
    files.sort()
    
    if args.limit > 0:
        files = files[:args.limit]
        
    results = []
    
    store = FileRunStore(args.home)
    # Gov config: allow everything found for demo
    # In real world, we might want to check allowlist stricter.
    
    total = 0
    passed = 0
    improved = 0
    failed = 0
    
    for fname in files:
        fpath = os.path.join(args.candidates_dir, fname)
        row = {
            "file": fname,
            "status": "PENDING"
        }
        
        try:
            with open(fpath, "r") as f:
                c_dict = json.load(f)
                
            # Validate
            errs = validate_bundle_dict(c_dict)
            if errs:
                row["status"] = "FAIL"
                row["error"] = f"Invalid bundle: {errs}"
                failed += 1
                results.append(row)
                continue
                
            # Get ID/Symbol/TF
            # We assume c_dict matches expected structure
            sym = c_dict.get("symbol")
            tf = c_dict.get("timeframe")
            build_ts = c_dict.get("build_ts")
            
            # Helper to get canonical ID
            # c_obj = bundle_from_dict(c_dict)
            # cid = candidate_id(c_obj)
            # Or use filename if strictly named? Let's use internal data
            cid = fname.replace(".json", "") # Use filename as ID proxy if consistent
            
            row["candidate_id"] = cid
            row["symbol"] = sym
            row["timeframe"] = tf
            
            # Locate Bars
            # 1. sym_tf.json
            bpath1 = os.path.join(args.bars_dir, f"{sym}_{tf}.json")
            bpath2 = os.path.join(args.bars_dir, f"{sym}.json")
            
            bars_path = None
            if os.path.exists(bpath1):
                bars_path = bpath1
            elif os.path.exists(bpath2):
                bars_path = bpath2
                
            if not bars_path:
                row["status"] = "FAIL"
                row["error"] = "No bars found"
                failed += 1
                results.append(row)
                continue
                
            row["bars_path"] = bars_path
            
            # Setup Run
            trace = TraceIds(
                engine_version="v4-dev",
                data_fingerprint=f"bars_{os.path.basename(bars_path)}",
                config_signature=f"war:{session_id}"
            )
            
            # Run
            meta = run_cycle(
                symbol=sym,
                timeframe=tf,
                candidate_build_ts=build_ts,
                trace_ids=trace,
                data=JsonFileDataPort(bars_path),
                broker=SimBroker(),
                store=store,
                risk_cfg=RiskGateConfig(max_notional=0), # Unlimited for war
                gov_cfg=GovernanceConfig(allowlist=[sym], max_age_seconds=999999999), 
                home=args.home,
                run_profile="WAR"
            )
            
            rid = meta["run_id"]
            row["run_id"] = rid
            
            # Get Verdict & Stage
            jpath = os.path.join(args.home, "runs", rid, "judge.json")
            if os.path.exists(jpath):
                with open(jpath) as f:
                    j = json.load(f)
                    verdict = j.get("overall", "UNKNOWN")
                    row["verdict"] = verdict
                    
                    if verdict == "PASS": passed += 1
                    elif verdict == "IMPROVE": improved += 1
                    else: failed += 1
            else:
                row["verdict"] = "ERROR"
                row["error"] = "No judge result"
                failed += 1
                
            # Get Stage (from candidates_stage side effect folder)
            # Or assume run_cycle updated it. 
            # We can read 'stage' from candidate bundle if we re-read?
            # Or check candidates_stage file.
            # Let's inspect stage later or just skip for summary.
            # Row update
            # row["stage_after"] = ... (read from disk)
            spath = os.path.join(args.home, "candidates_stage", f"{cid}.json")
            if os.path.exists(spath):
                with open(spath) as f:
                   s_info = json.load(f)
                   row["stage_after"] = s_info.get("stage")
            
            row["status"] = "DONE"
            
        except Exception as e:
            row["status"] = "FAIL"
            row["error"] = str(e)
            failed += 1
            
        results.append(row)
        total += 1
        print(f"Completed {cid}: {row.get('verdict', 'ERR')}")
        
    # Write Index
    idx_path = os.path.join(session_dir, "index.json")
    with open(idx_path, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"Session {session_id} Complete.")
    print(f"Total: {total}, Pass: {passed}, Improve: {improved}, Fail: {failed}")
    print(f"Index: {idx_path}")
    
    if failed > 0:
        sys.exit(2)
        
if __name__ == "__main__":
    main()
