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
                    
                    # Track trades (MXI-1130)
                    order = payload.get("order")
                    if order and order.get("status") == "FILLED":
                        trades.append(order)
                        fee_cost += order.get("fee_cost", 0)
                        # Slippage cost calculation relative to limit_price
                        limit = order.get("limit_price", 0)
                        fill = order.get("fill_price", 0)
                        qty = order.get("qty", 1.0)
                        if limit > 0:
                            slippage_cost += abs(fill - limit) * abs(qty)

            except:
                continue

    # PnL Calculation (Simplified for this sprint: entries only, assume close at last bar)
    # In next iterations, we will handle full trade lifecycles.
    win_count = 0
    total_trades = len(trades)
    
    # Placeholder for drawdown calculation if we had time series of equity
    # For now, we'll return the collected aggregates.
    
    return {
        "run_id": run_id,
        "bars_count": bars_count,
        "blocks_count": blocks_count,
        "trades_count": total_trades,
        "total_pnl_raw": sum([t.get('qty',0)*t.get('fill_price',0) for t in trades]), # Just sum for now
        "fee_cost": fee_cost,
        "slippage_cost": slippage_cost,
        "win_rate": 0.0, # Need exits for real win rate
        "event_types": dict(event_counts)
    }
