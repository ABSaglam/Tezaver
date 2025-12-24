from typing import List, Dict, Any

class GameChartMarksV1:
    @staticmethod
    def generate_marks(trades: List[Any], steps: List[Any]) -> List[Dict[str, Any]]:
        marks = []
        
        # Trade Marks
        for t in trades:
            # Entry
            marks.append({
                "ts": t.entry_ts,
                "bar_index": t.ref_step_entry,
                "type": "BUY",
                "price": t.entry_price,
                "ref_id": t.trade_id,
                "color": "green",
                "symbol": "triangle-up"
            })
            # Exit
            if t.exit_ts:
                # Type determination (TP vs SL vs SIGNAL) - simplified
                m_type = "EXIT" 
                color = "red" if t.pnl_net < 0 else "blue"
                
                marks.append({
                    "ts": t.exit_ts,
                    "bar_index": t.ref_step_exit,
                    "type": m_type,
                    "price": t.exit_price,
                    "ref_id": t.trade_id,
                    "color": color,
                    "symbol": "triangle-down"
                })
                
        # Block Marks (from steps)
        for s in steps:
            if s.verdict == "BLOCK":
                marks.append({
                    "ts": s.ts,
                    "bar_index": s.bar_index,
                    "type": "BLOCK",
                    "price": s.high, # Mark above bar
                    "ref_id": f"step_{s.bar_index}",
                    "color": "gray",
                    "symbol": "x"
                })
                
        return marks
