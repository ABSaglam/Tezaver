"""
Sniper vs Silver A/B Report
============================

Compare Silver full replay and Sniper backtest under same conditions.
CLI and UI compatible.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from tezaver.matrix.wargame.runner import run_silver_15m_full_replay_for_symbol
from tezaver.sniper.sniper_backtest import run_sniper_backtest_for_symbol_timeframe


@dataclass
class StrategyResult:
    """Result of a strategy simulation."""
    name: str
    kind: str  # "silver" or "sniper"
    capital_start: float
    capital_end: float
    pnl_pct: float
    trade_count: int
    win_rate: float
    max_drawdown_pct: float
    extra: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def run_sniper_vs_silver_report(
    symbol: str,
    timeframe: str,
    risk_per_trade: float,
    tightness: int = 50,
    mode: str = "experiment",
) -> Dict[str, Any]:
    """
    Silver full replay vs Sniper backtest under same capital & risk.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Timeframe (e.g., "15m").
        risk_per_trade: Risk per trade (1.0 = 100% equity).
        tightness: Silver filter tightness (0-100).
        mode: "experiment" = bypass risk contract, "contract" = enforce.
        
    Returns:
        Dict with silver, sniper, and delta comparison.
    """
    symbol = symbol.upper()
    
    # 1) Silver – full replay war game
    silver_report = run_silver_15m_full_replay_for_symbol(
        symbol=symbol,
        risk=risk_per_trade,
        mode=mode,
        tightness=tightness,
        start=None,
        end=None,
    )
    
    silver = StrategyResult(
        name="Silver 15m Full Replay",
        kind="silver",
        capital_start=silver_report.capital_start,
        capital_end=silver_report.capital_end,
        pnl_pct=(silver_report.capital_end / silver_report.capital_start - 1.0) * 100.0,
        trade_count=silver_report.trade_count,
        win_rate=silver_report.win_rate * 100.0,  # Convert to percentage
        max_drawdown_pct=silver_report.max_drawdown_pct * 100.0,  # Convert to percentage
        extra={
            "source": "full_replay",
            "environment": "wargame",
            "tightness": tightness,
            "mode": mode,
        },
    )
    
    # 2) Sniper – sniper backtest
    sniper_raw = run_sniper_backtest_for_symbol_timeframe(
        symbol=symbol,
        timeframe=timeframe,
        risk_per_trade=risk_per_trade,
    )
    
    sniper = StrategyResult(
        name="Sniper v1",
        kind="sniper",
        capital_start=sniper_raw["capital_start"],
        capital_end=sniper_raw["capital_end"],
        pnl_pct=sniper_raw["pnl_pct"],
        trade_count=sniper_raw["trade_count"],
        win_rate=sniper_raw["win_rate"],
        max_drawdown_pct=sniper_raw["max_drawdown_pct"],
        extra={
            "entries_total": sniper_raw["total_entries"],
            "entries_selected": sniper_raw["selected_entries"],
            "environment": "offline_sniper",
        },
    )
    
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "risk_per_trade": risk_per_trade,
        "tightness": tightness,
        "mode": mode,
        "silver": silver.to_dict(),
        "sniper": sniper.to_dict(),
        "delta": {
            "capital_end_diff": sniper.capital_end - silver.capital_end,
            "pnl_pct_diff": sniper.pnl_pct - silver.pnl_pct,
            "max_dd_diff": sniper.max_drawdown_pct - silver.max_drawdown_pct,
        },
    }


# =============================================================================
# CLI
# =============================================================================

def _print_sniper_vs_silver_cli(result: Dict[str, Any]) -> None:
    """Print A/B report as formatted table."""
    sym = result["symbol"]
    tf = result["timeframe"]
    risk = result["risk_per_trade"]
    tight = result["tightness"]

    silver = result["silver"]
    sniper = result["sniper"]
    delta = result["delta"]

    print()
    print("=" * 70)
    print(f"🎯 Sniper vs Silver A/B – {sym} {tf}")
    print("=" * 70)
    print(f"Risk / Trade  : {risk:.2f}x equity (mode={result['mode']}, tightness={tight})")
    print()
    print("Strategy         │ 100 → X       │ PnL%     │ Trades │ Win%   │ MaxDD%")
    print("─────────────────┼───────────────┼──────────┼────────┼────────┼────────")
    print(
        f"Silver 15m       │ "
        f"{silver['capital_start']:.0f}→{silver['capital_end']:.1f}".ljust(13) + " │ "
        f"{silver['pnl_pct']:+7.2f}% │ "
        f"{silver['trade_count']:6d} │ "
        f"{silver['win_rate']:5.1f}% │ "
        f"{silver['max_drawdown_pct']:6.1f}%"
    )
    print(
        f"Sniper v1        │ "
        f"{sniper['capital_start']:.0f}→{sniper['capital_end']:.1f}".ljust(13) + " │ "
        f"{sniper['pnl_pct']:+7.2f}% │ "
        f"{sniper['trade_count']:6d} │ "
        f"{sniper['win_rate']:5.1f}% │ "
        f"{sniper['max_drawdown_pct']:6.1f}%"
    )
    print("─────────────────┼───────────────┼──────────┼────────┼────────┼────────")
    print(
        f"Δ (Sniper-Silver)  "
        f"ΔCap={delta['capital_end_diff']:+.1f}, "
        f"ΔPnL={delta['pnl_pct_diff']:+.2f}%, "
        f"ΔMaxDD={delta['max_dd_diff']:+.1f}%"
    )
    print("=" * 70)
    print(
        f"📊 Sniper entries: total={sniper['extra']['entries_total']}, "
        f"selected={sniper['extra']['entries_selected']}"
    )
    print("=" * 70)
    print()


def main():
    """CLI entry point."""
    import sys

    if len(sys.argv) < 4 or sys.argv[1] in ("-h", "--help"):
        print("🎯 Sniper vs Silver A/B Report")
        print("=" * 50)
        print()
        print("Usage:")
        print("  python -m tezaver.sniper.sniper_vs_silver_report SYMBOL TIMEFRAME RISK [TIGHTNESS]")
        print()
        print("Arguments:")
        print("  SYMBOL     Trading symbol (e.g., BTCUSDT)")
        print("  TIMEFRAME  Timeframe (e.g., 15m)")
        print("  RISK       Risk per trade (1.0 = 100% equity)")
        print("  TIGHTNESS  Silver filter tightness 0-100 (default: 50)")
        print()
        print("Examples:")
        print("  python -m tezaver.sniper.sniper_vs_silver_report BTCUSDT 15m 1.0")
        print("  python -m tezaver.sniper.sniper_vs_silver_report BTCUSDT 15m 0.5 75")
        sys.exit(0)

    symbol = sys.argv[1].upper()
    timeframe = sys.argv[2]
    risk = float(sys.argv[3])
    tightness = int(sys.argv[4]) if len(sys.argv) > 4 else 50

    try:
        result = run_sniper_vs_silver_report(
            symbol=symbol,
            timeframe=timeframe,
            risk_per_trade=risk,
            tightness=tightness,
            mode="experiment",
        )
        _print_sniper_vs_silver_cli(result)
    except FileNotFoundError as e:
        print(f"❌ Dosya bulunamadı: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Hata: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
