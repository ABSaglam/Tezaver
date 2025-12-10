"""
Tezaver Sim Core Experiments
============================

Core strategy experiments for single-button testing.
Config is now derived from Silver Strategy Card v1.
"""

from typing import Dict, Any
from dataclasses import replace

from tezaver.sim.sim_presets import get_preset_by_id, build_config_from_preset
from tezaver.sim.sim_config import RallySimConfig
from tezaver.sim import sim_engine


def build_btc_15m_core_strategy_config_from_card() -> RallySimConfig:
    """
    Build RallySimConfig for BTC15M_STRATEGY_V1.
    Base config from preset, overridden by Silver Strategy Card v1.
    
    Rules:
      - sl_pct floor: minimum 2% (0.02)
      - max_horizon_bars ceiling: 48 bars (12 hours)
    """
    # 1) Base config from preset
    preset = get_preset_by_id("BTC15M_STRATEGY_V1")
    if preset is None:
        # Fallback: create minimal config
        return RallySimConfig(
            symbol="BTCUSDT",
            timeframe="15m",
            min_quality_score=60.0,
            tp_pct=0.07,
            sl_pct=0.035,
            max_horizon_bars=24
        )
    
    cfg = build_config_from_preset(preset, symbol="BTCUSDT")

    # 2) Load Strategy Card
    try:
        from tezaver.rally.rally_grade_cards import load_btc_15m_silver_strategy_card_v1
        card = load_btc_15m_silver_strategy_card_v1()
    except ImportError:
        card = None
    
    if not card or not card.get("ok", False):
        # Card missing or invalid, use preset as-is
        return cfg

    filters = card.get("filters", {})
    risk = card.get("risk", {})

    # --- Quality Score ---
    q_f = filters.get("quality_score") or {}
    q_min = q_f.get("min")
    if q_min is not None:
        try:
            cfg = replace(cfg, min_quality_score=float(q_min))
        except (TypeError, ValueError):
            pass

    # --- Allowed Shapes ---
    shapes_f = filters.get("rally_shape") or {}
    allowed_shapes = shapes_f.get("allowed") or []
    if allowed_shapes:
        cfg = replace(cfg, allowed_shapes=list(allowed_shapes))

    # --- TP ---
    tp = risk.get("tp_pct")
    if tp is not None:
        try:
            cfg = replace(cfg, tp_pct=float(tp))
        except (TypeError, ValueError):
            pass

    # --- SL with 2% floor ---
    sl = risk.get("sl_pct")
    if sl is not None:
        try:
            sl_val = float(sl)
            # SL floor: minimum 2%
            if sl_val < 0.02:
                sl_val = 0.02
            cfg = replace(cfg, sl_pct=sl_val)
        except (TypeError, ValueError):
            pass

    # --- Horizon with 48 bar ceiling ---
    horizon = risk.get("max_horizon_bars")
    if horizon is not None:
        try:
            h_val = int(horizon)
            # 48 bar = 12 hours (15m)
            if h_val > 48:
                h_val = 48
            cfg = replace(cfg, max_horizon_bars=h_val)
        except (TypeError, ValueError):
            pass

    return cfg


def run_btc_15m_core_strategy_sim() -> Dict[str, Any]:
    """
    Run BTC 15m core strategy simulation.
    Config is now derived from Silver Strategy Card v1.
    """
    return run_btc_core_strategy_sim("15m")


def run_btc_core_strategy_sim(timeframe: str) -> Dict[str, Any]:
    """
    Generic BTC core strategy simulation for any timeframe (15m, 1h, 4h).
    Config is derived from Silver Strategy Card for that timeframe.
    """
    symbol = "BTCUSDT"
    profile_id = f"BTC{timeframe.upper()}_STRATEGY_V1"
    
    # Build config from strategy card
    cfg = _build_btc_config_from_card(symbol, timeframe)

    events_df = sim_engine.load_rally_events(symbol, timeframe)
    prices_df = sim_engine.load_price_series(symbol, timeframe)

    if events_df.empty:
        return {
            "ok": False,
            "reason": "no_rally_events",
            "config_id": profile_id,
            "symbol": symbol,
            "timeframe": timeframe,
        }

    if prices_df.empty:
        return {
            "ok": False,
            "reason": "no_price_data",
            "config_id": profile_id,
            "symbol": symbol,
            "timeframe": timeframe,
        }

    filtered_events = sim_engine.filter_events(events_df, cfg)

    if filtered_events.empty:
        return {
            "ok": False,
            "reason": "no_events_after_filter",
            "config_id": profile_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "raw_event_count": len(events_df),
        }

    trades_df, equity_df = sim_engine.simulate_trades(filtered_events, prices_df, cfg)

    perf = {
        "trade_count": 0,
        "win_rate": 0.0,
        "avg_pnl": 0.0,
        "sum_pnl": 0.0,
        "max_drawdown": 0.0,
        "final_equity": 1.0,
        "capital_start": 100.0,
        "capital_end": 100.0,
    }

    if trades_df is not None and len(trades_df) > 0:
        total_trades = len(trades_df)
        
        pnl_col = "pnl" if "pnl" in trades_df.columns else "gross_return_pct"
        
        wins = (trades_df[pnl_col] > 0).sum()
        win_rate = wins / total_trades if total_trades > 0 else 0.0

        avg_pnl = float(trades_df["gross_return_pct"].mean() * 100.0) if total_trades > 0 else 0.0
        sum_pnl = float(trades_df["gross_return_pct"].sum() * 100.0) if total_trades > 0 else 0.0

        # Max drawdown
        max_dd = 0.0
        if not equity_df.empty and "equity" in equity_df.columns:
            max_equity = equity_df["equity"].cummax()
            drawdowns = (equity_df["equity"] - max_equity) / max_equity
            max_dd = float(drawdowns.min() * 100.0)

        # Capital tracking
        pnl_series = trades_df["gross_return_pct"].astype(float)
        equity_curve = (1.0 + pnl_series).cumprod()
        final_equity = float(equity_curve.iloc[-1]) if not equity_curve.empty else 1.0
        capital_start = 100.0
        capital_end = capital_start * final_equity

        perf = {
            "trade_count": int(total_trades),
            "win_rate": float(win_rate),
            "avg_pnl": avg_pnl,
            "sum_pnl": sum_pnl,
            "max_drawdown": max_dd,
            "final_equity": final_equity,
            "capital_start": capital_start,
            "capital_end": capital_end,
        }

    config_info = {
        "tp_pct": cfg.tp_pct,
        "sl_pct": cfg.sl_pct,
        "max_horizon_bars": cfg.max_horizon_bars,
    }

    return {
        "ok": True,
        "config_id": profile_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "config_from_card": True,
        "config": config_info,
        "event_count": len(filtered_events),
        "performance": perf,
    }


def _build_btc_config_from_card(symbol: str, timeframe: str) -> RallySimConfig:
    """
    Build RallySimConfig from Silver Strategy Card for any timeframe.
    """
    from tezaver.rally.rally_grade_cards import load_silver_strategy_card_v1
    
    # Default config
    default_cfg = RallySimConfig(
        symbol=symbol,
        timeframe=timeframe,
        tp_pct=0.10,
        sl_pct=0.035,
        max_horizon_bars=24,
    )
    
    # Load card
    card = load_silver_strategy_card_v1(symbol, timeframe)
    
    if not card or not card.get("ok", False):
        return default_cfg
    
    risk = card.get("risk", {})
    
    tp_pct = risk.get("tp_pct", 0.10)
    sl_pct = risk.get("sl_pct", 0.035)
    max_horizon = risk.get("max_horizon_bars", 24)
    
    # Apply floors/ceilings based on timeframe
    if timeframe == "15m":
        if sl_pct < 0.02:
            sl_pct = 0.02
        if max_horizon > 48:
            max_horizon = 48
    elif timeframe == "1h":
        if sl_pct < 0.03:
            sl_pct = 0.03
        if max_horizon > 24:
            max_horizon = 24
    elif timeframe == "4h":
        if sl_pct < 0.04:
            sl_pct = 0.04
        if max_horizon > 12:
            max_horizon = 12
    
    return RallySimConfig(
        symbol=symbol,
        timeframe=timeframe,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        max_horizon_bars=max_horizon,
    )

