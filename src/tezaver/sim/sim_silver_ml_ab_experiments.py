"""
Tezaver Silver Strategy ML Filter A/B Experiments
==================================================

Test the same Silver strategy with different ML filter combinations:
- baseline: No ML filters
- ml_atr: Only ATR 15m ML band
- ml_atr_rsi1h: ATR + RSI 1H ML band
- ml_all: ATR + RSI 1H + 1D RSI Gap

Now includes Capital 100 → X tracking.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd

from tezaver.sim.sim_config import RallySimConfig
from tezaver.sim import sim_engine
from tezaver.sim.sim_core_experiments import (
    build_btc_15m_core_strategy_config_from_card,
)
from tezaver.rally.rally_grade_cards import (
    load_btc_15m_silver_strategy_card_v1,
)


SYMBOL = "BTCUSDT"
TIMEFRAME = "15m"
CAPITAL_START = 100.0


@dataclass
class ScenarioResult:
    name: str
    event_count: int
    trade_count: int
    win_rate: float
    avg_pnl: float          # per-trade average return (0.07 = 7%)
    sum_pnl: float          # total return (0.39 = 39%)
    max_drawdown: float     # absolute value (0.10 = 10%)
    final_equity: float     # equity curve final (1.0 → 100, 2.0 → 200)
    capital_start: float    # starting capital (100)
    capital_end: float      # ending capital (e.g. 241.5)


def _load_events_and_prices() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load BTC 15m rally events and price series."""
    events = sim_engine.load_rally_events(SYMBOL, TIMEFRAME)
    prices = sim_engine.load_price_series(SYMBOL, TIMEFRAME)
    return events, prices


def _compute_rsi_gap_1d(events: pd.DataFrame) -> pd.DataFrame:
    """Add 1D RSI gap column if source columns exist."""
    if "rsi_1d" in events.columns and "rsi_ema_1d" in events.columns:
        events = events.copy()
        events["rsi_gap_1d_local"] = events["rsi_1d"] - events["rsi_ema_1d"]
    return events


def _compute_segment_performance(
    trades: pd.DataFrame,
    equity_df: pd.DataFrame
) -> Dict[str, float]:
    """Compute performance metrics from trades DataFrame with capital tracking."""
    capital_start = CAPITAL_START
    
    if trades is None or trades.empty:
        return {
            "trade_count": 0,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "sum_pnl": 0.0,
            "max_drawdown": 0.0,
            "final_equity": 1.0,
            "capital_start": capital_start,
            "capital_end": capital_start,
        }

    trade_count = int(len(trades))
    
    # Find PnL column
    pnl_col = "gross_return_pct"
    if pnl_col not in trades.columns:
        pnl_col = "pnl" if "pnl" in trades.columns else None
    
    if pnl_col is None:
        return {
            "trade_count": trade_count,
            "win_rate": 0.0,
            "avg_pnl": 0.0,
            "sum_pnl": 0.0,
            "max_drawdown": 0.0,
            "final_equity": 1.0,
            "capital_start": capital_start,
            "capital_end": capital_start,
        }

    pnl = trades[pnl_col].astype(float)
    
    wins = (pnl > 0).sum()
    win_rate = float(wins) / float(trade_count) if trade_count > 0 else 0.0
    
    avg_pnl = float(pnl.mean()) if trade_count > 0 else 0.0
    sum_pnl = float(pnl.sum())

    # Equity curve: 1.0 base = 100 capital
    equity = (1.0 + pnl).cumprod()
    peak = equity.cummax()
    dd = (equity - peak) / peak
    max_dd = float(dd.min()) if not dd.empty else 0.0
    
    final_equity = float(equity.iloc[-1]) if not equity.empty else 1.0
    capital_end = capital_start * final_equity

    return {
        "trade_count": trade_count,
        "win_rate": win_rate,
        "avg_pnl": avg_pnl,
        "sum_pnl": sum_pnl,
        "max_drawdown": abs(max_dd),
        "final_equity": final_equity,
        "capital_start": capital_start,
        "capital_end": capital_end,
    }


def _get_ml_filters_from_card() -> Dict[str, Any]:
    """Get ML filters from Silver Strategy Card v2."""
    card = load_btc_15m_silver_strategy_card_v1()
    if not card or not card.get("ok", False):
        return {}
    return card.get("ml_filters") or {}


# ---- ML Filter Applicators ----

def _filter_with_atr(
    df: pd.DataFrame,
    ml_filters: Dict[str, Any],
) -> pd.DataFrame:
    """Apply ATR 15m ML band filter."""
    f = ml_filters.get("atr_pct_15m")
    if not f:
        return df

    atr_min = float(f.get("min", 0))
    atr_max = float(f.get("max", float("inf")))

    if "atr_pct_15m" not in df.columns:
        return df

    mask = (df["atr_pct_15m"] >= atr_min) & (df["atr_pct_15m"] <= atr_max)
    return df.loc[mask].copy()


def _filter_with_rsi1h(
    df: pd.DataFrame,
    ml_filters: Dict[str, Any],
) -> pd.DataFrame:
    """Apply RSI 1H ML band filter."""
    f = ml_filters.get("rsi_1h")
    if not f:
        return df

    rsi_min = float(f.get("min", 0))
    rsi_max = float(f.get("max", 100))

    if "rsi_1h" not in df.columns:
        return df

    mask = (df["rsi_1h"] >= rsi_min) & (df["rsi_1h"] <= rsi_max)
    return df.loc[mask].copy()


def _filter_with_rsi_gap_1d(
    df: pd.DataFrame,
    ml_filters: Dict[str, Any],
) -> pd.DataFrame:
    """Apply 1D RSI Gap filter (rsi_1d - rsi_ema_1d)."""
    f = ml_filters.get("rsi_gap_1d")
    if not f:
        return df

    gap_min = float(f.get("min", -float("inf")))
    gap_max = float(f.get("max", float("inf")))

    if "rsi_gap_1d_local" not in df.columns:
        df = _compute_rsi_gap_1d(df)

    if "rsi_gap_1d_local" not in df.columns:
        return df

    mask = (df["rsi_gap_1d_local"] >= gap_min) & (df["rsi_gap_1d_local"] <= gap_max)
    return df.loc[mask].copy()


def _run_scenario(
    name: str,
    events: pd.DataFrame,
    prices: pd.DataFrame,
    cfg: RallySimConfig,
) -> ScenarioResult:
    """Run simulation for a specific scenario with capital tracking."""
    if events is None or events.empty:
        return ScenarioResult(
            name=name,
            event_count=0,
            trade_count=0,
            win_rate=0.0,
            avg_pnl=0.0,
            sum_pnl=0.0,
            max_drawdown=0.0,
            final_equity=1.0,
            capital_start=CAPITAL_START,
            capital_end=CAPITAL_START,
        )

    # Run simulation
    trades_df, equity_df = sim_engine.simulate_trades(events, prices, cfg)
    perf = _compute_segment_performance(trades_df, equity_df)
    
    return ScenarioResult(
        name=name,
        event_count=int(len(events)),
        trade_count=perf["trade_count"],
        win_rate=perf["win_rate"],
        avg_pnl=perf["avg_pnl"],
        sum_pnl=perf["sum_pnl"],
        max_drawdown=perf["max_drawdown"],
        final_equity=perf["final_equity"],
        capital_start=perf["capital_start"],
        capital_end=perf["capital_end"],
    )


def run_btc_15m_silver_ml_ab_test() -> Dict[str, Any]:
    """
    Run 4-scenario A/B test for Silver Strategy + ML filters.
    Now includes Capital 100 → X tracking.
    """
    # 1) Config from Silver Strategy Card v2
    cfg = build_btc_15m_core_strategy_config_from_card()

    # 2) Load events + prices
    events_raw, prices = _load_events_and_prices()

    # 3) Apply base filters via sim_engine
    base_events = sim_engine.filter_events(events_raw, cfg)
    base_events = base_events.copy()

    # 4) Get ML filters from card
    ml_filters = _get_ml_filters_from_card()

    # 4a) Compute derived columns
    base_events = _compute_rsi_gap_1d(base_events)

    # ---- Scenarios ----
    scenarios: Dict[str, ScenarioResult] = {}

    # A) Baseline - no ML filters
    scenarios["baseline"] = _run_scenario("baseline", base_events, prices, cfg)

    # B) ML-ATR only
    df_ml_atr = _filter_with_atr(base_events, ml_filters)
    scenarios["ml_atr"] = _run_scenario("ml_atr", df_ml_atr, prices, cfg)

    # C) ML-ATR + RSI1H
    df_ml_atr_rsi1h = _filter_with_rsi1h(df_ml_atr, ml_filters)
    scenarios["ml_atr_rsi1h"] = _run_scenario("ml_atr_rsi1h", df_ml_atr_rsi1h, prices, cfg)

    # D) ML-ALL (ATR + RSI1H + RSI Gap 1D)
    df_ml_all = _filter_with_rsi_gap_1d(df_ml_atr_rsi1h, ml_filters)
    scenarios["ml_all"] = _run_scenario("ml_all", df_ml_all, prices, cfg)

    # ---- Summary ----
    summary = {
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "scenarios": {},
    }

    for key, res in scenarios.items():
        summary["scenarios"][key] = {
            "name": res.name,
            "event_count": res.event_count,
            "trade_count": res.trade_count,
            "win_rate": res.win_rate,
            "avg_pnl": res.avg_pnl,
            "sum_pnl": res.sum_pnl,
            "max_drawdown": res.max_drawdown,
            "final_equity": res.final_equity,
            "capital_start": res.capital_start,
            "capital_end": res.capital_end,
        }

    return summary


if __name__ == "__main__":
    print("=" * 60)
    print("BTCUSDT 15m Silver Strategy – ML Filter A/B Test")
    print("=" * 60)
    
    summary = run_btc_15m_silver_ml_ab_test()

    print(f"Symbol:   {summary['symbol']}")
    print(f"TF:       {summary['timeframe']}")
    print()

    for key, s in summary["scenarios"].items():
        print(f"[{key}]")
        print(f"  events:      {s['event_count']}")
        print(f"  trades:      {s['trade_count']}")
        print(f"  win_rate:    {s['win_rate']*100:.1f}%")
        print(f"  avg_pnl:     {s['avg_pnl']*100:.2f}%")
        print(f"  sum_pnl:     {s['sum_pnl']*100:.2f}%")
        print(f"  max_dd:      {s['max_drawdown']*100:.2f}%")
        print(f"  capital_100: 100 → {s['capital_end']:.2f}")
        print()
