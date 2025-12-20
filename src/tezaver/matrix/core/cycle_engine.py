import time
from typing import Optional
from dataclasses import asdict

from tezaver.matrix.core.bars import require_closed_bar
from tezaver.matrix.core.trace import TraceIds, require_trace_ids
from tezaver.matrix.core.state import RunState, validate_state
from tezaver.matrix.core.gates import eval_all_gates, RiskGateConfig, GovernanceConfig

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
    
    # 2. Fetch Data
    bars = data.get_closed_bars(symbol, timeframe)
    
    state = RunState()
    event_count = 0
    gate_history = []
    
    # 3. Main Loop
    for bar in bars:
        require_closed_bar(bar)
        
        # Validate State
        invariants = validate_state(state)
        if invariants:
            ev = {
                "ts": bar.ts, 
                "event_type": "FATAL_INVARIANT", 
                "run_id": run_id,
                "payload": {"errors": invariants},
                "trace": asdict(trace_ids)
            }
            store.append_event(run_id, ev)
            break
            
        # Decision
        decision = "HOLD"
        # Deterministic simple rule:
        # If close > open -> BUY signal (hypothetically)
        # But for Phase-4 scope, keep HOLD to simplify.
        
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
        store.append_event(run_id, ev)
        event_count += 1
        
        state.strategy.last_bar_ts = bar.ts
        
    # 4. Finalize
    store.write_gates(run_id, [asdict(g) for g in gate_history])
    store.finalize_run(run_id)
    
    meta["event_count"] = event_count
    # Optimization: update meta file? Not strictly required by prompt but good practice.
    # store.create_run(run_id, meta) # Overwrite meta if store supports it
    
    return meta
