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
    
    # Extract Order Info
    # s: symbol, S: side, q: original qty, z: filled qty, L: last filled price, X: status
    # X: NEW, PARTIALLY_FILLED, FILLED, CANCELED, REJECTED, EXPIRED
    status = data.get("X")
    filled_qty = float(data.get("z", 0))
    last_price = float(data.get("L", 0))
    side = data.get("S")
    
    # 1. Update Portfolio (Best Effort)
    # If FILLED or PARTIALLY_FILLED, and "z" increased? 
    # "z" is cumulative filled quantity.
    # We need delta to update portfolio correctly if using incremental logic.
    # Paper Broker `load_portfolio` reads `portfolio.json`.
    # `portfolio.json` has `open_positions`, `pnl`, etc.
    # This acts as a "source of truth update".
    # But wait, `portfolio.json` is usually derived or simplistic in Paper. 
    # In REAL mode, we should ideally REPLACE portfolio with Account Update snapshot.
    # But ORDER_UPDATE gives us fast fills.
    
    # For Phase-14C.2, let's just emit proper EXCHANGE_ORDER_UPDATE event to `orders.ndjson`
    # and maybe update a simplified "real_positions.json" if we wanted strict separation.
    # The requirement says: "local portfolio.json güncelle (qty/avg_price best-effort)".
    
    if status in ["FILLED", "PARTIALLY_FILLED"]:
        # We need to know if this fill was already processed?
        # Reconciler runs sequentially. Checkpoint handles "processed up to line N".
        # So we process each message ONCE.
        # However, "z" is cumulative. We need "l" (last filled quantity of the trade)?
        # msg["o"]["l"] is "Order Last Filled Quantity". This is the delta!
        last_fill_qty = float(data.get("l", 0))
        
        if last_fill_qty > 0:
            pf = load_portfolio(home, sid)
            # Update PF logic
            # If BUY -> positions += qty, cost basis update?
            # If SELL -> positions -= qty
            
            # Simple assumption for Matrix v4 (Long Only default? Or Net?)
            # Assuming simplified "Net Position" tracking in `portfolio.json`.
            
            curr_pos = pf.get("inventory", {}).get(data.get("s"), 0.0)
            
            if side == "BUY":
                curr_pos += last_fill_qty
            else:
                curr_pos -= last_fill_qty
                
            if "inventory" not in pf: pf["inventory"] = {}
            pf["inventory"][data.get("s")] = curr_pos
            
            save_portfolio(home, sid, pf)

    # 2. Append Event to Strategy Order Log
    # orders_path = .../strategies/<sid>/orders.ndjson
    # We should append a normalized event.
    order_evt = {
        "ts": msg.get("E"),
        "type": "EXCHANGE_ORDER_UPDATE",
        "payload": {
            "symbol": data.get("s"),
            "side": side,
            "status": status,
            "filled": filled_qty,
            "price": last_price,
            "cid": cid
        }
    }
    
    s_dir = os.path.join(home, "cloud_runtime", "strategies", sid)
    if os.path.exists(s_dir):
        with open(os.path.join(s_dir, "orders.ndjson"), "a") as f:
            f.write(json.dumps(order_evt) + "\n")

def _process_account_update(home: str, msg: Dict):
    # msg["a"]["B"] -> Balances
    # msg["a"]["P"] -> Positions
    # For Phase-14C.2, we just verify it exists and maybe dump it.
    # Requirement: "positions içinde ilgili symbol varsa authoritative snapshot gibi sakla"
    
    data = msg.get("a", {})
    positions = data.get("P", [])
    
    # We don't know Strategy ID easily from Account Update (it's global for account).
    # But we map by Symbol -> Strategy?
    # Matrix maps Strategy -> Symbol.
    # We can iterate active strategies and match symbol.
    
    active_strats = list_active_strategies(home) # returns list of sids
    # Load each strat config to find symbol? Expensive.
    # For this phase, let's just dump the global position snapshot.
    
    dump_path = os.path.join(home, "cloud_runtime", "userstream", "exchange_position_snapshot.json")
    with open(dump_path, "w") as f:
        json.dump(positions, f, indent=2)
