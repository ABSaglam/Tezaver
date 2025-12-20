import os
import json
import time
from typing import Dict, List, Optional
from tezaver.matrix.core.export_package import export_candidate
from tezaver.matrix.core.cloud_import import import_export_package
from tezaver.matrix.core.cloud_registry import list_strategies, read_strategy
from tezaver.matrix.core.checksums import write_json

def get_approved_candidates(home: str) -> List[str]:
    """Lists candidate_ids from approved pool."""
    app_dir = os.path.join(home, "approved")
    if not os.path.exists(app_dir): return []
    return [d for d in os.listdir(app_dir) if os.path.isdir(os.path.join(app_dir, d))]

def is_candidate_deployed(home: str, candidate_id: str) -> bool:
    """Checks if a strategy with this candidate_id already exists in cloud registry."""
    sids = list_strategies(home)
    for sid in sids:
        s = read_strategy(home, sid)
        if s and s.get("candidate_id") == candidate_id:
            return True
    return False

def plan_migration(home: str, policy: Dict) -> Dict:
    """
    Scans approved candidates and creates a migration plan based on policy.
    Policy keys:
      - mode: "PROMOTE_ALL" | "PROMOTE_ALLOWLIST"
      - activate: bool
      - allowlist: List[str]
    """
    mode = policy.get("mode", "PROMOTE_ALL")
    activate = policy.get("activate", False)
    allowlist = set(policy.get("allowlist", []))
    
    candidates = get_approved_candidates(home)
    items = []
    
    for cid in candidates:
        should_migrate = False
        
        if mode == "PROMOTE_ALL":
            should_migrate = True
        elif mode == "PROMOTE_ALLOWLIST":
            if cid in allowlist:
                should_migrate = True
                
        if should_migrate:
            # Check Idempotency (Plan phase or Execute phase? Execute is safer, but Plan helps visibility)
            # If we plan it, but execute skips it, that's fine.
            # Let's include it in plan, but mark "status" if we wanted?
            # Plan format: list of dicts.
            items.append({
                "candidate_id": cid,
                "approved_path": os.path.join(home, "approved", cid),
                "activate": activate
            })
            
    return {
        "ts": int(time.time()),
        "policy": policy,
        "items": items
    }

def execute_migration(home: str, plan: Dict) -> Dict:
    """
    Executes the migration plan.
    Returns a report with results.
    """
    report_items = []
    
    ops_dir = os.path.join(home, "ops", "migration")
    os.makedirs(ops_dir, exist_ok=True)
    events_path = os.path.join(ops_dir, "events.ndjson")
    
    def log_event(type: str, cid: str, detail: str):
        evt = {
            "type": type,
            "ts": int(time.time()*1000),
            "candidate_id": cid,
            "detail": detail
        }
        with open(events_path, "a") as f:
            f.write(json.dumps(evt) + "\n")
            
    total = len(plan.get("items", []))
    ok_count = 0
    fail_count = 0
    skip_count = 0
    
    for item in plan.get("items", []):
        cid = item["candidate_id"]
        activate = item["activate"]
        
        res_item = {"candidate_id": cid, "status": "UNKNOWN"}
        
        try:
            # Idempotency Check
            if is_candidate_deployed(home, cid):
                log_event("MIGRATION_ITEM_SKIP", cid, "Already deployed")
                res_item["status"] = "SKIPPED"
                skip_count += 1
                report_items.append(res_item)
                continue
                
            # 1. Export
            # We export now (JIT). This creates EXPORT_<cid>_<ts>
            exp_res = export_candidate(home, cid)
            export_path = exp_res["export_path"]
            
            # 2. Gate Check (MX-15004)
            if activate:
                from tezaver.matrix.core.release_gate import evaluate_release_gate
                gate_res = evaluate_release_gate(home, cid)
                if not gate_res["ok"]:
                    activate = False # FORCE PAUSED
                    log_event("MIGRATION_BLOCKED_BY_GATE", cid, f"Forced PAUSED. Failed checks: {[c['code'] for c in gate_res['checks'] if c['status']=='FAIL']}")
                    res_item["gate_blocked"] = True
                    res_item["gate_details"] = gate_res
            
            # 3. Import
            imp_res = import_export_package(home, export_path, activate=activate)
            strat_id = imp_res["strategy_id"]
            
            log_event("MIGRATION_ITEM_OK", cid, f"Imported as {strat_id}")
            res_item["status"] = "OK"
            res_item["strategy_id"] = strat_id
            ok_count += 1
            
        except Exception as e:
            log_event("MIGRATION_ITEM_FAIL", cid, str(e))
            res_item["status"] = "FAIL"
            res_item["error"] = str(e)
            fail_count += 1
            
        report_items.append(res_item)
        
    report = {
        "ts": int(time.time()),
        "plan_ts": plan.get("ts"),
        "total": total,
        "ok": ok_count,
        "fail": fail_count,
        "skipped": skip_count,
        "results": report_items
    }
    
    # Save Report
    write_json(os.path.join(ops_dir, "latest.json"), report)
    
    return report
