import os
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Dict

@dataclass
class GateVerdict:
    name: str
    status: str # PASS, FAIL, IMPROVE
    reason: str = ""

def judge_run(home: str, run_id: str, scorecard: Dict) -> Dict:
    """Evaluates a run against Gates and issues a Verdict."""
    
    # Load Meta
    run_dir = os.path.join(home, "runs", run_id)
    meta_path = os.path.join(run_dir, "meta.json")
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            
    gates = []
    
    # 1. TRACE_OK
    trace = meta.get("trace", {})
    if trace and trace.get("engine_version") and trace.get("data_fingerprint"):
        gates.append(GateVerdict("TRACE_OK", "PASS"))
    else:
        gates.append(GateVerdict("TRACE_OK", "FAIL", "Missing trace data"))
        
    # 2. TELEMETRY_OK
    # Re-validate first few events? Or trust previous checks?
    # Simple check: do we have events?
    if scorecard.get("event_types"):
        gates.append(GateVerdict("TELEMETRY_OK", "PASS"))
    else:
        gates.append(GateVerdict("TELEMETRY_OK", "FAIL", "No events found"))
        
    # 3. NO_BLOCKS
    blocks = scorecard.get("blocks_count", 0)
    if blocks == 0:
        gates.append(GateVerdict("NO_BLOCKS", "PASS"))
    else:
        gates.append(GateVerdict("NO_BLOCKS", "FAIL", f"Found {blocks} blocks"))
        
    # 4. DATA_OK
    # Check data_reports/latest.json
    data_rep_path = os.path.join(home, "data_reports", "latest.json")
    if os.path.exists(data_rep_path):
        try:
             with open(data_rep_path) as f:
                 rep = json.load(f)
                 if rep.get("ok"):
                     gates.append(GateVerdict("DATA_OK", "PASS"))
                 else:
                     gates.append(GateVerdict("DATA_OK", "IMPROVE", "Data issues found"))
        except:
             gates.append(GateVerdict("DATA_OK", "IMPROVE", "Corrupt data report"))
    else:
        gates.append(GateVerdict("DATA_OK", "IMPROVE", "No data report found"))
        
    # 5. MIN_TRADES (MXI-1140)
    trades_count = scorecard.get("trades_count", 0)
    if trades_count >= 1:
        gates.append(GateVerdict("MIN_TRADES", "PASS", f"Found {trades_count} trades"))
    else:
        gates.append(GateVerdict("MIN_TRADES", "FAIL", "No trades executed"))
        
    # 6. PROFITABLE (MXI-1140)
    pnl = scorecard.get("total_pnl_raw", 0)
    if pnl > 0:
        gates.append(GateVerdict("PROFITABLE", "PASS", f"PnL {pnl:.2f} > 0"))
    elif trades_count > 0:
        gates.append(GateVerdict("PROFITABLE", "IMPROVE", f"PnL {pnl:.2f} is negative"))
    else:
        gates.append(GateVerdict("PROFITABLE", "SKIP", "No trades to evaluate PnL"))

    # Compute Overall
    statuses = [g.status for g in gates]
    overall = "PASS"
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "IMPROVE" in statuses:
        overall = "IMPROVE"
        
    result = {
        "run_id": run_id,
        "overall": overall,
        "gates": [asdict(g) for g in gates],
        "created_ts": int(time.time()),
        "scorecard_summary": {
            "pnl": scorecard.get("total_pnl_raw", 0),
            "trades": scorecard.get("trades_count", 0)
        }
    }
    
    # MXI-1150: Generate report.json
    report_path = os.path.join(run_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        
    return result
