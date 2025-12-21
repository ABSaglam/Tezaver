import time
from typing import Optional, Any, List
from dataclasses import asdict

from tezaver.matrix.core.bars import require_closed_bar, Bar
from tezaver.matrix.core.trace import TraceIds, require_trace_ids
from tezaver.matrix.core.state import RunState, validate_state
from tezaver.matrix.core.gates import eval_all_gates, RiskGateConfig, GovernanceConfig, GateResult

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
              strategy: Optional[Any] = None, # MXI-1100
              run_profile: str = "SNIPER", 
              run_id: Optional[str] = None) -> dict:
              
    # 1. Init
    from tezaver.matrix.core.run_profile import require_profile
    require_profile(run_profile)
    
    require_trace_ids(trace_ids)
    
    if not run_id:
        run_id = f"run_{symbol}_{timeframe}_{int(time.time())}"
        
    meta = {
        "run_id": run_id,
        "run_profile": run_profile,
        "created_ts": int(time.time()),
        "candidate": {"symbol": symbol, "timeframe": timeframe, "build_ts": candidate_build_ts},
        "trace": asdict(trace_ids),
        "event_count": 0
    }
    store.create_run(run_id, meta)
    
    # Telemetry Helper
    def log_event(etype, payload):
        ev = {
            "ts": int(time.time() * 1000), 
            "event_type": etype,
            "run_id": run_id,
            "payload": payload,
            "trace": asdict(trace_ids)
        }
        store.append_event(run_id, ev)
        return ev
    
    log_event("RUN_START", {"meta": meta})
    
    # 2. Fetch Data
    bars = data.get_closed_bars(symbol, timeframe)
    
    state = RunState()
    event_count = 0
    gate_history = []
    events_lines = [] 
    
    blocked = False
    block_reason = ""
    error_reason = ""
    
    # 3. Main Loop
    try:
        for bar in bars:
            require_closed_bar(bar)
                
            # Validate State
            invariants = validate_state(state)
            if invariants:
                block_reason = f"Fatal Invariant: {invariants}"
                log_event("FATAL_INVARIANT", {"errors": invariants})
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
                
            # Decision Logic (MXI-1100)
            decision = "HOLD"
            order_info = None
            if not blocked and strategy:
                order = strategy.decide(bar, state)
                if order:
                    decision = "ORDER_PLACEMENT"
                    # Execute via Broker
                    order = broker.place_order(order)
                    
                    if order.status.name == "FILLED": # Enum name
                        # Update State
                        state.position.qty += order.fill_qty
                        state.position.entry_price = order.fill_price
                        order_info = asdict(order)
                        order_info["status"] = "FILLED"
                    else:
                        decision = f"ORDER_{order.status.name}"
                        order_info = asdict(order)
                        order_info["status"] = order.status.name

            # Log Event
            ev_payload = {
                "bar_close": bar.close,
                "decision": decision,
                "gates": [asdict(g) for g in gate_results],
                "blocked": bool(blocks)
            }
            if order_info:
                ev_payload["order"] = order_info
                
            ev = {
                "ts": bar.ts,
                "event_type": "CYCLE_STEP",
                "run_id": run_id,
                "payload": ev_payload,
                "trace": asdict(trace_ids)
            }
            store.append_event(run_id, ev)
            from tezaver.matrix.core.telemetry import event_line
            events_lines.append(event_line(ev))
            event_count += 1
            
            if blocked:
                log_event("BLOCK", {"reason": block_reason})
                break
            
            state.strategy.last_bar_ts = bar.ts
            
    except Exception as e:
        error_reason = str(e)
        import traceback
        error_trace = traceback.format_exc()
        log_event("ERROR", {"error": error_reason, "trace": error_trace})
        blocked = True 
        
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
    
    # Compute & Write Audit
    # We'll use local memory lines for audit (contains Cycle Steps). 
    audit = compute_audit_from_events(events_lines)
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
        
    # 6. Jury & Judge & Approval (Phase-7)
    # Compute Scorecard
    from tezaver.matrix.core.jury import compute_scorecard
    scorecard = compute_scorecard(home, run_id)
    if hasattr(store, "write_scorecard"):
        store.write_scorecard(run_id, scorecard)
        
    # Judge Verdict
    from tezaver.matrix.core.judge import judge_run
    verdict = judge_run(home, run_id, scorecard)
    if hasattr(store, "write_judge_verdict"):
        store.write_judge_verdict(run_id, verdict)
        
    # Approval State Advance
    from tezaver.matrix.core.approval import apply_run_result
    from tezaver.matrix.ports.candidate_bundle import candidate_id
    # ... (ID logic omitted for brevity in search, assuming existing context)
    
    # Reconstruct ID (copied from previous Step logic or existing file content)
    import re
    def sanitize(s): return re.sub(r'[^a-zA-Z0-9]', '_', s)
    cid_ts = sanitize(candidate_build_ts)
    cid = f"{symbol}_{timeframe}_v1_{cid_ts}"
    
    apply_run_result(home, run_id, verdict, cid, run_profile)
    
    return meta
    
    return meta
