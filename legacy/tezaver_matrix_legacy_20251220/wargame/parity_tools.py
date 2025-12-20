# Matrix V2 Live vs War Game Parity Tools
"""
Tools for verifying parity between War Game and Live Cluster.

Same dataset + Same profile + Same risk = Same result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Tuple
from pathlib import Path

from tezaver.matrix.core.profile import MatrixProfileRepository
from tezaver.matrix.core.guardrail import GuardrailController, GuardrailConfig, GuardrailEnvironment
from tezaver.matrix.wargame.replay_datafeed import ReplayDataFeed
from tezaver.matrix.wargame.runner import run_silver_15m_from_patterns_for_symbol
from tezaver.matrix.wargame.reports import WargameReport


@dataclass
class ParityResult:
    """Result of comparing War Game vs Live Cluster."""
    symbol: str
    timeframe: str
    profile_id: str
    risk: float
    mode: str  # "contract" | "experiment"

    war_game_capital_end: float
    live_capital_end: float

    war_game_trades: int
    live_trades: int

    war_game_pnl_pct: float
    live_pnl_pct: float

    diff_capital: float
    diff_pnl_pct: float
    
    @property
    def is_parity(self) -> bool:
        """Check if results are within acceptable tolerance."""
        return abs(self.diff_capital) < 1e-6 and abs(self.diff_pnl_pct) < 1e-6


def _build_live_cluster_for_symbol(
    symbol: str,
    risk: float,
    mode: str,
    initial_capital: float = 100.0,
) -> Tuple:
    """
    Build a single-cell Live cluster for the given symbol.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        risk: Risk per trade.
        mode: "contract" or "experiment".
        initial_capital: Starting capital.
        
    Returns:
        Tuple of (cluster, profile_id).
    """
    from tezaver.matrix.live.live_config import MatrixLiveConfig, LiveStrategyCellConfig
    from tezaver.matrix.live.live_cluster import MatrixLiveCluster
    
    coin_page_root = Path("data/coin_profiles")
    repo = MatrixProfileRepository(coin_page_root)
    
    base = symbol.replace("USDT", "")
    profile_id = f"{base}_SILVER_15M_CORE_V1"
    
    # Build guardrail with LIVE environment
    guardrail = GuardrailController(GuardrailConfig())
    
    cell_cfg = LiveStrategyCellConfig(
        symbol=symbol,
        timeframe="15m",
        profile_id=profile_id,
        risk_mode=mode,
    )
    
    live_cfg = MatrixLiveConfig(
        environment=GuardrailEnvironment.WARGAME,  # Use WARGAME for parity (no blocking)
        initial_capital=initial_capital,
        cells=[cell_cfg],
    )
    
    cluster = MatrixLiveCluster(
        live_config=live_cfg,
        profile_repo=repo,
        guardrail=guardrail,
    )
    
    return cluster, profile_id


def run_silver_15m_live_vs_wargame_parity(
    symbol: str,
    risk: float = 1.0,
    mode: str = "experiment",
    tightness: float = 50.0,  # Default 50 for experiment mode (widen_factor=2.0)
) -> ParityResult:
    """
    Run parity check between War Game and Live Cluster.
    
    1) Runs War Game on rally_patterns_v1
    2) Runs same dataset through Live Cluster tick by tick
    3) Compares results
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        risk: Risk per trade (1.0 = 100%).
        mode: "contract" or "experiment".
        tightness: Filter tightness (50 = widen_factor 2.0 for parity).
        
    Returns:
        ParityResult with comparison data.
    """
    timeframe = "15m"
    initial_capital = 100.0
    
    # 1) Run War Game with same tightness as Live Cluster
    war_game_report: WargameReport = run_silver_15m_from_patterns_for_symbol(
        symbol=symbol,
        risk_per_trade_pct=risk,
        mode=mode,
        tightness=tightness,
    )
    
    war_capital_end = war_game_report.capital_end
    war_trades = war_game_report.trade_count
    war_pnl_pct = (war_capital_end / initial_capital - 1.0) * 100.0
    
    # 2) Run Live Cluster with same data
    cluster, profile_id = _build_live_cluster_for_symbol(
        symbol, risk, mode, initial_capital
    )
    
    # Load same parquet data
    feed = ReplayDataFeed.from_symbol_timeframe_silver_patterns(symbol, timeframe)
    
    # Tick through all snapshots
    while feed.has_next():
        snapshot = feed.next()
        if snapshot:
            cluster.tick(symbol, timeframe, snapshot)
    
    # Get live results
    live_capital_end = cluster.get_equity(symbol, timeframe, profile_id)
    live_pnl_pct = (live_capital_end / initial_capital - 1.0) * 100.0
    
    # Get trade count from live ledger
    live_trades = len(cluster._cells[(symbol, timeframe, profile_id)].account_store.get_ledger())
    
    # Calculate diffs
    diff_capital = live_capital_end - war_capital_end
    diff_pnl_pct = live_pnl_pct - war_pnl_pct
    
    return ParityResult(
        symbol=symbol,
        timeframe=timeframe,
        profile_id=profile_id,
        risk=risk,
        mode=mode,
        war_game_capital_end=war_capital_end,
        live_capital_end=live_capital_end,
        war_game_trades=war_trades,
        live_trades=live_trades,
        war_game_pnl_pct=war_pnl_pct,
        live_pnl_pct=live_pnl_pct,
        diff_capital=diff_capital,
        diff_pnl_pct=diff_pnl_pct,
    )


def print_parity_result(result: ParityResult) -> None:
    """Print parity result in a formatted way."""
    print("=== Silver 15m Live vs War Game Parity ===")
    print(f"Symbol   : {result.symbol}")
    print(f"Profile  : {result.profile_id}")
    print(f"Risk     : {result.risk:.2f} (mode={result.mode})")
    print()
    print(f"War Game Capital : 100.00 → {result.war_game_capital_end:.2f}  ({result.war_game_pnl_pct:+.2f}%)")
    print(f"Live Capital     : 100.00 → {result.live_capital_end:.2f}  ({result.live_pnl_pct:+.2f}%)")
    print(f"War Game Trades  : {result.war_game_trades}")
    print(f"Live Trades      : {result.live_trades}")
    print()
    print(f"Δ Capital        : {result.diff_capital:+.6f}")
    print(f"Δ PnL%           : {result.diff_pnl_pct:+.6f}")
    print()
    if result.is_parity:
        print("✅ PARITY: Results match!")
    else:
        print("❌ MISMATCH: Results differ!")
