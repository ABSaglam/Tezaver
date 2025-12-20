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

def run_war_once(home: str, candidates_dir: str, bars_dir: str, limit: int = 0) -> dict:
    home = home or os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix")
    if home: os.environ["TEZAVER_MATRIX_HOME"] = home
    
    start_ts = int(time.time())
    session_id = f"WAR_{start_ts}"
    session_dir = os.path.join(home, "war_sessions", session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    if not os.path.exists(candidates_dir):
        return {"error": f"Candidates dir not found: {candidates_dir}", "status": "FAIL"}
        
    files = [f for f in os.listdir(candidates_dir) if f.endswith(".json")]
    files.sort()
    
    if limit > 0:
        files = files[:limit]
        
    results = []
    store = FileRunStore(home)
    
    total = 0
    passed = 0
    improved = 0
    failed = 0
    
    for fname in files:
        fpath = os.path.join(candidates_dir, fname)
        row = {"file": fname, "status": "PENDING"}
        try:
            with open(fpath, "r") as f: c_dict = json.load(f)
            
            errs = validate_bundle_dict(c_dict)
            if errs:
                row["status"] = "FAIL"
                row["error"] = f"Invalid bundle: {errs}"
                failed += 1
                results.append(row)
                continue
                
            cid = fname.replace(".json", "")
            sym = c_dict.get("symbol")
            tf = c_dict.get("timeframe")
            build_ts = c_dict.get("build_ts")
            
            row["candidate_id"] = cid
            row["symbol"] = sym
            row["timeframe"] = tf
            
            # Bars
            bpath1 = os.path.join(bars_dir, f"{sym}_{tf}.json")
            bpath2 = os.path.join(bars_dir, f"{sym}.json")
            bars_path = bpath1 if os.path.exists(bpath1) else (bpath2 if os.path.exists(bpath2) else None)
            
            if not bars_path:
                row["status"] = "FAIL"
                row["error"] = "No bars found"
                failed += 1
                results.append(row)
                continue
            
            row["bars_path"] = bars_path
            
            trace = TraceIds("v4-dev", f"bars_{os.path.basename(bars_path)}", f"war:{session_id}")
            
            meta = run_cycle(
                symbol=sym, timeframe=tf, candidate_build_ts=build_ts,
                trace_ids=trace, data=JsonFileDataPort(bars_path), broker=SimBroker(),
                store=store, risk_cfg=RiskGateConfig(max_notional=0),
                gov_cfg=GovernanceConfig(allowlist=[sym], max_age_seconds=999999999), 
                home=home, run_profile="WAR"
            )
            
            rid = meta["run_id"]
            row["run_id"] = rid
            
            # Verdict
            jpath = os.path.join(home, "runs", rid, "judge.json")
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
                
            spath = os.path.join(home, "candidates_stage", f"{cid}.json")
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
        print(f"Completed {cid}: {row.get('verdict', 'ERR')}")
    
    total = len(results)
        
    idx_path = os.path.join(session_dir, "index.json")
    with open(idx_path, "w") as f:
        json.dump(results, f, indent=2)
        
    return {
        "session_id": session_id,
        "total": total,
        "passed": passed,
        "improved": improved,
        "failed": failed,
        "index_path": idx_path,
        "status": "DONE" if failed == 0 else "PARTIAL" # Or always DONE if job logic expects completion
    }

def main():
    parser = argparse.ArgumentParser(description="Matrix War Runner (MX-8003)")
    parser.add_argument("--candidates-dir", required=True, help="Directory containing candidate JSONs")
    parser.add_argument("--bars-dir", required=True, help="Directory containing bars JSONs")
    parser.add_argument("--home", default=os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix"), help="Matrix Home")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of candidates (0=all)")
    
    args = parser.parse_args()
    
    print("Starting War Session...")
    res = run_war_once(args.home, args.candidates_dir, args.bars_dir, args.limit)
    
    if "error" in res:
        print(f"Error: {res['error']}")
        sys.exit(2)
        
    print(f"Session {res['session_id']} Complete.")
    print(f"Total: {res['total']}, Pass: {res['passed']}, Improve: {res['improved']}, Fail: {res['failed']}")
    print(f"Index: {res['index_path']}")
    
    if res['failed'] > 0:
        sys.exit(2)
        
if __name__ == "__main__":
    main()
