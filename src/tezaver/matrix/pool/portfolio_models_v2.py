"""
Portfolio Models V2
===================

Enhanced portfolio models with PnL, fees, exposure tracking.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class PortfolioPositionV2:
    """Enhanced position with PnL tracking."""
    pos_id: str
    symbol: str
    timeframe: Optional[str]
    bundle_id: Optional[str]
    status: str  # "OPEN"|"CLOSED"
    opened_ts_iso: str
    closed_ts_iso: Optional[str]
    
    avg_entry: float
    qty: float
    notional_entry: float
    
    fees_paid: float
    slippage_paid: float
    
    realized_pnl: float
    unrealized_pnl: float
    
    last_mark_price: float
    last_mark_ts_iso: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pos_id": self.pos_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "bundle_id": self.bundle_id,
            "status": self.status,
            "opened_ts_iso": self.opened_ts_iso,
            "closed_ts_iso": self.closed_ts_iso,
            "avg_entry": self.avg_entry,
            "qty": self.qty,
            "notional_entry": self.notional_entry,
            "fees_paid": self.fees_paid,
            "slippage_paid": self.slippage_paid,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "last_mark_price": self.last_mark_price,
            "last_mark_ts_iso": self.last_mark_ts_iso
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioPositionV2":
        return cls(
            pos_id=d.get("pos_id", ""),
            symbol=d.get("symbol", ""),
            timeframe=d.get("timeframe"),
            bundle_id=d.get("bundle_id"),
            status=d.get("status", "OPEN"),
            opened_ts_iso=d.get("opened_ts_iso", now_iso()),
            closed_ts_iso=d.get("closed_ts_iso"),
            avg_entry=d.get("avg_entry", 0.0),
            qty=d.get("qty", 0.0),
            notional_entry=d.get("notional_entry", 0.0),
            fees_paid=d.get("fees_paid", 0.0),
            slippage_paid=d.get("slippage_paid", 0.0),
            realized_pnl=d.get("realized_pnl", 0.0),
            unrealized_pnl=d.get("unrealized_pnl", 0.0),
            last_mark_price=d.get("last_mark_price", 0.0),
            last_mark_ts_iso=d.get("last_mark_ts_iso", now_iso())
        )

@dataclass
class PortfolioTotalsV2:
    """Aggregated totals."""
    open_positions: int
    notional_open: float
    fees_paid: float
    slippage_paid: float
    realized_pnl: float
    unrealized_pnl: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "open_positions": self.open_positions,
            "notional_open": self.notional_open,
            "fees_paid": self.fees_paid,
            "slippage_paid": self.slippage_paid,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl
        }

@dataclass
class PortfolioStateV2:
    """Full portfolio state v2."""
    version: str
    updated_ts_iso: str
    positions: List[PortfolioPositionV2]
    totals: PortfolioTotalsV2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "updated_ts_iso": self.updated_ts_iso,
            "positions": [p.to_dict() for p in self.positions],
            "totals": self.totals.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioStateV2":
        positions = [PortfolioPositionV2.from_dict(p) for p in d.get("positions", [])]
        totals_d = d.get("totals", {})
        totals = PortfolioTotalsV2(
            open_positions=totals_d.get("open_positions", 0),
            notional_open=totals_d.get("notional_open", 0.0),
            fees_paid=totals_d.get("fees_paid", 0.0),
            slippage_paid=totals_d.get("slippage_paid", 0.0),
            realized_pnl=totals_d.get("realized_pnl", 0.0),
            unrealized_pnl=totals_d.get("unrealized_pnl", 0.0)
        )
        return cls(
            version=d.get("version", "portfolio_state_sim_v2"),
            updated_ts_iso=d.get("updated_ts_iso", now_iso()),
            positions=positions,
            totals=totals
        )

def compute_totals(positions: List[PortfolioPositionV2]) -> PortfolioTotalsV2:
    """Compute totals from positions."""
    open_pos = [p for p in positions if p.status == "OPEN"]
    return PortfolioTotalsV2(
        open_positions=len(open_pos),
        notional_open=sum(p.notional_entry for p in open_pos),
        fees_paid=sum(p.fees_paid for p in positions),
        slippage_paid=sum(p.slippage_paid for p in positions),
        realized_pnl=sum(p.realized_pnl for p in positions),
        unrealized_pnl=sum(p.unrealized_pnl for p in open_pos)
    )

def empty_state_v2() -> PortfolioStateV2:
    """Create empty state v2."""
    return PortfolioStateV2(
        version="portfolio_state_sim_v2",
        updated_ts_iso=now_iso(),
        positions=[],
        totals=PortfolioTotalsV2(0, 0.0, 0.0, 0.0, 0.0, 0.0)
    )
