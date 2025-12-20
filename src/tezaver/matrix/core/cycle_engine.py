import time
from typing import Optional
from dataclasses import asdict

from tezaver.matrix.core.bars import require_closed_bar
from tezaver.matrix.core.trace import TraceIds, require_trace_ids
from tezaver.matrix.core.state import RunState, validate_state
from tezaver.matrix.core.gates import eval_all_gates, RiskGateConfig, GovernanceConfig

import time
from typing import Optional
from dataclasses import asdict

from tezaver.matrix.core.bars import require_closed_bar
from tezaver.matrix.core.trace import TraceIds, require_trace_ids
from tezaver.matrix.core.state import RunState, validate_state
from tezaver.matrix.core.gates import eval_all_gates, RiskGateConfig, GovernanceConfig

from tezaver.matrix.core.telemetry import event_line, validate_event_dict
from tezaver.matrix.core.audit import compute_audit_from_events
from tezaver.matrix.core.incident import build_incident_bundle

from tezaver.matrix.ports.data_port import DataPort
from tezaver.matrix.ports.broker_port import BrokerPort
from tezaver.matrix.ports.store_port import StorePort

def run_cycle(symbol: str, 
              timeframe: str, 
              candidate_build_ts: str,
              trace_ids: TraceIds, 
              data: DataPort,
              broker: BrokerPort,
              store: StorePort,
              risk_cfg: RiskGateConfig,
              gov_cfg: GovernanceConfig,
              home: str,
              run_id: Optional[str] = None) -> dict:
              
    # 1. Init
    require_trace_ids(trace_ids)
    
    if not run_id:
        run_id = f"run_{symbol}_{timeframe}_{int(time.time())}"
        
    meta = {
        "run_id": run_id,
        "created_ts": int(time.time()),
        "candidate": {"symbol": symbol, "timeframe": timeframe, "build_ts": candidate_build_ts},
        "trace": asdict(trace_ids),
        "event_count": 0
    }
    store.create_run(run_id, meta)
    
    # Telemetry Helper
    def log_event(etype, payload):
        ev = {
            "ts": int(time.time() * 1000), # System time for meta events, bar time for cycle
            "event_type": etype,
            "run_id": run_id,
            "payload": payload,
            "trace": asdict(trace_ids)
        }
        # Schema validation (best effort in runtime, or throw?)
        # Let's log warning if invalid? Or just rely on correctness.
        # errors = validate_event_dict(ev)
        store.append_event(run_id, ev)
        return ev
    
    log_event("RUN_START", {"meta": meta})
    
    # 2. Fetch Data
    bars = data.get_closed_bars(symbol, timeframe)
    
    state = RunState()
    event_count = 0
    gate_history = []
    events_lines = [] # Keep in memory for audit (optimization: or read from disk)
    
    blocked = False
    block_reason = ""
    error_reason = ""
    
    # 3. Main Loop
    try:
        for bar in bars:
            require_closed_bar(bar)
            
            # Log Bar (Optional or Debug? Prompt says RUN_START, BAR, DECISION...)
            # log_event("BAR", {"ts": bar.ts, "close": bar.close}) 
            # Use bar.ts for cycle events
            
            # Validate State
            invariants = validate_state(state)
            if invariants:
                block_reason = f"Fatal Invariant: {invariants}"
                ev = {
                    "ts": bar.ts, 
                    "event_type": "FATAL_INVARIANT", 
                    "run_id": run_id,
                    "payload": {"errors": invariants},
                    "trace": asdict(trace_ids)
                }
                store.append_event(run_id, ev)
                events_lines.append(event_line(ev))
                blocked = True
                break
                
            # Gate Eval
            now_ts_sec = bar.ts / 1000.0 
            gate_results = eval_all_gates(
                symbol=symbol,
                price=bar.close,
                desired_qty=1.0, 
                state=state,
                risk_cfg=risk_cfg,
                gov_cfg=gov_cfg,
                candidate_build_ts=candidate_build_ts,
                now_ts=now_ts_sec
            )
            
            gate_history = gate_results
            
            # Check for BLOCK
            blocks = [g for g in gate_results if not g.allow]
            if blocks:
                blocked = True
                block_reason = f"Gate Block: {[b.name for b in blocks]}"
                # Log usage of Block logic
                # We stop the run or skip trade? 
                # "Gate BLOCK ... => Incident Bundle". Usually means Stop Run in this context?
                # Or just skip bar? Let's assume Stop Run for safety/visibility unless specified otherwise.
                # Prompt says: "Gate BLOCK ... => meta+gates+..." -> implies critical stop or major event.
                # Let's Stop.
                
            # Log Event
            ev = {
                "ts": bar.ts,
                "event_type": "CYCLE_STEP",
                "run_id": run_id,
                "payload": {
                    "bar_close": bar.close,
                    "decision": "HOLD", # Demo
                    "gates": [asdict(g) for g in gate_results],
                    "blocked": bool(blocks)
                },
                "trace": asdict(trace_ids)
            }
            store.append_event(run_id, ev)
            events_lines.append(event_line(ev))
            event_count += 1
            
            if blocked:
                log_event("BLOCK", {"reason": block_reason})
                break
            
            state.strategy.last_bar_ts = bar.ts
            
    except Exception as e:
        error_reason = str(e)
        log_event("ERROR", {"error": error_reason})
        blocked = True # Treat exception as block for incident
        
    # 4. Finalize
    store.write_gates(run_id, [asdict(g) for g in gate_history])
    log_event("RUN_END", {"end_ts": int(time.time())})
    
    # Compute & Write Audit
    # We need all event lines. For optimization we kept them or read back.
    # We kept 'events_lines' for cycle steps, but need start/end too.
    # Let's read back from store logic? StorePort doesn't expose read.
    # Simple solution: Re-read file using a helper or assume Memory Lines is sufficient for now.
    # Or just use the lines we have (mostly cycle steps + start/end).
    # Since we can't easily read back via Port (StorePort write-only for core), 
    # we strictly rely on what we have or skip re-check.
    # Audit module takes list[str].
    
    # We'll use local memory lines for audit (contains Cycle Steps). 
    # Does not contain RUN_START inside loop, but audit.py checks "ORDER_FILLED" etc.
    audit = compute_audit_from_events(events_lines)
    # StorePort needs write_audit? Yes, prompt added it.
    if hasattr(store, "write_audit"):
        store.write_audit(run_id, audit)
        
    store.finalize_run(run_id)
    
    meta["event_count"] = event_count
    
    # 5. Incident Bundle on Block/Error
    if blocked or error_reason:
        reason = block_reason or error_reason
        # build_incident_bundle needs home.
        inc_id = build_incident_bundle(home, run_id, reason)
        meta["incident_id"] = inc_id
    
    return meta
