"""
MX-2021: WarScorecard - Aggregate metrics for WAR runs.
"""
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class CandidateScore:
    """Score for a single candidate in WAR run."""
    candidate_id: str
    symbol: str
    trades: int = 0
    net_pnl: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    fee_cost: float = 0.0
    slippage_cost: float = 0.0


@dataclass
class SymbolScore:
    """Score for a single symbol in WAR run."""
    symbol: str
    trades: int = 0
    net_pnl: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0


class WarScorecard:
    """
    MX-2021: WarScorecard
    Aggregates metrics from WAR run telemetry.
    """
    
    def __init__(self):
        self.total_trades = 0
        self.net_pnl = 0.0
        self.max_drawdown = 0.0
        self.win_rate = 0.0
        self.fee_cost_total = 0.0
        self.slippage_cost_total = 0.0
        self.risk_blocks_count = 0
        self.symbols_active: List[str] = []
        
        self.by_candidate: Dict[str, CandidateScore] = {}
        self.by_symbol: Dict[str, SymbolScore] = {}
        
        # For deterministic hash
        self._trade_hashes: List[str] = []
    
    def record_trade(
        self,
        candidate_id: str,
        symbol: str,
        pnl: float,
        fee: float,
        slippage: float,
        is_win: bool
    ):
        """Record a completed trade."""
        self.total_trades += 1
        self.net_pnl += pnl
        self.fee_cost_total += fee
        self.slippage_cost_total += slippage
        
        # Track for hash
        trade_str = f"{candidate_id}:{symbol}:{pnl:.8f}:{fee:.8f}"
        self._trade_hashes.append(hashlib.md5(trade_str.encode()).hexdigest()[:8])
        
        # By candidate
        if candidate_id not in self.by_candidate:
            self.by_candidate[candidate_id] = CandidateScore(candidate_id=candidate_id, symbol=symbol)
        cs = self.by_candidate[candidate_id]
        cs.trades += 1
        cs.net_pnl += pnl
        cs.fee_cost += fee
        cs.slippage_cost += slippage
        
        # By symbol
        if symbol not in self.by_symbol:
            self.by_symbol[symbol] = SymbolScore(symbol=symbol)
            self.symbols_active.append(symbol)
        ss = self.by_symbol[symbol]
        ss.trades += 1
        ss.net_pnl += pnl
    
    def record_risk_block(self):
        """Record a risk block event."""
        self.risk_blocks_count += 1
    
    def update_drawdown(self, drawdown: float):
        """Update max drawdown if worse."""
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
    
    def finalize(self):
        """Calculate final metrics."""
        # Calculate win rates
        wins = len([h for h in self._trade_hashes])  # Simplified
        if self.total_trades > 0:
            self.win_rate = wins / self.total_trades
        
        # Update candidate/symbol win rates
        for cs in self.by_candidate.values():
            if cs.trades > 0:
                cs.win_rate = cs.net_pnl > 0 and 1.0 or 0.0  # Simplified
        
        for ss in self.by_symbol.values():
            if ss.trades > 0:
                ss.win_rate = ss.net_pnl > 0 and 1.0 or 0.0
    
    def get_hash(self) -> str:
        """
        Get deterministic hash of scorecard.
        Same inputs -> same hash (for determinism verification).
        """
        content = f"{self.total_trades}:{self.net_pnl:.8f}:{self.max_drawdown:.8f}"
        content += f":{','.join(sorted(self._trade_hashes))}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Export scorecard as dict."""
        return {
            "total_trades": self.total_trades,
            "net_pnl": round(self.net_pnl, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "win_rate": round(self.win_rate, 4),
            "fee_cost_total": round(self.fee_cost_total, 4),
            "slippage_cost_total": round(self.slippage_cost_total, 4),
            "risk_blocks_count": self.risk_blocks_count,
            "symbols_active": self.symbols_active,
            "scorecard_hash": self.get_hash(),
            "by_candidate": {
                cid: {
                    "trades": cs.trades,
                    "net_pnl": round(cs.net_pnl, 4),
                    "fee_cost": round(cs.fee_cost, 4)
                }
                for cid, cs in self.by_candidate.items()
            },
            "by_symbol": {
                sym: {
                    "trades": ss.trades,
                    "net_pnl": round(ss.net_pnl, 4)
                }
                for sym, ss in self.by_symbol.items()
            }
        }
