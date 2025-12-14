# Matrix Strategy Board v1
"""
Overview table of all CoinPage V2 profiles.

Shows status, benchmark, risk contract, and live eligibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from tezaver.matrix.core.profile import MatrixProfileRepository, MatrixCellProfile


@dataclass
class ProfileBoardRow:
    """Single row in the profile board."""
    symbol: str
    timeframe: str
    profile_id: str
    status: str
    pnl_pct: Optional[float]
    trades: Optional[int]
    max_risk_per_trade: Optional[float]
    live_eligible: bool


def _is_live_eligible(status: str, max_risk_per_trade: Optional[float]) -> bool:
    """
    V1 eligibility rule:
    - APPROVED status + risk_contract with max_risk_per_trade = eligible for LIVE.
    """
    if status.upper() != "APPROVED":
        return False
    if max_risk_per_trade is None:
        return False
    return True


def build_profile_board(root: Optional[Path] = None) -> List[ProfileBoardRow]:
    """
    Scan all CoinPage V2 files and build a profile board.
    
    Args:
        root: Optional path to coin_profiles directory.
              Defaults to data/coin_profiles.
    
    Returns:
        List of ProfileBoardRow, one per profile.
    """
    if root is None:
        # Default root: data/coin_profiles relative to project root
        # Try current working directory first, then fallback to relative path
        cwd_root = Path.cwd() / "data" / "coin_profiles"
        if cwd_root.exists():
            root = cwd_root
        else:
            # Fallback: relative to this file (src/tezaver/matrix -> project root)
            base_dir = Path(__file__).resolve().parents[3]
            root = base_dir / "data" / "coin_profiles"
    
    if not root.exists():
        return []
    
    rows: List[ProfileBoardRow] = []
    
    # Scan symbol directories
    for symbol_dir in sorted(root.iterdir()):
        if not symbol_dir.is_dir():
            continue
        if symbol_dir.name.startswith("."):
            continue
        
        symbol = symbol_dir.name
        repo = MatrixProfileRepository(coin_page_root=root)
        
        # Load profiles for this symbol (skip if no coin page)
        try:
            profiles = repo.load_profiles_for_symbol(symbol)
        except (FileNotFoundError, ValueError):
            # No coin page for this symbol, skip
            continue
        
        if not profiles:
            continue
        
        for profile in profiles:
            # Extract benchmark data
            pnl_pct: Optional[float] = None
            trades: Optional[int] = None
            benchmark = getattr(profile, "benchmark", None)
            if benchmark is not None:
                pnl_pct = getattr(benchmark, "pnl_pct", None)
                trades = getattr(benchmark, "trades", None)
            
            # Extract risk contract data
            max_risk: Optional[float] = None
            risk_contract = getattr(profile, "risk_contract", None)
            if risk_contract is not None:
                max_risk = getattr(risk_contract, "max_risk_per_trade", None)
            
            # Determine live eligibility
            status = profile.status or "UNKNOWN"
            live_eligible = _is_live_eligible(status, max_risk)
            
            rows.append(
                ProfileBoardRow(
                    symbol=symbol,
                    timeframe=profile.timeframe,
                    profile_id=profile.profile_id,
                    status=status,
                    pnl_pct=pnl_pct,
                    trades=trades,
                    max_risk_per_trade=max_risk,
                    live_eligible=live_eligible,
                )
            )
    
    # Sort by symbol, timeframe, profile_id
    rows.sort(key=lambda r: (r.symbol, r.timeframe, r.profile_id))
    return rows


def print_profile_board(rows: List[ProfileBoardRow]) -> None:
    """
    Print profile board as a formatted table.
    """
    if not rows:
        print("No profiles found.")
        return
    
    print("=" * 100)
    print("Matrix Strategy Board v1 – CoinPage V2 Profilleri")
    print("=" * 100)
    header = f"{'Symbol':10} {'TF':6} {'Profile':28} {'Status':12} {'PnL%':8} {'Trades':8} {'MaxRisk':8} {'LIVE?':6}"
    print(header)
    print("-" * 100)
    
    for r in rows:
        pnl_str = f"{r.pnl_pct:.2f}%" if r.pnl_pct is not None else "-"
        trades_str = str(r.trades) if r.trades is not None else "-"
        risk_str = f"{r.max_risk_per_trade:.2f}" if r.max_risk_per_trade is not None else "-"
        live_str = "YES" if r.live_eligible else "NO"
        
        # Truncate profile_id if too long
        profile_id_display = r.profile_id[:27] if len(r.profile_id) > 27 else r.profile_id
        
        line = f"{r.symbol:10} {r.timeframe:6} {profile_id_display:28} {r.status:12} {pnl_str:8} {trades_str:8} {risk_str:8} {live_str:6}"
        print(line)
    
    print("-" * 100)
    
    # Summary
    total = len(rows)
    live_count = sum(1 for r in rows if r.live_eligible)
    print(f"Total profiles: {total} | Live eligible: {live_count}")


def main() -> None:
    """CLI entry point."""
    rows = build_profile_board()
    print_profile_board(rows)


if __name__ == "__main__":
    main()
