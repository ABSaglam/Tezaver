# Matrix Operator Console v1
"""
Combined CLI view of Strategy Board and Live Autowire.

Provides a single entry point to view all Matrix profiles and Live cluster status.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any

from tezaver.matrix.profile_board import build_profile_board, ProfileBoardRow
from tezaver.matrix.live.live_cluster import build_live_cluster_from_profile_board


@dataclass
class OperatorSummary:
    """Summary statistics for the operator console."""
    total_profiles: int
    live_eligible_count: int


@dataclass
class LiveCellInfo:
    """Info about a single live cell."""
    symbol: str
    timeframe: str
    profile_id: str
    max_risk_per_trade: Optional[float]


def build_operator_console_snapshot(
    initial_capital: float = 100.0,
    risk_mode: str = "contract",
) -> Dict[str, Any]:
    """
    Build snapshot of Strategy Board and Live Cluster.
    
    Args:
        initial_capital: Starting capital for live cluster.
        risk_mode: "contract" or "experiment".
    
    Returns:
        Dict with board_rows, summary, live_cells, and config info.
    """
    # Build strategy board
    board_rows = build_profile_board()
    
    # Calculate summary
    total = len(board_rows)
    live_count = sum(1 for r in board_rows if r.live_eligible)
    summary = OperatorSummary(total_profiles=total, live_eligible_count=live_count)
    
    # Build live cluster
    cluster = build_live_cluster_from_profile_board(
        initial_capital=initial_capital,
        risk_mode=risk_mode,
    )
    
    # Extract live cell info
    live_cells: List[LiveCellInfo] = []
    for cell in cluster.list_cells():
        # Get max_risk from the corresponding board row
        max_risk: Optional[float] = None
        for row in board_rows:
            if (row.symbol == cell.symbol and 
                row.timeframe == cell.timeframe and
                row.profile_id == cell.profile_id):
                max_risk = row.max_risk_per_trade
                break
        
        live_cells.append(LiveCellInfo(
            symbol=cell.symbol,
            timeframe=cell.timeframe,
            profile_id=cell.profile_id,
            max_risk_per_trade=max_risk,
        ))
    
    return {
        "board_rows": board_rows,
        "summary": summary,
        "live_cells": live_cells,
        "initial_capital": initial_capital,
        "risk_mode": risk_mode,
    }


def print_operator_console(snapshot: Dict[str, Any]) -> None:
    """
    Print operator console to stdout.
    
    Args:
        snapshot: Dict from build_operator_console_snapshot.
    """
    board_rows: List[ProfileBoardRow] = snapshot["board_rows"]
    summary: OperatorSummary = snapshot["summary"]
    live_cells: List[LiveCellInfo] = snapshot["live_cells"]
    initial_capital: float = snapshot["initial_capital"]
    risk_mode: str = snapshot["risk_mode"]
    
    # Header
    print("=" * 100)
    print("Matrix Operator Console v1 – Strategy Board & Live Autowire")
    print("=" * 100)
    
    # Strategy Board table header
    header = f"{'Symbol':10} {'TF':6} {'Profile':28} {'Status':12} {'PnL%':8} {'Trades':8} {'MaxRisk':8} {'LIVE?':6}"
    print(header)
    print("-" * 100)
    
    # Strategy Board rows
    for r in board_rows:
        pnl_str = f"{r.pnl_pct:.2f}%" if r.pnl_pct is not None else "-"
        trades_str = str(r.trades) if r.trades is not None else "-"
        risk_str = f"{r.max_risk_per_trade * 100:.2f}%" if r.max_risk_per_trade is not None else "-"
        live_str = "YES" if r.live_eligible else "NO"
        
        profile_display = r.profile_id[:27] if len(r.profile_id) > 27 else r.profile_id
        
        line = f"{r.symbol:10} {r.timeframe:6} {profile_display:28} {r.status:12} {pnl_str:8} {trades_str:8} {risk_str:8} {live_str:6}"
        print(line)
    
    print("-" * 100)
    print(f"Total profiles: {summary.total_profiles} | Live eligible: {summary.live_eligible_count}")
    print()
    
    # Live Cluster section
    print(f"Live Cluster (initial_capital={initial_capital}, mode={risk_mode})")
    
    if not live_cells:
        print("  (no LIVE eligible profiles)")
    else:
        for cell in live_cells:
            risk_pct = f"{cell.max_risk_per_trade * 100:.2f}%" if cell.max_risk_per_trade else "-"
            print(f"  ✓ {cell.symbol} {cell.timeframe} {cell.profile_id} (max_risk={risk_pct})")


def main(argv: List[str] | None = None) -> None:
    """
    CLI entry point.
    
    Args:
        argv: Optional list of arguments [initial_capital, risk_mode].
    """
    initial_capital = 100.0
    risk_mode = "contract"
    
    if argv:
        # Parse initial_capital
        if len(argv) >= 1:
            try:
                initial_capital = float(argv[0])
            except ValueError:
                pass
        
        # Parse risk_mode
        if len(argv) >= 2 and argv[1] in ("contract", "experiment"):
            risk_mode = argv[1]
    
    snapshot = build_operator_console_snapshot(
        initial_capital=initial_capital,
        risk_mode=risk_mode,
    )
    print_operator_console(snapshot)


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
