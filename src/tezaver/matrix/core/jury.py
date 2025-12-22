import os
import json
from typing import Dict
from collections import Counter

def compute_scorecard(home: str, run_id: str) -> Dict:
    """
    MXI-1130: Computes real financial metrics from run events.
    """
    events_path = os.path.join(home, "runs", run_id, "events.ndjson")
    if not os.path.exists(events_path):
        return {} 
        
    event_counts = Counter()
    bars_count = 0
    blocks_count = 0
    trades = []
    
    # Financial metrics
    total_pnl = 0.0
    fee_cost = 0.0
    slippage_cost = 0.0
    trade_audit = [] # MXI-1401
    
    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
                etype = ev.get("event_type", "UNKNOWN")
                event_counts[etype] += 1
                
                if etype == "CYCLE_STEP":
                    bars_count += 1
                    payload = ev.get("payload", {})
                    
                    if payload.get("blocked"):
                        blocks_count += 1
                    
                    # Track trades (MXI-1130, MXI-1401)
                    order = payload.get("order")
                    if order and order.get("status") == "FILLED":
                        trades.append(order)
                        
                        f_price = order.get("fill_price", 0)
                        l_price = order.get("limit_price", 0)
                        qty = order.get("qty", 1.0)
                        fee = order.get("fee_cost", 0)
                        
                        slip = abs(f_price - l_price) * abs(qty) if l_price > 0 else 0
                        
                        fee_cost += fee
                        slippage_cost += slip
                        
                        # Audit Entry (MX-5120 / V2)
                        audit_entry = {
                            "ts": ev.get("ts"),
                            "symbol": order.get("symbol"),
                            "side": order.get("side"),
                            "qty": qty,
                            "entry_price": l_price,
                            "exit_price": f_price,
                            "fee": fee,
                            "slippage": slip,
                            "net_pnl": 0.0,
                            "exit_reason": "FILLED"
                        }
                        trade_audit.append(audit_entry)
                
                # MX-9360: Also count BAR events for bars_count
                if etype == "BAR":
                    bars_count += 1
                
                # MX-9360: Count DECISION and BLOCK events for legacy scorecard
                if etype == "DECISION":
                    event_counts["decisions"] = event_counts.get("decisions", 0) + 1
                if etype == "BLOCK":
                    blocks_count += 1

            except:
                continue

    # PnL Calculation
    # MX-5120: total_pnl_raw should be sum of net_pnl, not notional.
    total_pnl_raw = sum([t.get('net_pnl', 0) for t in trade_audit])
    total_trades = len(trades)
    
    return {
        "run_id": run_id,
        "bars_count": bars_count,
        "blocks_count": blocks_count,
        "decisions_count": event_counts.get("decisions", 0),  # MX-9360
        "incidents_count": 0,  # MX-9360: No incidents tracking yet
        "trades_count": total_trades,
        "total_pnl_raw": total_pnl_raw, 
        "fee_cost": fee_cost,
        "slippage_cost": slippage_cost,
        "trade_audit_v2": trade_audit,
        "win_rate": 0.0,
        "event_types": dict(event_counts)
    }
