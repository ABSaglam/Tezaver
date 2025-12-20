import os
import json
import time
import uuid
from typing import Dict, Any, Tuple

def get_portfolio_path(home: str, strategy_id: str) -> str:
    return os.path.join(home, "cloud_runtime", "strategies", strategy_id, "portfolio.json")

def get_orders_path(home: str, strategy_id: str) -> str:
    return os.path.join(home, "cloud_runtime", "strategies", strategy_id, "orders.ndjson")

def load_portfolio(home: str, strategy_id: str) -> Dict[str, Any]:
    path = get_portfolio_path(home, strategy_id)
    if os.path.exists(path):
        with open(path) as f: return json.load(f)
    # Default State
    return {
        "position_qty": 0.0,
        "avg_price": 0.0,
        "last_fill_ts": 0,
        "last_updated_ts": int(time.time() * 1000)
    }

def save_portfolio(home: str, strategy_id: str, portfolio: Dict[str, Any]) -> None:
    path = get_portfolio_path(home, strategy_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(portfolio, f, indent=2)

def append_order_event(home: str, strategy_id: str, event_type: str, payload: Dict[str, Any]) -> None:
    path = get_orders_path(home, strategy_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    evt = {
        "ts": int(time.time() * 1000),
        "type": event_type,
        "strategy_id": strategy_id,
        "payload": payload
    }
    with open(path, "a") as f:
        f.write(json.dumps(evt) + "\n")

def execute_paper_order(home: str, strategy_id: str, side: str, qty: float, price: float, ts: int) -> Dict[str, Any]:
    # 1. Generate Order ID
    order_id = f"PORD_{strategy_id}_{ts}_{uuid.uuid4().hex[:6]}"
    
    # 2. Log ORDER_NEW
    append_order_event(home, strategy_id, "ORDER_NEW", {
        "order_id": order_id,
        "side": side,
        "qty": qty,
        "price": price, # limit price or trigger price
        "ts": ts
    })
    
    # 3. Simulate Fill (Instant)
    # Paper broker assumes guaranteed fill at 'price' (usually close price)
    fill_id = f"FILL_{uuid.uuid4().hex[:8]}"
    append_order_event(home, strategy_id, "ORDER_FILLED", {
        "order_id": order_id,
        "fill_id": fill_id,
        "side": side,
        "fill_qty": qty,
        "fill_price": price,
        "ts": ts
    })
    
    # 4. Update Portfolio
    pf = load_portfolio(home, strategy_id)
    curr_qty = pf["position_qty"]
    curr_avg = pf["avg_price"]
    
    # Simple FIFO/Weighted Avg logic? 
    # For now, simplistic:
    # If side matches current sign or current is 0 -> Weighted Avg
    # If side opposes -> Reduce quantity (realize pnl - not tracked here yet)
    
    new_qty = curr_qty
    if side == "BUY":
        # Adding to position
        if curr_qty >= 0:
            total_val = (curr_qty * curr_avg) + (qty * price)
            new_qty = curr_qty + qty
            if new_qty > 0:
                pf["avg_price"] = total_val / new_qty
            else:
                 pf["avg_price"] = 0
        else:
            # Closing SHORT
            new_qty = curr_qty + qty # e.g. -1 + 1 = 0
            # Avg price doesn't change on reduction usually, PnL is realized
            if new_qty == 0: pf["avg_price"] = 0
            
    elif side == "SELL":
         if curr_qty <= 0:
             # Adding to SHORT
             total_val = (abs(curr_qty) * curr_avg) + (qty * price)
             new_qty = curr_qty - qty
             if abs(new_qty) > 0:
                 pf["avg_price"] = total_val / abs(new_qty)
         else:
             # Closing LONG
             new_qty = curr_qty - qty
             if new_qty == 0: pf["avg_price"] = 0
             
    pf["position_qty"] = new_qty
    pf["last_fill_ts"] = ts
    pf["last_updated_ts"] = int(time.time() * 1000)
    
    save_portfolio(home, strategy_id, pf)
    
    # 5. Log POSITION_UPDATE
    append_order_event(home, strategy_id, "POSITION_UPDATE", pf)
    
    return {
        "order_id": order_id,
        "status": "FILLED",
        "fill_price": price,
        "fill_qty": qty,
        "new_position": new_qty
    }
