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


@dataclass
class RallyOverlay:
    """Rally event overlay data."""
    ts: str
    gain_pct: float
    bars_to_peak: int
    label: str
    raw_details: Dict[str, Any]
    end_ts: Optional[str] = None




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


def parse_open_trades_from_events(events: List[Dict[str, Any]]) -> List[Trade]:
    """Parse currently open (incomplete) trades from events."""
    open_trades = []
    open_orders = {}  # key: (symbol, tf) -> open event
    
    # Re-using similar logic to parse_trades but specifically hunting stragglers
    # Simplification: Just scan for OPENs that are not matched by a CLOSE in the same stream?
    # Better: Scan sequentially.
    
    # We can actually refactor parse_trades_from_events to return (completed, open)
    # But to avoid breaking valid API, let's create a new function or helper.
    
    # Let's do a quick pass for PROOF_OPEN and POSITION_OPEN without matching close
    # This is "good enough" for the diagnostic view
    
    # Efficient approach: Track state
    state = {} # (symbol, tf) -> event
    
    for e in events:
        et = e.get("event_type", "")
        sym = e.get("symbol", "")
        tf = e.get("timeframe", e.get("tf", ""))
        key = (sym, tf)
        
        if et in ("PROOF_OPEN_RESULT", "POSITION_OPEN") or (et == "ORDER_LIFECYCLE_DONE" and e.get("action") == "OPEN"):
            state[key] = e
        elif et in ("PROOF_CLOSE_RESULT", "POSITION_CLOSE") or (et == "ORDER_LIFECYCLE_DONE" and e.get("action") == "CLOSE"):
            if key in state:
                del state[key]
                
    # Remaining in state are open
    for key, evt in state.items():
        sym, tf = key
        open_px = evt.get("fill_price") or evt.get("price") or evt.get("open_px")
        qty = evt.get("qty") or evt.get("fill_qty") or evt.get("open_qty")
        
        open_trades.append(Trade(
            trade_id=f"OPEN_{sym}_{tf}_{evt.get('ts', '')[:19]}",
            symbol=sym,
            timeframe=tf,
            open_ts=evt.get("ts", ""),
            open_px=float(open_px) if open_px else None,
            close_ts=None,
            close_px=None,
            side=evt.get("side", "BUY"),
            qty=float(qty) if qty else None,
            net_pnl=None,
            close_reason=None,
            sl_px=_extract_sl_tp(evt, "sl"),
            tp_px=_extract_sl_tp(evt, "tp"),
        ))
        
    return list(reversed(open_trades))


def get_trade_replay_diagnostics(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate diagnostic summary for Trade Replay."""
    counts = {}
    for e in events:
        et = e.get("event_type", "UNKNOWN")
        counts[et] = counts.get(et, 0) + 1
        
    completed = parse_trades_from_events(events)
    opens = parse_open_trades_from_events(events)
    
    return {
        "event_count": len(events),
        "counts_by_event_type": counts,
        "completed_trades": len(completed),
        "open_trades": len(opens),
    }

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
        "PREFLIGHT_EVAL", "CARD_GATE_EVAL", 
        "RISK_LIMIT_CHECK", "RISK_LIMIT_BLOCK", "RISK_CONTRACT_CHECK",
        "HTF_PERMISSION_EVAL", "HTF_VETO_APPLIED",
        "STRATEGY_SIGNAL",
        "POSITION_OPEN", "POSITION_CLOSE", "POSITION_UPDATE",
        "ORDER_LIFECYCLE_DONE", 
        "INCIDENT_BUNDLE_EXPORTED"
    }
    
    # Collect all candidate events first
    candidates = []
    
    for e in events:
        et = e.get("event_type", "")
        # Fuzzy match for RISK_* and POSITION_* and HTF_* if not in set
        if et not in relevant_types:
            if not (et.startswith("RISK_") or et.startswith("POSITION_") or et.startswith("HTF_")):
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
        
        candidates.append((evt_dt, e))
        
    # Sort by time
    candidates.sort(key=lambda x: x[0])
    
    # Cap at 30 rows logic
    if len(candidates) > 30:
        # Take first 20 (context/entry) and last 10 (exit/result)
        candidates = candidates[:20] + candidates[-10:]
        # Re-dedupe if overlap
        seen = set()
        unique = []
        for dt, e in candidates:
            eid = f"{e.get('ts')}_{e.get('event_type')}"
            if eid not in seen:
                unique.append((dt, e))
                seen.add(eid)
        candidates = unique
    
    for _, e in candidates:
        et = e.get("event_type", "")
        
        # Extract decision/reason
        decision = e.get("decision") or e.get("allow") or e.get("ok")
        if et == "STRATEGY_SIGNAL":
            decision = e.get("signal")
        elif isinstance(decision, bool):
            decision = "PASS" if decision else "BLOCK"
        
        reason = e.get("reason") or e.get("close_reason") or ""
        if isinstance(e.get("reasons"), list):
            reason = ",".join(e.get("reasons", []))[:50]
        elif isinstance(e.get("violations"), list) and e.get("violations"):
             reason = str(e.get("violations")[0])[:50]
        
        # Build details string
        details_parts = []
        for k in ["action", "side", "qty", "price", "pnl", "fill_price"]:
            if k in e:
                val = e[k]
                if isinstance(val, (float, int)):
                     if k in ["price", "fill_price"]: val = f"{val:.2f}"
                     elif k == "pnl": val = f"{val:.4f}"
                details_parts.append(f"{k}={val}")
        
        # For HTF/Signal, add extra details
        if "HTF" in et and "context" in e:
            details_parts.append(f"ctx={str(e['context'])[:20]}")
        
        timeline.append(TimelineRow(
            ts=e.get("ts", "")[:19],
            event_type=et,
            decision=str(decision) if decision is not None else None,
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


def build_decision_context(events: List[Dict[str, Any]], trade: Trade) -> Dict[str, Any]:
    """
    Build "Why" context for a trade - latest relevant decision events.
    
    Returns structured dict with summary and component states.
    """
    context = {
        "summary": "N/A",
        "preflight": None,
        "card_gate": None,
        "risk": None,
        "htf": None,
        "signal": None,
        "signal_reason": None,
        "close_reason": trade.close_reason,
    }
    
    try:
        trade_dt = datetime.fromisoformat(trade.open_ts.replace("Z", "+00:00"))
    except:
        return context
    
    # Iterate events chronologically up to trade_dt
    last_preflight = None
    last_card = None
    last_risk = None
    last_htf = None
    last_signal = None 
    
    for e in events:
        ts_str = e.get("ts", "")
        # Only look at events before/at trade open
        try:
            evt_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if evt_dt > trade_dt + timedelta(seconds=1): # Allow 1s slop
                continue
        except:
            continue
        
        et = e.get("event_type", "")
        
        if et == "PREFLIGHT_EVAL":
            last_preflight = "PASS" if e.get("decision") else "FAIL"
        elif et == "CARD_GATE_EVAL":
            # decision can be bool or string
            dec = e.get("decision")
            if isinstance(dec, bool): dec = "PASS" if dec else "FAIL"
            last_card = dec or e.get("gate", "—")
        elif et.startswith("RISK_"):
            if et == "RISK_LIMIT_BLOCK":
                last_risk = "BLOCK"
            elif et == "RISK_LIMIT_CHECK":
                last_risk = "PASS" if e.get("decision", True) else "BLOCK"
        elif et == "HTF_PERMISSION_EVAL":
             # details: decision=ALLOW/VETO
             last_htf = e.get("decision", "—")
        elif et == "HTF_VETO_APPLIED":
             last_htf = "VETO"
        elif et == "STRATEGY_SIGNAL":
             sig = e.get("signal")
             if sig and sig != "NONE":
                 last_signal = (sig, e.get("reason", ""))
    
    context["preflight"] = last_preflight
    context["card_gate"] = last_card
    context["risk"] = last_risk
    context["htf"] = last_htf
    
    if last_signal:
        context["signal"] = last_signal[0]
        context["signal_reason"] = last_signal[1]
    
    # Build Summary
    # Format: "Sig: {sig} ({reason}) | HTF: {htf} | Risk: {risk}"
    parts = []
    if context["signal"]:
        reason_short = context["signal_reason"] or ""
        if reason_short.startswith("FAIL_"): reason_short = reason_short[5:]
        parts.append(f"Sig: {context['signal']} ({reason_short})")
    
    if context["htf"]:
        parts.append(f"HTF: {context['htf']}")
        
    if context["risk"]:
        parts.append(f"Risk: {context['risk']}")
        
    if not parts and trade.close_reason:
        parts.append(f"Closed: {trade.close_reason}")
        
    context["summary"] = " | ".join(parts) if parts else "No Context Available"
    
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
        
        # Fallback: Legacy SIGNAL events (e.g. from older SIM logs)
        elif et == "SIGNAL":
            if symbol and e.get("symbol") != symbol: continue
            if timeframe and e.get("timeframe") != timeframe: continue
            
            ts_str = e.get("ts", "")
            try:
                evt_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if not (start_dt <= evt_dt <= end_dt): continue
            except: continue
            
            details = e.get("details", {})
            sig_type = details.get("signal_type") or e.get("signal_type")
            
            if sig_type == "SILVER_ENTRY":
                # Treat as OPEN_LONG
                marker_type, color, shape = SIGNAL_MARKER_MAP["OPEN_LONG"]
                signal_label = "OPEN_LONG"
            else:
                marker_type = "signal"
                color = "blue"
                shape = "circle"
                signal_label = sig_type or "SIGNAL"
                
            price = details.get("close") or e.get("close")
            if price is None and isinstance(details.get("snapshot"), dict):
                price = details["snapshot"].get("close")
            
            points.append(OverlayPoint(
                ts=ts_str,
                price=price,
                marker_type=marker_type,
                signal=signal_label,
                reason=details.get("reason"),
                passed_filters=None,
                color=color,
                symbol_shape=shape,
            ))

        # Fallback: Router Decisions (Live)
        elif et == "ROUTER_CLUSTER_DECISION":
            if symbol and e.get("symbol") != symbol: continue
            if timeframe and e.get("timeframe") != timeframe: continue
            
            ts_str = e.get("ts", "")
            try:
                evt_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if not (start_dt <= evt_dt <= end_dt): continue
            except: continue
            
            action = e.get("action")
            if action == "OPEN":
                marker_type, color, shape = SIGNAL_MARKER_MAP["OPEN_LONG"]
                signal_label = "OPEN_LONG"
            elif action == "CLOSE":
                marker_type, color, shape = SIGNAL_MARKER_MAP["CLOSE_LONG"]
                signal_label = "CLOSE_LONG"
            else:
                continue

            points.append(OverlayPoint(
                ts=ts_str,
                price=e.get("price"),
                marker_type=marker_type,
                signal=signal_label,
                reason=e.get("reason"),
                passed_filters=True,
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


@dataclass
class RallyOverlay:
    """Rally event overlay data."""
    ts: str
    gain_pct: float
    bars_to_peak: int
    label: str
    raw_details: Dict[str, Any]
    end_ts: Optional[str] = None
    ahenk_score: Optional[float] = None
    betrayal_risk: Optional[float] = None


def extract_rally_events(
    events: List[Dict[str, Any]],
    start_ts: str,
    end_ts: str,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    show_yorum: bool = False,
) -> List[RallyOverlay]:
    """
    Extract RALLY_DETECTED events for overlay.
    """
    # Lazy import to avoid circular dependency if analysis imports ui
    from tezaver.analysis.olay_yorum import calculate_ahenk_score, calculate_betrayal_risk
    
    rallies = []
    try:
        start_dt = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_ts.replace("Z", "+00:00"))
    except:
        return []
        
    for e in events:
        if len(rallies) >= 200:
            break
            
        if e.get("event_type") != "RALLY_DETECTED":
            continue
            
        if symbol and e.get("symbol") != symbol:
            continue
        if timeframe and e.get("timeframe") != timeframe:
            continue
            
        # Priority: bar_close_ts -> details.event_time -> ts
        details = e.get("details", {})
        ts_val = e.get("bar_close_ts") or details.get("event_time") or e.get("ts")
        
        if not ts_val:
            continue
            
        try:
            # Handle potential non-string in details (pandas Timestamp)
            if hasattr(ts_val, "isoformat"):
                ts_str = ts_val.isoformat()
                dt = ts_val
                if dt.tzinfo is None:
                     dt = dt.replace(tzinfo=timezone.utc)
            else:
                ts_str = str(ts_val)
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                
            if not (start_dt <= dt <= end_dt):
                continue
        except:
            continue
            
        gain = float(details.get("future_max_gain_pct", 0.0))
        bars = int(details.get("bars_to_peak", 0))
        
        label = f"RALLY +{gain:.1%} / {bars} bars"
        
        ahenk = None
        betrayal = None
        
        if show_yorum:
            ahenk, _ = calculate_ahenk_score(details)
            betrayal, _ = calculate_betrayal_risk(details)
            label += f" | Ahenk {ahenk:.2f} | İhanet {betrayal:.2f}"
        
        # Calculate end_ts for zone
        end_ts_val = None
        if timeframe and bars > 0:
            try:
                # Parse timeframe duration (simplified for standard TFs)
                duration_mins = 0
                if timeframe == "15m": duration_mins = 15
                elif timeframe == "1h": duration_mins = 60
                elif timeframe == "4h": duration_mins = 240
                elif timeframe.endswith("m"): duration_mins = int(timeframe[:-1])
                
                if duration_mins > 0:
                    delta = timedelta(minutes=duration_mins * bars)
                    end_ts_dt = dt + delta
                    end_ts_val = end_ts_dt.isoformat()
            except:
                pass
        
        rallies.append(RallyOverlay(
            ts=ts_str,
            gain_pct=gain,
            bars_to_peak=bars,
            label=label,
            raw_details=details,
            end_ts=end_ts_val,
            ahenk_score=ahenk,
            betrayal_risk=betrayal
        ))
        
    return rallies


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


def build_fallback_candles_from_events(
    events: List[Dict[str, Any]], 
    start_ts: str, 
    end_ts: str
) -> List[Dict[str, Any]]:
    """
    Build pseudo-candles from event prices when OHLCV is missing.
    
    Extracts prices from STRATEGY_SIGNAL, ORDER lines, PROOF_OPEN/CLOSE, etc.
    Returns format compatible with load_ohlcv (ts, open=close, volume=0).
    """
    pseudo = []
    try:
        start_dt = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_ts.replace("Z", "+00:00"))
    except:
        return []

    processed_timestamps = set()

    for e in events:
        # Timestamp mapping: prefer bar_close_ts
        ts = e.get("bar_close_ts") or e.get("ts", "")
        if not ts:
            continue
            
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if not (start_dt <= dt <= end_dt):
                continue
        except:
            continue
            
        # Avoid duplicate timestamps for cleaner chart
        if ts in processed_timestamps:
            continue
            
        # Price Priority: close > close_px > fill_price > price > executed_price > snapshot.close > open_px
        price = None
        for key in ["close", "close_px", "fill_price", "price", "executed_price"]:
            if e.get(key) is not None:
                price = e[key]
                break
        
        if price is None and isinstance(e.get("snapshot"), dict):
            price = e["snapshot"].get("close")
            
        if price is None:
             # Fallback to open_px (e.g. for PROOF_OPEN)
             price = e.get("open_px")

        if price is not None:
            try:
                price_val = float(price)
            except:
                continue
            
            if price_val > 0:
                pseudo.append({
                    "ts": ts,
                    "open": price_val,
                    "high": price_val,
                    "low": price_val,
                    "close": price_val,
                    "volume": 0
                })
                processed_timestamps.add(ts)
            
    # Sort by timestamp
    pseudo.sort(key=lambda x: x["ts"])
    return pseudo
