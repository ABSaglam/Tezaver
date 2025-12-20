import os
import json
import time
from typing import Dict, Any, List
from tezaver.matrix.core.cloud_runtime import list_active_strategies, append_runtime_event
from tezaver.matrix.core.paper_broker import load_portfolio, save_portfolio

def reconcile_stream(home: str) -> Dict[str, Any]:
    """
    Parses raw user stream events and reconciles local state.
    """
    stream_dir = os.path.join(home, "cloud_runtime", "userstream")
    raw_file = os.path.join(stream_dir, "raw.ndjson")
    checkpoint_file = os.path.join(stream_dir, "checkpoint.json")
    
    if not os.path.exists(raw_file):
        return {"processed": 0, "status": "NO_FILE"}

    # Load Checkpoint
    checkpoint = {"last_line": 0}
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file) as f: checkpoint = json.load(f)
        except: pass
        
    start_line = checkpoint["last_line"]
    current_line = 0
    updates_count = 0
    
    # Pre-load strategies map (clientOrderId prefix -> strategy_id)
    # Our format: "mx_<strategy_id>_..."
    # We don't strictly need a map if we parse the ID.
    
    events_to_emit = [] # (run_id, event) tuples if we had run_id linkage.
    # Currently cloud_runtime events are per run_id.
    # We might not know valid run_id easily without loading state.
    # For now, we update PERSISTENT STATE (portfolio.json, orders.ndjson).
    
    with open(raw_file, "r") as f:
        for i, line in enumerate(f):
            if i < start_line:
                current_line += 1
                continue
                
            try:
                msg = json.loads(line)
                etype = msg.get("e")
                
                if etype == "ORDER_TRADE_UPDATE":
                    _process_order_update(home, msg)
                    updates_count += 1
                elif etype == "ACCOUNT_UPDATE":
                    _process_account_update(home, msg)
                    updates_count += 1
                    
            except Exception as e:
                # Log error?
                pass
            
            current_line += 1
            
    # Save Checkpoint
    with open(checkpoint_file, "w") as f:
        json.dump({"last_line": current_line, "ts": int(time.time()*1000)}, f)
        
    return {"processed": current_line - start_line, "updates": updates_count}

def _process_order_update(home: str, msg: Dict):
    data = msg.get("o", {})
    cid = data.get("c", "") # clientOrderId
    
    # Check if ours: mx_<sid>_<ts>_<uuid>
    if not cid.startswith("mx_"):
        return
        
    parts = cid.split("_")
    if len(parts) < 2: return
    
    sid = parts[1] # Strategy ID
    
    # Use Lifecycle Tracker
    from tezaver.matrix.core.exchange_lifecycle import ExchangeOrderLifecycleTracker
    tracker = ExchangeOrderLifecycleTracker(home, sid)
    
    # Tracker handles delta calculation and idempotency
    # data is the "o" payload
    delta_qty = tracker.update_order(data)
    
    status = data.get("X")
    side = data.get("S")
    filled_qty = float(data.get("z", 0)) # Cumulative
    last_price = float(data.get("L", 0))
    
    # 1. Update Portfolio (Incremental)
    if delta_qty > 0:
        pf = load_portfolio(home, sid)
        curr_pos = pf.get("inventory", {}).get(data.get("s"), 0.0)
        
        if side == "BUY":
            curr_pos += delta_qty
        else:
            curr_pos -= delta_qty
            
        if "inventory" not in pf: pf["inventory"] = {}
        pf["inventory"][data.get("s")] = curr_pos
        
        save_portfolio(home, sid, pf)

    # 2. Append Event to Strategy Order Log
    # Only if there was an update worth logging?
    # Or every time? EXECUTION_REPORT comes for status changes too.
    # We log all relevant events.
    
    order_evt = {
        "ts": msg.get("E"),
        "type": "EXCHANGE_ORDER_UPDATE",
        "payload": {
            "symbol": data.get("s"),
            "side": side,
            "status": status,
            "filled": filled_qty,
            "price": last_price,
            "cid": cid,
            "delta_fill": delta_qty
        }
    }
    
    s_dir = os.path.join(home, "cloud_runtime", "strategies", sid)
    if os.path.exists(s_dir):
        with open(os.path.join(s_dir, "orders.ndjson"), "a") as f:
            f.write(json.dumps(order_evt) + "\n")

def _process_account_update(home: str, msg: Dict):
    data = msg.get("a", {})
    positions = data.get("P", [])
    
    dump_path = os.path.join(home, "cloud_runtime", "userstream", "exchange_position_snapshot.json")
    with open(dump_path, "w") as f:
        json.dump(positions, f, indent=2)
        
    # Drift Check (Simplified)
    # We check if any position differs significantly from a loaded strategy portfolio.
    # But connecting symbols to strategies is hard without mapping.
    # Helper: Check well-known strategy?
    # For Phase-14C.3, we'll implement a basic check if we can resolve strategy.
    # Let's iterate active strategies and check their symbol.
    
    active_sids = list_active_strategies(home)
    for sid in active_sids:
        # Load Strategy Config to get Symbol
        # We assume standard path
        try:
             s_cfg_path = os.path.join(home, "cloud_runtime", "strategies", sid, "strategy.json")
             with open(s_cfg_path) as f: cfg = json.load(f)
             sym = cfg.get("symbol")
             
             # Find in exchange positions (snapshot)
             ex_qty = 0.0
             for p in positions:
                 if p.get("s") == sym:
                     ex_qty = float(p.get("pa", 0)) # Position Amount
                     break
                     
             # Load Local
             pf = load_portfolio(home, sid)
             loc_qty = pf.get("inventory", {}).get(sym, 0.0)
             
             if abs(ex_qty - loc_qty) > 0.0001:
                 # DRIFT!
                 evt = {
                     "ts": int(time.time()*1000), "type": "POSITION_DRIFT_DETECTED",
                     "strategy_id": sid,
                     "payload": {"symbol": sym, "local": loc_qty, "exchange": ex_qty}
                 }
                 # Warn Runtime? We need to write to runtime events.
                 # Where is runtime events? Runs/...
                 # UserStream Reconciler works on global userstream raw events, but needs to alert Runtime.
                 # We don't have active run_id here easily without loading state.
                 # We'll just print/log for now, or assume single active run?
                 # Better: append to Strategy-specific log or a global Alerts queue (impl in Phase-13C Alert Engine scans events).
                 # Alert Engine scans cloud_runtime/runs/...
                 # So we need to find current run.
                 from tezaver.matrix.core.cloud_runtime import start_or_load_runtime_state
                 st = start_or_load_runtime_state(home)
                 crid = st.get("cloud_run_id")
                 if crid:
                     append_runtime_event(home, crid, evt)
        except: pass
