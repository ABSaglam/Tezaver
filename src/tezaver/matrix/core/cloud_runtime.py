import os
import json
import time
import uuid
from typing import List, Dict, Any

def list_active_strategies(home: str) -> List[str]:
    reg_dir = os.path.join(home, "cloud_registry", "strategies")
    if not os.path.exists(reg_dir):
        return []
    
    active = []
    for sid in os.listdir(reg_dir):
        s_dir = os.path.join(reg_dir, sid)
        if not os.path.isdir(s_dir): continue
        
        # Check status.json
        stat_path = os.path.join(s_dir, "status.json")
        if os.path.exists(stat_path):
            try:
                with open(stat_path) as f: s = json.load(f)
                if s.get("status") == "ACTIVE":
                    active.append(sid)
            except:
                pass
                
    return sorted(active)

def _ensure_runtime_dirs(home: str) -> str:
    r_dir = os.path.join(home, "cloud_runtime")
    os.makedirs(os.path.join(r_dir, "runs"), exist_ok=True)
    os.makedirs(os.path.join(r_dir, "strategies"), exist_ok=True)
    return r_dir

def start_or_load_runtime_state(home: str) -> Dict[str, Any]:
    r_dir = _ensure_runtime_dirs(home)
    state_path = os.path.join(r_dir, "state.json")
    
    if os.path.exists(state_path):
        with open(state_path) as f: return json.load(f)
        
    # Create new run
    run_id = f"CLOUDRUN_{int(time.time())}"
    state = {
        "cloud_run_id": run_id,
        "started_ts": int(time.time()),
        "last_tick_ts": 0,
        "total_ticks": 0
    }
    
    # Init run dir
    run_dir = os.path.join(r_dir, "runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "meta.json"), "w") as f:
        json.dump({"run_id": run_id, "type": "CLOUD_RUNTIME", "ts": int(time.time())}, f)
        
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)
        
    return state

def append_runtime_event(home: str, cloud_run_id: str, event: Dict[str, Any]) -> None:
    path = os.path.join(home, "cloud_runtime", "runs", cloud_run_id, "events.ndjson")
    with open(path, "a") as f:
        f.write(json.dumps(event) + "\n")

def load_strategy_state(home: str, strategy_id: str) -> Dict[str, Any]:
    path = os.path.join(home, "cloud_runtime", "strategies", strategy_id, "state.json")
    if os.path.exists(path):
        with open(path) as f: return json.load(f)
    return None

def save_strategy_state(home: str, strategy_id: str, state: Dict[str, Any]) -> None:
    d = os.path.join(home, "cloud_runtime", "strategies", strategy_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "state.json"), "w") as f:
        json.dump(state, f, indent=2)
        
def parse_tf_ms(tf: str) -> int:
    # Minimal parser: 15m, 1h, 4h, 1d
    if tf.endswith("s"): return int(tf[:-1]) * 1000
    if tf.endswith("m"): return int(tf[:-1]) * 60 * 1000
    if tf.endswith("h"): return int(tf[:-1]) * 60 * 60 * 1000
    if tf.endswith("d"): return int(tf[:-1]) * 24 * 60 * 60 * 1000
    if tf == "1M": return 30 * 24 * 60 * 60 * 1000 # Approx
    return 15 * 60 * 1000 # Default fallback

    # Import Paper Broker & Risk
    from tezaver.matrix.core.paper_broker import execute_paper_order, load_portfolio
    from tezaver.matrix.core.global_risk import should_block_decision, load_global_risk, compute_totals
    from tezaver.matrix.core.broker_config import load_broker_config
    from tezaver.matrix.adapters.broker_real_dryrun import RealDryRunBroker
    
    # We need risk config passed in or load it?
    # Better pass it in args or load once per tick in caller.
    # Let's assume passed in `runtime_context` dict?
    # Or just load it again? It's cheap file read.
    # But for consistency across strategies in same tick, caller should pass it.
    # Updating signature is invasive.
    # Let's load it here for now or update signature. 
    # Actually, `cloud_runtime_tick` loads it. We can pass it if we change signature.
    # Let's change `strategy_step` signature to accept `risk_config` and `risk_totals`.
    


def pool_step(home: str, cloud_run_id: str, stage: str, risk_cfg: dict, broker_cfg: dict) -> Dict[str, Any]:
    """
    Execute the Matrix Pool Court System (15m Trigger).
    
    Roles:
      - Orchestrator: Gather Evidence (Defender/Prosecutor inside)
      - Court: Judge the Evidence
      - Idempotency: Skip if run_id already exists.
    
    Returns:
       Verdict and Status.
    """
    from tezaver.matrix.pool.pool_orchestrator_v1 import run_pool_evidence_bundle
    from tezaver.matrix.pool_court.pool_court_runner_v1 import run_pool_court
    from tezaver.matrix.bundles.bundle_registry import BundleRegistry
    from tezaver.matrix.pool.pool_reports_v1 import resolve_reports_dir
    
    # -- 1. 15m Tick Trigger & Run ID Generation --
    # "closed-bar only: henüz kapanmamış bar ile karar yok."
    # We round down current time to nearest 15m.
    # e.g. 10:38:33 -> 10:30:00. This is the "Current Open Bar Start".
    # The "Last Closed Bar" is 10:15:00.
    # We assume we run ONCE per Closed Bar.
    # So we target the candle that JUST closed.
    
    now_ts = int(time.time())
    window_s = 15 * 60
    current_window_start = (now_ts // window_s) * window_s
    last_closed_bar_ts = current_window_start - window_s
    
    # Deterministic Run ID: "POOL_BTCUSDT_15m_<TS>"
    # User said: "symbol + timeframe + last_closed_bar_ts"
    # Scope: Single Coin (BTCUSDT) for now.
    symbol = "BTCUSDT"
    timeframe = "15m"
    
    # We use ISO format for ID to be readable? Or integer? 
    # Integer is safer for paths.
    run_id = f"POOL_{symbol}_{timeframe}_{last_closed_bar_ts}"
    
    # -- 2. Idempotency Check --
    # Check if this run_id already has a result.
    # resolve_reports_dir resolves to 'out/matrix_runs/<stage>/<run_id>/reports'
    reports_dir = resolve_reports_dir(stage, run_id, home)
    verdict_path = os.path.join(reports_dir, "pool_court_verdict_v1.json")
    
    if os.path.exists(verdict_path):
        # Already run!
        return {"status": "SKIPPED_IDEMPOTENT", "run_id": run_id}
        
    # -- 3. Setup Registry (Hot Reload) --
    registry = BundleRegistry()
    registry.discover_and_load(os.path.join(home, ".tezaver_matrix", "approved_bundles_v1"))
    
    # -- 4. Execution Context --
    trace_ctx = {
        "engine_version": "v1.0.0",
        "data_fingerprint": f"TICK_{now_ts}",
        "config_signature": "UNKNOWN"
    }

    # Closed bars map for Defender
    # We MUST tell Defender that the 15m bar at `last_closed_bar_ts` is CLOSED.
    from datetime import datetime, timezone
    closed_iso = datetime.fromtimestamp(last_closed_bar_ts, timezone.utc).isoformat()
    closed_bars = {"15m": closed_iso}
    
    try:
        # -- 5. Orchestrator (Evidence) --
        evidence = run_pool_evidence_bundle(
            stage, run_id, trace_ctx, registry,
            options={
                "closed_bars": closed_bars,
                "kill_switch_triggered": risk_cfg.get("paused", False),
                "global_limits": risk_cfg
            }
        )
        
        # -- 6. Court (Verdict) --
        verdict_res = run_pool_court(stage, run_id, trace_ctx)
        
        # Log to Event Stream
        # Log to Event Stream
        append_runtime_event(home, cloud_run_id, {
            "ts": int(time.time()*1000), 
            "type": "POOL_COURT_VERDICT",
            "payload": {
                "verdict": verdict_res["verdict"],
                "decision_action": verdict_res.get("decision_action", "UNKNOWN"),
                "run_id": run_id,
                "tick_ts": last_closed_bar_ts
            }
        })
        
        # -- 7. Action Bridge (TODO: Execution) --
        # If ALLOW, we would generate orders here.
        
        return {
            "status": "OK", 
            "verdict": verdict_res["verdict"], 
            "decision_action": verdict_res.get("decision_action", "UNKNOWN"),
            "run_id": run_id
        }
        
    except Exception as e:
        err = str(e)
        append_runtime_event(home, cloud_run_id, {
            "ts": int(time.time()*1000), 
            "type": "POOL_ERROR", 
            "payload": {"error": err, "run_id": run_id}
        })
        return {"status": "ERROR", "error": err, "run_id": run_id}


def strategy_step(home: str, cloud_run_id: str, strategy_id: str, strategy_json: dict, steps: int, 
                  risk_config: dict = None, risk_totals: dict = None, broker_config: dict = None) -> Dict[str, Any]:
    # 1. Check Bars Source
    bs = strategy_json.get("bars_source")
    if not bs or bs.get("type") != "JSON_FILE" or not bs.get("path"):
        evt = {
            "ts": int(time.time() * 1000), "type": "STRATEGY_SKIPPED",
            "strategy_id": strategy_id, "payload": {"reason": "NO_BARS_SOURCE"}
        }
        append_runtime_event(home, cloud_run_id, evt)
        return {"skipped": True, "reason": "NO_BARS_SOURCE"}
        
    # 2. Load Bars
    b_path = bs["path"]
    if not os.path.exists(b_path):
        evt = {
            "ts": int(time.time() * 1000), "type": "STRATEGY_SKIPPED",
            "strategy_id": strategy_id, "payload": {"reason": "BARS_FILE_MISSING", "path": b_path}
        }
        append_runtime_event(home, cloud_run_id, evt)
        return {"skipped": True, "reason": "BARS_FILE_MISSING"}
        
    try:
        with open(b_path) as f: bars = json.load(f)
    except Exception as e:
        evt = {
            "ts": int(time.time() * 1000), "type": "STRATEGY_SKIPPED",
            "strategy_id": strategy_id, "payload": {"reason": "BARS_LOAD_ERROR", "error": str(e)}
        }
        append_runtime_event(home, cloud_run_id, evt)
        return {"skipped": True, "reason": "BARS_LOAD_ERROR"}
        
    # 3. Load State
    state = load_strategy_state(home, strategy_id)
    if not state:
        tf_ms = parse_tf_ms(strategy_json.get("timeframe", "15m"))
        state = {
            "cursor": 0,
            "last_ts": 0,
            "tf_ms": tf_ms,
            "bars_fingerprint": str(os.path.getmtime(b_path)) # Simple fingerpint for now
        }
        
    cursor = state["cursor"]
    last_ts = state["last_ts"]
    tf_ms = state["tf_ms"]
    
    # 4. Advance
    advanced = 0
    final_ts = int(time.time() * 1000)
    
    # Import Paper Broker logic access
    from tezaver.matrix.core.paper_broker import execute_paper_order, load_portfolio
    from tezaver.matrix.core.global_risk import should_block_decision
    from tezaver.matrix.adapters.broker_real_dryrun import RealDryRunBroker
    
    for _ in range(steps):
        if cursor >= len(bars): break
        
        bar = bars[cursor]
        if not bar.get("closed", False) and not bar.get("is_closed", False):
            break
            
        bar_ts = bar["ts"]
        
        # Gap Check
        if last_ts > 0 and (bar_ts - last_ts) > (1.1 * tf_ms):
             evt = {
                "ts": int(time.time() * 1000), "type": "STRATEGY_GAP_DETECTED",
                "strategy_id": strategy_id,
                "payload": {"last_ts": last_ts, "current_ts": bar_ts, "delta": bar_ts - last_ts}
             }
             append_runtime_event(home, cloud_run_id, evt)
             
             evt_rec = {
                "ts": int(time.time() * 1000), "type": "STRATEGY_RECONNECT",
                "strategy_id": strategy_id, "payload": {}
             }
             append_runtime_event(home, cloud_run_id, evt_rec)
             
        # Bar Event
        evt_bar = {
            "ts": int(time.time() * 1000), "type": "STRATEGY_BAR",
            "strategy_id": strategy_id,
            "payload": {"bar_ts": bar_ts, "close": bar["close"]}
        }
        append_runtime_event(home, cloud_run_id, evt_bar)
        
        # Decision Logic (Demo Rule: Green->BUY, Red->SELL)
        pf = load_portfolio(home, strategy_id)
        qty = pf["position_qty"]
        action = "HOLD"
        
        open_p = bar.get("open", 0)
        close_p = bar.get("close", 0)
        
        if close_p > open_p and qty == 0:
            action = "BUY"
        elif close_p < open_p and qty > 0:
            action = "SELL"
            
        # Risk Check
        blocked_reason = None
        if action == "BUY" and risk_config and risk_totals:
            if should_block_decision(risk_config, risk_totals, action):
                blocked_reason = "GLOBAL_RISK_LIMIT"
                action = "HOLD" # Force Hold
                
        # Execute
        broker_mode = broker_config.get("mode", "PAPER") if broker_config else "PAPER"
        
        if action in ["BUY", "SELL"]:
            if broker_mode == "PAPER":
                # Regular Paper Execution
                execute_paper_order(home, strategy_id, action, 1.0, close_p, bar_ts)
                # Update totals for next iteration
                if action == "BUY" and risk_totals: risk_totals["open_positions"] += 1
                if action == "SELL" and risk_totals: risk_totals["open_positions"] = max(0, risk_totals["open_positions"] - 1)
                
            elif broker_mode == "REAL_DRYRUN":
                # Real DryRun Execution (Legacy/Simple)
                broker = RealDryRunBroker(reduce_only=broker_config.get("reduce_only", True))
                symbol = strategy_json.get("symbol", "UNKNOWN")
                res = broker.place_order(strategy_id, symbol, action, 1.0, close_p, bar_ts)
                
                evt_real = {
                    "ts": int(time.time() * 1000), "type": "REAL_ORDER_WOULD_SEND",
                    "strategy_id": strategy_id, "payload": res
                }
                append_runtime_event(home, cloud_run_id, evt_real)
                execute_paper_order(home, strategy_id, action, 1.0, close_p, bar_ts)
                if action == "BUY" and risk_totals: risk_totals["open_positions"] += 1
                if action == "SELL" and risk_totals: risk_totals["open_positions"] = max(0, risk_totals["open_positions"] - 1)

            elif broker_mode == "REAL_BINANCE_STUB":
                # 1. Secrets Gate
                from tezaver.matrix.core.secrets import load_binance_secrets
                secrets = load_binance_secrets(home)
                
                if not secrets["present"]:
                    evt_mis = {
                        "ts": int(time.time() * 1000), "type": "BROKER_MISCONFIG",
                        "strategy_id": strategy_id,
                        "payload": {"reason": "SECRETS_MISSING", "mode": broker_mode}
                    }
                    append_runtime_event(home, cloud_run_id, evt_mis)
                    
                    if action == "BUY":
                        # Block BUY if secrets missing
                        action = "HOLD"
                        blocked_reason = "SECRETS_MISSING"
                    # SELL is allowed? In real logic yes to reduce risk, but without secrets we CANNOT communicate with exchange effectively even in Stub mode (conceptually).
                    # But Stub doesn't need real secrets to run code.
                    # HOWEVER, user requirement says: "secrets present değilse FAIL ... BUY blokla ... SELL serbest (reduce-only mantığı)"
                    # BUT enforce check: "write BROKER_MISCONFIG reason=SECRETS_MISSING"
                    
                else: 
                    # 2. Stub Execution
                    from tezaver.matrix.adapters.binance_client_stub import BinanceClientStub
                    stub = BinanceClientStub(secrets["api_key"], secrets["api_secret"], secrets["testnet"])
                    symbol = strategy_json.get("symbol", "UNKNOWN")
                    
                    # Call Stub
                    res = stub.place_order(symbol, action, 1.0, close_p, broker_config.get("reduce_only", True), bar_ts)
                    
                    evt_real = {
                        "ts": int(time.time() * 1000), "type": "REAL_ORDER_WOULD_SEND",
                        "strategy_id": strategy_id,
                        "payload": {"mode": "REAL_BINANCE_STUB", "response": res}
                    }
                    append_runtime_event(home, cloud_run_id, evt_real)
                    
                    # Simulate Fill for Portfolio Consistency
                    execute_paper_order(home, strategy_id, action, 1.0, close_p, bar_ts)
                    if action == "BUY" and risk_totals: risk_totals["open_positions"] += 1
                    if action == "SELL" and risk_totals: risk_totals["open_positions"] = max(0, risk_totals["open_positions"] - 1)
                    if action == "BUY" and risk_totals: risk_totals["open_positions"] += 1
                    if action == "SELL" and risk_totals: risk_totals["open_positions"] = max(0, risk_totals["open_positions"] - 1)

            elif broker_mode == "REAL_BINANCE":
                # 0. ReduceOnly Guard
                from tezaver.matrix.core.reduce_only_guard import ReduceOnlyGuard
                ro_guard = ReduceOnlyGuard()
                reduce_only = broker_config.get("reduce_only", True)
                
                # Check Local Risk Totals for simple Open Pos check?
                # Ideally we check Portfolio.
                # Guard needs current position.
                # We use local portfolio for now as best estimate.
                from tezaver.matrix.core.paper_broker import load_portfolio
                pf = load_portfolio(home, strategy_id)
                curr_pos = pf.get("inventory", {}).get(strategy_json.get("symbol"), 0.0)
                
                violation = ro_guard.check_violation(action, reduce_only, curr_pos)
                if violation:
                     action = "HOLD"
                     blocked_reason = f"REDUCE_ONLY_VIOLATION: {violation}"
                     evt_v = {
                         "ts": int(time.time()*1000), "type": "REDUCE_ONLY_VIOLATION",
                         "strategy_id": strategy_id, "payload": {"reason": violation}
                     }
                     append_runtime_event(home, cloud_run_id, evt_v)
                
                # 1. Secrets Gate
                from tezaver.matrix.core.secrets import load_binance_secrets
                secrets = load_binance_secrets(home)
                
                if not secrets["present"]:
                    evt_mis = {
                        "ts": int(time.time() * 1000), "type": "BROKER_MISCONFIG",
                        "strategy_id": strategy_id,
                        "payload": {"reason": "SECRETS_MISSING", "mode": broker_mode}
                    }
                    append_runtime_event(home, cloud_run_id, evt_mis)
                    
                    if action == "BUY":
                         action = "HOLD"
                         blocked_reason = "SECRETS_MISSING"
                else:
                    # 2. Real Execution
                    from tezaver.matrix.adapters.binance_rest_client import BinanceRestClient
                    from tezaver.matrix.adapters.broker_binance_real import RealBinanceBroker
                    
                    # Init Client (Ideally cached or reused per tick, but for now init per step or tick)
                    # To avoid creating new session every step, we should move this up to tick scope or cache.
                    # But for now, ensuring correctness first.
                    base_url = broker_config.get("binance_base_url")
                    
                    client = BinanceRestClient(secrets["api_key"], secrets["api_secret"], secrets["testnet"], base_url)
                    # Sync time? Ideally once per tick if needed at start. For now client handles request signing.
                    # If drift is high, it might fail. Phase-14C.1 requirement says handle it.
                    # Let's simple sync on init here for safety, though slow.
                    # Optimized: Check if we have drift in state or shared dict?
                    # Sticking to safe simple impl: sync on instantiation if needed logic is inside client.
                    # Client.sync_time() needs valid network.
                    # Auto-sync logic is inside client (manual call required).
                    client.sync_time() 
                    
                    # Dry Run Override within REAL_BINANCE?
                    # User requirement says: "REAL_BINANCE only if config active".
                    # We assume if mode is REAL_BINANCE, we really send (unless strategy specific flag? No global config).
                    # Actually RealBinanceBroker supports dry_run arg.
                    # We should probably pass dry_run=False here since the mode IS REAL_BINANCE.
                    # If we want dry run we use REAL_DRYRUN or REAL_BINANCE_STUB.
                    
                    broker = RealBinanceBroker(client, dry_run=False, reduce_only=broker_config.get("reduce_only", True))
                    symbol = strategy_json.get("symbol", "UNKNOWN")
                    
                    res = broker.place_order(strategy_id, symbol, action, 1.0, close_p, bar_ts)
                    
                    evt_real = {
                        "ts": int(time.time() * 1000), "type": "REAL_ORDER_SENT", # Changed from WOULD_SEND to SENT
                        "strategy_id": strategy_id,
                        "payload": res
                    }
                    append_runtime_event(home, cloud_run_id, evt_real)
                    
                    if not res.get("accepted"):
                         # ERROR from Broker
                         evt_err = {
                             "ts": int(time.time() * 1000), "type": "BROKER_ERROR",
                             "strategy_id": strategy_id, "payload": res
                         }
                         append_runtime_event(home, cloud_run_id, evt_err)
                         
                    # Telemetry
                    meta = client.last_call_meta
                    meta["time_offset"] = client.time_offset_ms
                    evt_tel = {
                         "ts": int(time.time() * 1000), "type": "BROKER_TELEMETRY",
                         "payload": meta
                    }
                    append_runtime_event(home, cloud_run_id, evt_tel)
                    
                    # 3. State Consistency?
                    # If REAL, we should load position from Exchange?
                    # Phase-14C.1 is just Broker Adapter. Portfolio syncing is next.
                    # For now, we still mimic fill to keep Panel happy?
                    # "Emniyet (Safety) kuralları: 2) Yeni pozisyon açmayı gerektiren BUY ... Gate'ten geçmeden görme"
                    # We passed Gate (Secrets).
                    # We assume it fills? If real, it might fill later.
                    # For this phase, let's keep execute_paper_order as a "Shadow Tracking".
                    execute_paper_order(home, strategy_id, action, 1.0, close_p, bar_ts)
                    if action == "BUY" and risk_totals: risk_totals["open_positions"] += 1
                    if action == "SELL" and risk_totals: risk_totals["open_positions"] = max(0, risk_totals["open_positions"] - 1)
        payload = {"action": action, "bar_ts": bar_ts, "trigger_price": close_p}
        if blocked_reason:
            payload["blocked"] = True
            payload["reason"] = blocked_reason
            # Also emit dedicated BLOCK event
            evt_blk = {
                "ts": int(time.time() * 1000), "type": "GLOBAL_RISK_BLOCK",
                "strategy_id": strategy_id, "payload": {"decision": "BUY", "reason": blocked_reason, "totals": risk_totals}
            }
            append_runtime_event(home, cloud_run_id, evt_blk)
            
        evt_dec = {
            "ts": int(time.time() * 1000), "type": "STRATEGY_DECISION",
            "strategy_id": strategy_id,
            "payload": payload
        }
        append_runtime_event(home, cloud_run_id, evt_dec)
        
        last_ts = bar_ts
        cursor += 1
        advanced += 1
        
    # 5. Heartbeat & Save
    state["cursor"] = cursor
    state["last_ts"] = last_ts
    save_strategy_state(home, strategy_id, state)
    
    pf_final = load_portfolio(home, strategy_id)
    
    evt_hb = {
        "ts": int(time.time() * 1000), "type": "STRATEGY_HEARTBEAT",
        "strategy_id": strategy_id,
        "payload": {
            "cursor": cursor, 
            "total": len(bars), 
            "last_ts": last_ts,
            "position": pf_final["position_qty"]
        }
    }
    append_runtime_event(home, cloud_run_id, evt_hb)
    
    return {"skipped": False, "advanced": advanced, "cursor": cursor, "total": len(bars)}

def cloud_runtime_tick(home: str, ticks: int = 1, steps_per_strategy: int = 10) -> Dict[str, Any]:
    from tezaver.matrix.core.global_risk import load_global_risk, compute_totals
    from tezaver.matrix.core.broker_config import load_broker_config
    
    state = start_or_load_runtime_state(home)
    crid = state["cloud_run_id"]
    
    active_strats = list_active_strategies(home)
    
    strategy_results = {}
    events_written = 0  # MX-9330: Track events written
    broker_cfg = {"mode": "PAPER"}  # MX-9330: Initialize to avoid UnboundLocalError
    risk_cfg = {"paused": False}  # MX-9330: Initialize to avoid UnboundLocalError
    
    for t in range(ticks):
        tick_ts = int(time.time() * 1000)
        
        # 1. Global Risk Check (Kill Switch)
        risk_cfg = load_global_risk(home)
        if risk_cfg["paused"]:
            append_runtime_event(home, crid, {"ts": tick_ts, "type": "GLOBAL_PAUSED", "tick_seq": state["total_ticks"] + 1})
            # Heartbeat for paused state
            hb = {
                "ts": tick_ts,
                "type": "RUNTIME_HEARTBEAT_PAUSED",
                "active_count": len(active_strats),
                "strategies": active_strats,
                "paused": True
            }
            # Skip strategies
            continue
            
        # 2. Secrets Health
        from tezaver.matrix.core.secrets import load_binance_secrets, redact_secrets
        secrets = load_binance_secrets(home)
        append_runtime_event(home, crid, {
            "ts": tick_ts, "type": "SECRETS_HEALTH",
            "payload": redact_secrets(secrets)
        })

        # 3. Broker Config Check
        broker_cfg = load_broker_config(home)
        append_runtime_event(home, crid, {
            "ts": tick_ts, "type": "BROKER_MODE", 
            "payload": {"mode": broker_cfg["mode"], "exchange": broker_cfg.get("exchange")}
        })
            

        # 4. Compute Totals
        risk_totals = compute_totals(home, active_strats)
        append_runtime_event(home, crid, {
            "ts": tick_ts, "type": "GLOBAL_RISK_SNAPSHOT", 
            "payload": {"totals": risk_totals, "limits": risk_cfg}
        })
        
        # --- MATRIX COURT STEP (The Bridge) ---
        # Run the Pool Court System (Defender/Prosecutor/Judge)
        pool_res = pool_step(home, crid, "WAR", risk_cfg, broker_cfg)
        # --------------------------------------
        
        # General Tick Event
        append_runtime_event(home, crid, {"ts": tick_ts, "type": "CLOUD_TICK", "tick_seq": state["total_ticks"] + 1, "strategy_id": active_strats[0] if active_strats else None})
        events_written += 1  # MX-9330: Count CLOUD_TICK event
        
        # Process Strategies
        for sid in active_strats:
            # Load Strategy JSON
            s_path = os.path.join(home, "cloud_registry", "strategies", sid, "strategy.json")
            if not os.path.exists(s_path):
                 # Can't run without def
                 continue
                 
            with open(s_path) as f: s_json = json.load(f)
            
            res = strategy_step(
                home, crid, sid, s_json, steps_per_strategy, 
                risk_config=risk_cfg, risk_totals=risk_totals, broker_config=broker_cfg
            )
            strategy_results[sid] = res
            
        # Runtime Heartbeat
        hb = {
            "ts": tick_ts,
            "type": "RUNTIME_HEARTBEAT",
            "active_count": len(active_strats),
            "strategies": active_strats
        }
        append_runtime_event(home, crid, hb)
        
        # Update State
        state["last_tick_ts"] = int(time.time())
        state["total_ticks"] += 1
        
    # Save State
    with open(os.path.join(home, "cloud_runtime", "state.json"), "w") as f:
        json.dump(state, f, indent=2)
        
    # Save Heartbeat snapshot
    with open(os.path.join(home, "cloud_runtime", "runs", crid, "heartbeat.json"), "w") as f:
        json.dump(hb, f, indent=2)
        
    return {
        "cloud_run_id": crid,
        "ticks_processed": ticks,
        "active_strategies": len(active_strats),
        "events_written": events_written,  # MX-9330: Add missing key
        "state": state,
        "latest_strategy_results": strategy_results,
        "risk_paused": risk_cfg.get("paused", False),
        "broker_mode": broker_cfg.get("mode", "PAPER")
    }
