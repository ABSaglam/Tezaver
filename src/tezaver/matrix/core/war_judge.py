"""
MX-2022: WarJudge - Gate/verdict logic for WAR runs.
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class WarGates:
    """Gate thresholds for WAR verdict."""
    min_total_trades: int = 10
    max_drawdown_pct: float = 20.0  # 20%
    min_profitable_pnl: float = 0.0  # Optional: require positive PnL


class WarJudge:
    """
    MX-2022: WarJudge
    Evaluates WAR scorecard against gates and produces verdict.
    """
    
    def __init__(self, gates: WarGates = None):
        self.gates = gates or WarGates()
    
    def evaluate(self, scorecard: Dict) -> Tuple[str, List[Dict]]:
        """
        Evaluate scorecard against gates.
        Returns: (verdict, reasons)
        verdict: "PASS" | "IMPROVE" | "FAIL"
        """
        reasons = []
        
        total_trades = scorecard.get("total_trades", 0)
        max_drawdown = scorecard.get("max_drawdown", 0)
        net_pnl = scorecard.get("net_pnl", 0)
        risk_blocks = scorecard.get("risk_blocks_count", 0)
        
        # Gate 1: Minimum trades
        if total_trades < self.gates.min_total_trades:
            reasons.append({
                "gate": "MIN_TOTAL_TRADES",
                "threshold": self.gates.min_total_trades,
                "actual": total_trades,
                "severity": "FAIL"
            })
        
        # Gate 2: Max drawdown
        if max_drawdown > self.gates.max_drawdown_pct:
            reasons.append({
                "gate": "MAX_DRAWDOWN_PCT",
                "threshold": self.gates.max_drawdown_pct,
                "actual": max_drawdown,
                "severity": "FAIL"
            })
        
        # Gate 3: Profitability (optional)
        if net_pnl < self.gates.min_profitable_pnl:
            reasons.append({
                "gate": "MIN_PROFITABLE_PNL",
                "threshold": self.gates.min_profitable_pnl,
                "actual": net_pnl,
                "severity": "IMPROVE"
            })
        
        # Gate 4: Risk blocks warning
        if risk_blocks > 0:
            reasons.append({
                "gate": "RISK_BLOCKS",
                "threshold": 0,
                "actual": risk_blocks,
                "severity": "WARN"
            })
        
        # Determine verdict
        fail_count = len([r for r in reasons if r["severity"] == "FAIL"])
        improve_count = len([r for r in reasons if r["severity"] == "IMPROVE"])
        
        if fail_count > 0:
            verdict = "FAIL"
        elif improve_count > 0:
            verdict = "IMPROVE"
        else:
            verdict = "PASS"
        
        return verdict, reasons
    
    def generate_report(self, scorecard: Dict) -> Dict:
        """Generate full verdict report."""
        verdict, reasons = self.evaluate(scorecard)
        
        return {
            "verdict": verdict,
            "gates": {
                "min_total_trades": self.gates.min_total_trades,
                "max_drawdown_pct": self.gates.max_drawdown_pct,
                "min_profitable_pnl": self.gates.min_profitable_pnl
            },
            "reasons": reasons,
            "scorecard_hash": scorecard.get("scorecard_hash", "N/A")
        }
