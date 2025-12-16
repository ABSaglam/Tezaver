"""
Trade Replay Data Helpers

Provides functions to parse trades from NDJSON events, build timelines,
and load OHLCV data for charting.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import json


@dataclass
class Trade:
    """Represents an open/close trade pair."""
    trade_id: str
    symbol: str
    timeframe: str
    open_ts: str
    open_px: Optional[float]
    close_ts: Optional[str]
    close_px: Optional[float]
    side: str  # BUY / SELL
    qty: Optional[float]
    net_pnl: Optional[float]
    close_reason: Optional[str]
    sl_px: Optional[float] = None  # Stop loss price
    tp_px: Optional[float] = None  # Take profit price


@dataclass
class TimelineRow:
    """A single event in the trade timeline."""
    ts: str
    event_type: str
    decision: Optional[str]
    reason: Optional[str]
    details: str


@dataclass
class OverlayPoint:
    """A marker point for chart overlay."""
    ts: str  # x coordinate (bar_close_ts or ts)
    price: Optional[float]  # y coordinate
    marker_type: str  # "entry", "exit", "signal", "position_open", "position_close"
    signal: str  # OPEN_LONG, CLOSE_LONG, etc.
    reason: Optional[str]
    passed_filters: Optional[bool]
    rsi: Optional[float] = None
    atr_pct: Optional[float] = None
    color: str = "blue"
    symbol_shape: str = "triangle-up"


# SL/TP field name mappings
SL_FIELDS = ["stop_price", "stop_px", "sl", "stopLoss", "stop_loss"]
TP_FIELDS = ["take_profit", "tp", "takeProfit", "take_profit_price"]


def _extract_sl_tp(event: Dict[str, Any], kind: str) -> Optional[float]:
    """Extract SL or TP price from event if present."""
    fields = SL_FIELDS if kind == "sl" else TP_FIELDS
    for f in fields:
        val = event.get(f)
        if val is not None:
            try:
                return float(val)
            except:
                pass
    return None


def filter_trades(
    trades: List[Trade], 
    symbol: Optional[str] = None, 
    timeframe: Optional[str] = None,
    limit: int = 50,
) -> List[Trade]:
    """
    Filter trades by symbol and/or timeframe.
    
    Args:
        trades: List of Trade objects
        symbol: Filter by symbol (None or "ALL" = no filter)
        timeframe: Filter by timeframe (None or "ALL" = no filter)
        limit: Max trades to return
    
    Returns filtered list (newest first).
    """
    result = trades
    
    if symbol and symbol != "ALL":
        result = [t for t in result if t.symbol == symbol]
    
    if timeframe and timeframe != "ALL":
        result = [t for t in result if t.timeframe == timeframe]
    
    return result[:limit]


def parse_trades_from_events(events: List[Dict[str, Any]]) -> List[Trade]:
    """
    Parse trades from NDJSON events.
    
    Sources (priority):
    1. ORDER_LIFECYCLE_DONE with action=OPEN/CLOSE
    2. POLICY_ACTION events
    
    Returns list of Trade objects (most recent first).
    """
    trades = []
    open_orders = {}  # key: (symbol, tf) -> open event
    
    for e in events:
        et = e.get("event_type", "")
        
        # ORDER_LIFECYCLE_DONE events
        if et == "ORDER_LIFECYCLE_DONE":
            action = e.get("action", "")
            symbol = e.get("symbol", "")
            tf = e.get("timeframe", e.get("tf", ""))
            cell_key = (symbol, tf)
            
            if action == "OPEN":
                open_orders[cell_key] = e
            elif action == "CLOSE" and cell_key in open_orders:
                open_evt = open_orders.pop(cell_key)
                
                # Calculate PnL if possible
                open_px = open_evt.get("fill_price") or open_evt.get("price")
                close_px = e.get("fill_price") or e.get("price")
                qty = open_evt.get("fill_qty") or open_evt.get("qty")
                
                pnl = None
                if open_px and close_px and qty:
                    side = open_evt.get("side", "BUY")
                    if side == "BUY":
                        pnl = (close_px - open_px) * qty
                    else:
                        pnl = (open_px - close_px) * qty
                
                # Extract SL/TP if present
                sl_px = _extract_sl_tp(open_evt, "sl")
                tp_px = _extract_sl_tp(open_evt, "tp")
                
                trade = Trade(
                    trade_id=f"{symbol}_{tf}_{open_evt.get('ts', '')[:19]}",
                    symbol=symbol,
                    timeframe=tf,
                    open_ts=open_evt.get("ts", ""),
                    open_px=open_px,
                    close_ts=e.get("ts", ""),
                    close_px=close_px,
                    side=open_evt.get("side", "BUY"),
                    qty=qty,
                    net_pnl=pnl,
                    close_reason=e.get("reason", e.get("close_reason", "")),
                    sl_px=sl_px,
                    tp_px=tp_px,
                )
                trades.append(trade)
        
        # PROOF_OPEN_RESULT / PROOF_CLOSE_RESULT pairing
        elif et == "PROOF_OPEN_RESULT":
            symbol = e.get("symbol", "")
            tf = e.get("timeframe", "")
            cell_key = (symbol, tf)
            open_orders[cell_key] = e
            
        elif et == "PROOF_CLOSE_RESULT":
            symbol = e.get("symbol", "")
            tf = e.get("timeframe", "")
            cell_key = (symbol, tf)
            
            if cell_key in open_orders:
                open_evt = open_orders.pop(cell_key)
                
                # PROOF fields: open_qty / close_qty, fill_price might be missing or simulated
                open_px = open_evt.get("fill_price")
                close_px = e.get("fill_price")
                qty = open_evt.get("open_qty")
                
                pnl = None
                if open_px and close_px and qty:
                    # PROOF is typically LONG only for now
                    pnl = (close_px - open_px) * qty
                
                trade = Trade(
                    trade_id=f"PROOF_{symbol}_{tf}_{open_evt.get('ts', '')[:19]}",
                    symbol=symbol,
                    timeframe=tf,
                    open_ts=open_evt.get("ts", ""),
                    open_px=open_px,
                    close_ts=e.get("ts", ""),
                    close_px=close_px,
                    side="BUY",  # Default to BUY for PROOF
                    qty=qty,
                    net_pnl=pnl,
                    close_reason=e.get("reason", ""),
                )
                trades.append(trade)

        # POSITION_OPEN / POSITION_CLOSE pairing
        elif et == "POSITION_OPEN":
            symbol = e.get("symbol", "")
            tf = e.get("timeframe", "")
            cell_key = (symbol, tf)
            open_orders[cell_key] = e
            
        elif et == "POSITION_CLOSE":
            symbol = e.get("symbol", "")
            tf = e.get("timeframe", "")
            cell_key = (symbol, tf)
            
            if cell_key in open_orders:
                open_evt = open_orders.pop(cell_key)
                
                # POSITION events usually don't have price/qty details in V1, mostly timestamps
                trade = Trade(
                    trade_id=f"POS_{symbol}_{tf}_{open_evt.get('ts', '')[:19]}",
                    symbol=symbol,
                    timeframe=tf,
                    open_ts=open_evt.get("ts", ""),
                    open_px=None,
                    close_ts=e.get("ts", ""),
                    close_px=None,
                    side="BUY", 
                    qty=open_evt.get("qty"),
                    net_pnl=None,
                    close_reason=None,
                )
                trades.append(trade)
        
        # POLICY_CYCLE_RESULT as backup
        elif et == "POLICY_CYCLE_RESULT":
            symbol = e.get("symbol", "")
            tf = e.get("timeframe", e.get("tf", ""))
            
            trade = Trade(
                trade_id=f"{symbol}_{tf}_{e.get('ts', '')[:19]}",
                symbol=symbol,
                timeframe=tf,
                open_ts=e.get("open_ts", e.get("ts", "")),
                open_px=e.get("open_price"),
                close_ts=e.get("close_ts", e.get("ts", "")),
                close_px=e.get("close_price"),
                side=e.get("side", "BUY"),
                qty=e.get("qty"),
                net_pnl=e.get("pnl") or e.get("net_pnl"),
                close_reason=e.get("close_reason", ""),
            )
            trades.append(trade)
    
    # Reverse to show newest first
    return list(reversed(trades))


def build_trade_timeline(
    events: List[Dict[str, Any]], 
    trade: Trade,
    window_minutes: int = 30
) -> List[TimelineRow]:
    """
    Build timeline of events around a trade window.
    
    Filters events by:
    - symbol/timeframe match
    - timestamp within [open_ts - window, close_ts + window]
    """
    timeline = []
    
    # Parse trade timestamps
    try:
        open_dt = datetime.fromisoformat(trade.open_ts.replace("Z", "+00:00"))
        close_ts = trade.close_ts or trade.open_ts
        close_dt = datetime.fromisoformat(close_ts.replace("Z", "+00:00"))
    except:
        return timeline
    
    window = timedelta(minutes=window_minutes)
    start_dt = open_dt - window
    end_dt = close_dt + window
    
    relevant_types = {
        "PREFLIGHT_EVAL", "CARD_GATE_EVAL", "RISK_LIMIT_CHECK", "RISK_LIMIT_BLOCK",
        "MAINNET_GUARD_EVAL", "MAINNET_ARMED", "ORDER_LIFECYCLE_START", 
        "ORDER_LIFECYCLE_DONE", "POLICY_OPEN", "POLICY_CLOSE", "POLICY_CYCLE_RESULT",
        "INCIDENT_BUNDLE_EXPORTED", "ROUTER_TICK"
    }
    
    for e in events:
        et = e.get("event_type", "")
        if et not in relevant_types:
            continue
        
        # Check symbol/tf match (if present)
        sym = e.get("symbol", "")
        tf = e.get("timeframe", e.get("tf", ""))
        if sym and sym != trade.symbol:
            continue
        if tf and tf != trade.timeframe:
            continue
        
        # Check timestamp
        ts_str = e.get("ts", "")
        try:
            evt_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if not (start_dt <= evt_dt <= end_dt):
                continue
        except:
            continue
        
        # Extract decision/reason
        decision = e.get("decision") or e.get("allow") or e.get("ok")
        if isinstance(decision, bool):
            decision = "PASS" if decision else "BLOCK"
        
        reason = e.get("reason") or e.get("close_reason") or ""
        if isinstance(e.get("reasons"), list):
            reason = ",".join(e.get("reasons", []))[:50]
        
        # Build details string
        details_parts = []
        for k in ["action", "side", "qty", "price", "violations"]:
            if k in e:
                val = e[k]
                if isinstance(val, list):
                    val = str(val)[:30]
                details_parts.append(f"{k}={val}")
        
        timeline.append(TimelineRow(
            ts=ts_str[:19],
            event_type=et,
            decision=str(decision) if decision else None,
            reason=str(reason)[:50] if reason else None,
            details=", ".join(details_parts)[:60],
        ))
    
    return timeline


def get_ohlcv_paths(symbol: str, timeframe: str) -> List[Path]:
    """
    Get list of possible OHLCV parquet paths to try.
    
    Returns paths in priority order:
    1. coin_cells/{SYMBOL}/data/history_{TF}.parquet (primary)
    2. data/enriched/{SYMBOL}/klines_{TF}.parquet (fallback)
    3. TEZAVER_OHLCV_ROOT env override
    """
    import os
    from tezaver.core.coin_cell_paths import get_history_file, get_project_root
    
    paths = []
    
    # Primary: coin_cells path
    paths.append(get_history_file(symbol, timeframe))
    
    # Fallback: data/enriched
    root = get_project_root()
    paths.append(root / "data" / "enriched" / symbol / f"klines_{timeframe}.parquet")
    
    # Env override
    env_root = os.environ.get("TEZAVER_OHLCV_ROOT")
    if env_root:
        paths.append(Path(env_root) / symbol / f"history_{timeframe}.parquet")
    
    return paths


def load_ohlcv(
    symbol: str, 
    timeframe: str, 
    start_ts: str, 
    end_ts: str,
    lookback_bars: int = 20,
    lookforward_bars: int = 10,
) -> tuple:
    """
    Load OHLCV candles from local parquet storage.
    
    Returns tuple: (candles_list, paths_tried)
    - candles_list: List of candle dicts or None
    - paths_tried: List of paths attempted (for error messages)
    """
    import pandas as pd
    
    paths_tried = get_ohlcv_paths(symbol, timeframe)
    
    # Find first existing path
    parquet_path = None
    for p in paths_tried:
        if p.exists():
            parquet_path = p
            break
    
    if not parquet_path:
        return (None, paths_tried)
    
    try:
        df = pd.read_parquet(parquet_path)
        
        # Parse timestamps
        start_dt = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_ts.replace("Z", "+00:00"))
        
        # Filter to window
        if "datetime" in df.columns:
            df["_dt"] = pd.to_datetime(df["datetime"], utc=True)
        elif "timestamp" in df.columns:
            df["_dt"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        else:
            return (None, paths_tried)
        
        # Find indices
        mask = (df["_dt"] >= start_dt) & (df["_dt"] <= end_dt)
        if not mask.any():
            return (None, paths_tried)
        
        first_idx = mask.idxmax()
        last_idx = mask[::-1].idxmax()
        
        # Extend window
        start_idx = max(0, first_idx - lookback_bars)
        end_idx = min(len(df) - 1, last_idx + lookforward_bars)
        
        df_window = df.iloc[start_idx:end_idx + 1]
        
        candles = []
        for _, row in df_window.iterrows():
            candles.append({
                "ts": row["_dt"].isoformat() if pd.notna(row["_dt"]) else "",
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)),
            })
        
        return (candles if candles else None, paths_tried)
        
    except Exception:
        return (None, paths_tried)


def get_trade_context(events: List[Dict[str, Any]], trade: Trade) -> Dict[str, Any]:
    """
    Get "Why" context for a trade - latest relevant decision events.
    """
    context = {
        "preflight": None,
        "card_gate": None,
        "risk_limit": None,
        "mainnet_guard": None,
        "close_reason": trade.close_reason,
    }
    
    try:
        trade_dt = datetime.fromisoformat(trade.open_ts.replace("Z", "+00:00"))
    except:
        return context
    
    for e in events:
        ts_str = e.get("ts", "")
        try:
            evt_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            # Only look at events before/at trade open
            if evt_dt > trade_dt:
                continue
        except:
            continue
        
        et = e.get("event_type", "")
        
        if et == "PREFLIGHT_EVAL":
            context["preflight"] = e.get("decision")
        elif et == "CARD_GATE_EVAL":
            context["card_gate"] = e.get("decision") or e.get("gate")
        elif et in ("RISK_LIMIT_CHECK", "RISK_LIMIT_BLOCK"):
            context["risk_limit"] = e.get("decision")
        elif et == "MAINNET_GUARD_EVAL":
            context["mainnet_guard"] = e.get("decision")
    
    return context


# Signal to marker mapping
SIGNAL_MARKER_MAP = {
    "OPEN_LONG": ("entry", "green", "triangle-up"),
    "OPEN_SHORT": ("entry", "red", "triangle-down"),
    "CLOSE_LONG": ("exit", "red", "triangle-down"),
    "CLOSE_SHORT": ("exit", "green", "triangle-up"),
    "NONE": ("signal", "gray", "circle"),
}


def extract_strategy_signals(
    events: List[Dict[str, Any]],
    start_ts: str,
    end_ts: str,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    max_signals: int = 200,
) -> List[OverlayPoint]:
    """
    Extract strategy signals from events within a time window.
    
    Returns list of OverlayPoint for chart overlay.
    """
    points = []
    
    try:
        start_dt = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_ts.replace("Z", "+00:00"))
    except:
        return points
    
    for e in events:
        if len(points) >= max_signals:
            break
        
        et = e.get("event_type", "")
        
        # STRATEGY_SIGNAL events
        if et == "STRATEGY_SIGNAL":
            # Filter by symbol/timeframe if specified
            if symbol and e.get("symbol") != symbol:
                continue
            if timeframe and e.get("timeframe") != timeframe:
                continue
            
            # Check timestamp in window
            ts_str = e.get("bar_close_ts") or e.get("ts", "")
            try:
                evt_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if not (start_dt <= evt_dt <= end_dt):
                    continue
            except:
                continue
            
            # Get signal and map to marker
            signal = e.get("signal", "NONE")
            marker_type, color, shape = SIGNAL_MARKER_MAP.get(signal, ("signal", "gray", "circle"))
            
            # Skip NONE signals by default
            if signal == "NONE":
                continue
            
            # Get price
            price = e.get("close")
            if price is None and isinstance(e.get("snapshot"), dict):
                price = e["snapshot"].get("close")
            
            points.append(OverlayPoint(
                ts=ts_str,
                price=price,
                marker_type=marker_type,
                signal=signal,
                reason=e.get("reason"),
                passed_filters=e.get("passed_filters"),
                rsi=e.get("rsi"),
                atr_pct=e.get("atr_pct"),
                color=color,
                symbol_shape=shape,
            ))
        
        # POSITION_OPEN / POSITION_CLOSE events
        elif et in ("POSITION_OPEN", "POSITION_CLOSE"):
            if symbol and e.get("symbol") != symbol:
                continue
            if timeframe and e.get("timeframe") != timeframe:
                continue
            
            ts_str = e.get("ts", "")
            try:
                evt_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if not (start_dt <= evt_dt <= end_dt):
                    continue
            except:
                continue
            
            marker_type = "position_open" if et == "POSITION_OPEN" else "position_close"
            color = "green" if et == "POSITION_OPEN" else "red"
            
            points.append(OverlayPoint(
                ts=ts_str,
                price=None,  # Will be resolved from OHLCV
                marker_type=marker_type,
                signal=et,
                reason=None,
                passed_filters=None,
                color=color,
                symbol_shape="line-ns" if "POSITION" in et else "circle",
            ))
    
    return points


def resolve_price_for_signal(
    point: OverlayPoint,
    candles: Optional[List[Dict[str, Any]]],
) -> float:
    """
    Resolve price for an overlay point.
    
    Priority:
    1. Use point.price if present
    2. Interpolate from OHLCV candles at point.ts
    3. Default to 0
    """
    if point.price is not None:
        return point.price
    
    if candles and point.ts:
        # Find closest candle
        try:
            point_dt = datetime.fromisoformat(point.ts.replace("Z", "+00:00"))
            best_candle = None
            best_diff = None
            
            for c in candles:
                c_ts = c.get("ts", "")
                try:
                    c_dt = datetime.fromisoformat(c_ts.replace("Z", "+00:00"))
                    diff = abs((c_dt - point_dt).total_seconds())
                    if best_diff is None or diff < best_diff:
                        best_diff = diff
                        best_candle = c
                except:
                    continue
            
            if best_candle:
                return float(best_candle.get("close", 0))
        except:
            pass
    
    return 0.0
