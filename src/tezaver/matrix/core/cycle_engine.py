import os
import time
import json
import hashlib
from typing import List, Dict, Optional
from dataclasses import asdict

from tezaver.matrix.core.bars import Bar, require_closed_bar
from tezaver.matrix.core.trace import TraceIds, require_trace_ids
from tezaver.matrix.core.state import RunState, validate_state
from tezaver.matrix.core.gates import eval_all_gates, RiskGateConfig, GovernanceConfig, GateResult

def run_cycle(bars: List[Bar], 
              trace_ids: TraceIds, 
              candidate_meta: dict, 
              risk_cfg: RiskGateConfig,
              gov_cfg: GovernanceConfig,
              home: str,
              run_id: Optional[str] = None) -> dict:
              
    # 1. Init
    require_trace_ids(trace_ids)
    
    if not run_id:
        # Construct run_id: created_ts + random suffix (or determinism in test)
        # We use time.time() here which is non-deterministic, but caller can provide fixed ID for tests.
        run_id = f"run_{candidate_meta.get('symbol')}_{candidate_meta.get('timeframe')}_{int(time.time())}"
        
    runs_dir = os.path.join(home, "runs", run_id)
    os.makedirs(runs_dir, exist_ok=True)
    
    state = RunState()
    
    events = []
    gate_history = []
    
    # Simple Demo Decision Logic
    # Always HOLD. If Price > 0 and no position -> Signal BUY (but Gates might block)
    # This is just a skeletal decision engine.
    
    # 2. Main Loop
    for bar in bars:
        require_closed_bar(bar)
        
        # Validate State invariant
        invariants = validate_state(state)
        if invariants:
            # Fatal error, stop cycle
            ev = {
                "ts": bar.ts, 
                "event_type": "FATAL_INVARIANT", 
                "run_id": run_id,
                "payload": {"errors": invariants},
                "trace": asdict(trace_ids)
            }
            events.append(ev)
            break
            
        # Demo Decision: purely hypothetical
        decision = "HOLD"
        # Deterministic dummy rule:
        # If close > open -> BUY signal (if no pos)
        # But for Phase-3 scope, we just log DECISION and evaluate GATES.
        
        # Evaluate Gates at every bar? Or only on Signal?
        # Let's evaluate Gates on every bar for "Continuous Monitoring"
        
        # Build TS from candidate meta
        build_ts = candidate_meta.get("build_ts", "")
        # "Now" is the bar timestamp (simulation time)
        now_ts_sec = bar.ts / 1000.0 
        
        gate_results = eval_all_gates(
            symbol=candidate_meta.get("symbol", "UNKNOWN"),
            price=bar.close,
            desired_qty=1.0, # hypothetical
            state=state,
            risk_cfg=risk_cfg,
            gov_cfg=gov_cfg,
            candidate_build_ts=build_ts,
            now_ts=now_ts_sec
        )
        
        # Store last gate result
        gate_history = gate_results
        
        # Log Event
        ev = {
            "ts": bar.ts,
            "event_type": "CYCLE_STEP",
            "run_id": run_id,
            "payload": {
                "bar_close": bar.close,
                "decision": decision,
                "gates": [asdict(g) for g in gate_results]
            },
            "trace": asdict(trace_ids)
        }
        events.append(ev)
        
        # Update State (noop for demo)
        state.strategy.last_bar_ts = bar.ts
        
    # 3. Finalize & Persist
    
    # Write events.ndjson
    events_path = os.path.join(runs_dir, "events.ndjson")
    with open(events_path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")
            
    # Write gates.json (snapshot of last bar)
    gates_path = os.path.join(runs_dir, "gates.json")
    with open(gates_path, "w", encoding="utf-8") as f:
        json.dump([asdict(g) for g in gate_history], f, indent=2)
        
    # Write meta.json
    meta = {
        "run_id": run_id,
        "created_ts": int(time.time()),
        "candidate": candidate_meta,
        "trace": asdict(trace_ids),
        "event_count": len(events)
    }
    meta_path = os.path.join(runs_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        
    return meta
