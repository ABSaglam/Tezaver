import os
import json
import time
from typing import Optional, Dict, List
from dataclasses import asdict

from tezaver.matrix.core.trace import TraceIds
from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig, eval_all_gates
from tezaver.matrix.core.state import RunState
from tezaver.matrix.core.approval import apply_run_result
from tezaver.matrix.core.judge import judge_run
from tezaver.matrix.core.jury import compute_scorecard
from tezaver.matrix.core.audit import compute_audit_from_events
from tezaver.matrix.ports.data_port import DataPort
from tezaver.matrix.ports.broker_port import BrokerPort
from tezaver.matrix.ports.store_port import StorePort

def parse_timeframe_ms(tf: str) -> int:
    """Simple timeframe parser to milliseconds."""
    try:
        if tf.endswith("m"): return int(tf[:-1]) * 60 * 1000
        if tf.endswith("h"): return int(tf[:-1]) * 60 * 60 * 1000
        if tf.endswith("d"): return int(tf[:-1]) * 24 * 60 * 60 * 1000
    except:
        pass
    # Fallback or error
    if tf == "1m": return 60000
    if tf == "5m": return 300000
    if tf == "15m": return 900000
    if tf == "1h": return 3600000
    if tf == "4h": return 14400000
    if tf == "1d": return 86400000
    return 60000 # Default to 1m if unknown

def init_live_state(timeframe: str, tf_ms: int, bars_fingerprint: str) -> dict:
    return {
        "cursor": 0,
        "last_bar_ts": 0,
        "timeframe": timeframe,
        "tf_ms": tf_ms,
        "bars_fingerprint": bars_fingerprint
    }

def load_live_state(home: str, run_id: str) -> Optional[dict]:
    path = os.path.join(home, "runs", run_id, "live_state.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def save_live_state(home: str, run_id: str, state: dict) -> None:
    path = os.path.join(home, "runs", run_id, "live_state.json")
    with open(path, "w") as f:
        json.dump(state, f, indent=2)

def start_live_run(
    home: str,
    symbol: str,
    timeframe: str,
    candidate_build_ts: str,
    trace_ids: TraceIds,
    data: DataPort,
    broker: BrokerPort,
    store: StorePort,
    gov_cfg: GovernanceConfig,
    risk_cfg: RiskGateConfig
) -> str:
    # 1. Generate Run ID
    ts = int(time.time())
    run_id = f"run_{symbol}_{timeframe}_LIVE_{ts}"
    
    # 2. Meta
    meta = {
        "run_id": run_id,
        "run_profile": "LIVE",
        "created_ts": ts,
        "candidate": {
            "symbol": symbol,
            "timeframe": timeframe,
            "build_ts": candidate_build_ts
        },
        "trace": asdict(trace_ids),
        "config": {
            "risk": risk_cfg.__dict__,
            "gov": gov_cfg.__dict__
        }
    }
    store.create_run(run_id, meta)
    
    # 3. Initial State
    # For fingerprint, we can grab first bar TS or use trace data_fingerprint if reliable.
    # Let's use data_fingerprint from trace as authoritative ref.
    tf_ms = parse_timeframe_ms(timeframe)
    state = init_live_state(timeframe, tf_ms, trace_ids.data_fingerprint)
    save_live_state(home, run_id, state)
    
    # 4. RUN_START event
    store.append_event(run_id, {
        "ts": int(time.time() * 1000),
        "event_type": "RUN_START",
        "run_id": run_id,
        "payload": {},
        "trace": asdict(trace_ids)
    })
    
    return run_id

def live_step(
    home: str,
    run_id: str,
    steps: int,
    symbol: str,
    timeframe: str,
    trace_ids: TraceIds,
    data: DataPort,
    broker: BrokerPort,
    store: StorePort,
    gov_cfg: GovernanceConfig,
    risk_cfg: RiskGateConfig,
    candidate_id: str = ""
) -> dict:
    # 1. Load State
    state = load_live_state(home, run_id)
    if not state:
        raise ValueError(f"Live state not found for {run_id}")
    
    cursor = state["cursor"]
    last_bar_ts = state.get("last_bar_ts", 0)
    tf_ms = state.get("tf_ms", parse_timeframe_ms(timeframe))
    
    # 2. Get Data
    bars = data.get_closed_bars(symbol, timeframe)
    
    # 3. Process Steps
    steps_done = 0
    now_ts = time.time()
    
    # RunState for gates
    run_state = RunState() 
    
    processed_count = 0
    
    while steps_done < steps and cursor < len(bars):
        bar_obj = bars[cursor]
        bar = asdict(bar_obj)
        
        # Gap Detection
        if last_bar_ts > 0:
            diff = bar["ts"] - last_bar_ts
            # If diff > 1.1 * tf_ms, it's a gap
            if diff > (1.1 * tf_ms):
                missing = diff - tf_ms
                store.append_event(run_id, {
                     "ts": int(time.time() * 1000),
                     "event_type": "GAP_DETECTED",
                     "run_id": run_id,
                     "payload": {
                         "prev_ts": last_bar_ts,
                         "next_ts": bar["ts"],
                         "expected_ms": tf_ms,
                         "missing_ms": missing
                     },
                     "trace": asdict(trace_ids)
                })
                # Reconnect Event
                store.append_event(run_id, {
                     "ts": int(time.time() * 1000),
                     "event_type": "RECONNECT",
                     "run_id": run_id,
                     "payload": {"mode": "SIM_RECONNECT", "reason": "Gap detected"},
                     "trace": asdict(trace_ids)
                })
        
        # Bar Event
        store.append_event(run_id, {
             "ts": int(time.time() * 1000),
             "event_type": "BAR",
             "run_id": run_id,
             "payload": bar,
             "trace": asdict(trace_ids)
        })
        
        # Decision (HOLD for live MVP)
        store.append_event(run_id, {
             "ts": int(time.time() * 1000),
             "event_type": "DECISION",
             "run_id": run_id,
             "payload": {"action": "HOLD", "reason": "Live MVP"},
             "trace": asdict(trace_ids)
        })
        
        # Gates Eval
        gate_results = eval_all_gates(
            symbol=symbol,
            price=bar["close"], # or c
            desired_qty=0, # HOLD
            state=run_state,
            risk_cfg=risk_cfg,
            gov_cfg=gov_cfg,
            candidate_build_ts="", # Pass empty or allow loading?
            now_ts=now_ts
        )
        
        store.append_event(run_id, {
             "ts": int(time.time() * 1000),
             "event_type": "GATE_EVAL",
             "run_id": run_id,
             "payload": {"results": [g.__dict__ for g in gate_results]},
             "trace": asdict(trace_ids)
        })
        
        # Update Loop State
        last_bar_ts = bar["ts"]
        cursor += 1
        steps_done += 1
        processed_count += 1
        
    # 4. Heartbeat (instead of run end)
    store.append_event(run_id, {
        "ts": int(time.time() * 1000),
        "event_type": "LIVE_HEARTBEAT",
        "run_id": run_id,
        "payload": {"cursor": cursor, "total_bars": len(bars), "processed": processed_count},
        "trace": asdict(trace_ids)
    })
    
    # 5. Update State
    state["cursor"] = cursor
    state["last_bar_ts"] = last_bar_ts
    save_live_state(home, run_id, state)
    
    # 6. Update Proofs (Judge, Scorecard, Approval)
    # Re-read all events to compute cumulative proofs
    events_path = os.path.join(home, "runs", run_id, "events.ndjson")
    event_lines = []
    if os.path.exists(events_path):
        with open(events_path) as f:
            event_lines = f.readlines()
            
    # Audit
    audit = compute_audit_from_events(event_lines)
    # Write Audit
    with open(os.path.join(home, "runs", run_id, "audit.json"), "w") as f:
        json.dump(audit, f, indent=2)
            
    # Scorecard (from file)
    scorecard = compute_scorecard(home, run_id)
    # Write Scorecard
    with open(os.path.join(home, "runs", run_id, "scorecard.json"), "w") as f:
        json.dump(scorecard, f, indent=2)
        
    judge = judge_run(home, run_id, scorecard)
    # Write Judge
    with open(os.path.join(home, "runs", run_id, "judge.json"), "w") as f:
        json.dump(judge, f, indent=2)
        
    # Apply Result
    final_res = apply_run_result(home, run_id, judge, candidate_id, run_profile="LIVE")
    
    return {
        "run_id": run_id,
        "steps_processed": processed_count,
        "cursor": cursor,
        "total_bars": len(bars),
        "verdict": judge.get("overall", "UNKNOWN"),
        "stage": final_res.get("stage", "UNKNOWN")
    }
