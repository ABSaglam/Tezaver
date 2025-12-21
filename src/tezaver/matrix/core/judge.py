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
    from tezaver.matrix.core.run_path import get_run_root
    
    # Infer mode from run_id prefix
    mode = "SNIPER"
    if run_id.startswith("war_"): mode = "WAR"
    elif run_id.startswith("live_"): mode = "LIVE"
    
    # Load Meta
    run_root = get_run_root(mode, run_id, home)
    meta_path = run_root / "meta.json"

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
    # MX-5110: Run-scoped check
    from tezaver.matrix.core.run_path import get_data_report_path
    
    # Infer mode from run_id prefix
    mode = "SNIPER"
    if run_id.startswith("war_"): mode = "WAR"
    elif run_id.startswith("live_"): mode = "LIVE"
    
    data_rep_path = get_data_report_path(mode, run_id, home)
    
    if os.path.exists(data_rep_path):
        try:
             with open(data_rep_path) as f:
                 rep = json.load(f)
                 if rep.get("ok"):
                     gates.append(GateVerdict("DATA_OK", "PASS"))
                 else:
                     gates.append(GateVerdict("DATA_OK", "FAIL", "DATA_QUALITY_FAIL"))
        except:
             gates.append(GateVerdict("DATA_OK", "FAIL", "MISSING_RUN_SCOPED_REPORT (Corrupt)"))
    else:
        gates.append(GateVerdict("DATA_OK", "FAIL", "MISSING_RUN_SCOPED_REPORT"))

        
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

    # 7. PNL_SANITY (MXI-1402)
    MAX_NOTIONAL = 1_000_000_000 # 1 Billion placeholder
    MAX_PNL_PCT = 20.0 # 20% single trade limit
    
    trade_audit = scorecard.get("trade_audit_v2", [])
    sanity_fail = False
    sanity_msg = "All trades within limits"
    
    for t in trade_audit:
        if t.get("notional", 0) > MAX_NOTIONAL:
            sanity_fail = True
            sanity_msg = f"Trade notional {t.get('notional'):.0f} exceeds limit {MAX_NOTIONAL}"
            break
        # PnL % calculation if exit price existed, but here we only have entries (notional).
        # We'll skip PnL % sanity until we have exits, or use a dummy check.
        
    if not sanity_fail:
        gates.append(GateVerdict("PNL_SANITY", "PASS", sanity_msg))
    else:
        gates.append(GateVerdict("PNL_SANITY", "FAIL", sanity_msg))

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
    report_path = run_root / "report.json"
    with open(report_path, "w", encoding="utf-8") as f:

        json.dump(result, f, indent=2)
        
    return result
