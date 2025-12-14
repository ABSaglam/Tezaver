"""
NDJSON Log Tail Reader

Provides utilities to read and filter NDJSON log files for the Live Ops Console.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set


def read_ndjson_tail(path: str | Path, n: int = 200) -> Dict[str, Any]:
    """
    Read the last N lines from an NDJSON file.
    
    Returns:
        {
            "events": List[dict],
            "lines_read": int,
            "parse_errors": int,
            "path": str,
        }
    """
    path = Path(path)
    
    if not path.exists():
        return {
            "events": [],
            "lines_read": 0,
            "parse_errors": 0,
            "path": str(path),
            "error": f"File not found: {path}",
        }
    
    events = []
    lines_read = 0
    parse_errors = 0
    
    try:
        # Read all lines and take last N
        with open(path, "r") as f:
            lines = f.readlines()
        
        # Take last N lines
        tail_lines = lines[-n:] if len(lines) > n else lines
        lines_read = len(tail_lines)
        
        for line in tail_lines:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                events.append(event)
            except json.JSONDecodeError:
                parse_errors += 1
    except Exception as e:
        return {
            "events": events,
            "lines_read": lines_read,
            "parse_errors": parse_errors,
            "path": str(path),
            "error": str(e),
        }
    
    return {
        "events": events,
        "lines_read": lines_read,
        "parse_errors": parse_errors,
        "path": str(path),
    }


def filter_events(
    events: List[Dict[str, Any]],
    include_types: Optional[Set[str]] = None,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    text_contains: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Filter events by type, symbol, timeframe, or text content.
    
    Args:
        events: List of event dictionaries
        include_types: Set of event types to include (e.g., {"ORDER_SUBMIT", "ORDER_RESULT"})
        symbol: Filter by symbol (e.g., "BTCUSDT")
        timeframe: Filter by timeframe (e.g., "1m", "15m")
        text_contains: Filter by text content (searches in fingerprint, profile_id, reason)
    
    Returns:
        Filtered list of events
    """
    result = []
    
    for event in events:
        # Filter by event type
        if include_types:
            event_type = event.get("event_type", "")
            if event_type not in include_types:
                continue
        
        # Filter by symbol
        if symbol:
            if event.get("symbol") != symbol:
                continue
        
        # Filter by timeframe
        if timeframe:
            if event.get("timeframe") != timeframe:
                continue
        
        # Filter by text content
        if text_contains:
            text_lower = text_contains.lower()
            searchable = " ".join([
                str(event.get("fingerprint", "")),
                str(event.get("profile_id", "")),
                str(event.get("reason", "")),
                str(event.get("order_id", "")),
            ]).lower()
            if text_lower not in searchable:
                continue
        
        result.append(event)
    
    return result


def get_last_order_events(
    events: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Get the last ORDER_SUBMIT/ORDER_RESULT/ORDER_BLOCKED event per cell.
    
    Returns:
        {
            "BTCUSDT|1m": {
                "last_submit": {...},
                "last_result": {...},
                "last_blocked": {...},
            },
            ...
        }
    """
    cells = {}
    
    for event in events:
        event_type = event.get("event_type", "")
        symbol = event.get("symbol")
        timeframe = event.get("timeframe")
        
        if not symbol or not timeframe:
            continue
        
        cell_key = f"{symbol}|{timeframe}"
        
        if cell_key not in cells:
            cells[cell_key] = {
                "symbol": symbol,
                "timeframe": timeframe,
                "last_submit": None,
                "last_result": None,
                "last_blocked": None,
            }
        
        if event_type == "ORDER_SUBMIT":
            cells[cell_key]["last_submit"] = event
        elif event_type == "ORDER_RESULT":
            cells[cell_key]["last_result"] = event
        elif event_type == "ORDER_BLOCKED":
            cells[cell_key]["last_blocked"] = event
    
    return cells


def events_to_table_rows(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert events to table rows for UI display.
    """
    rows = []
    for event in events:
        fingerprint = event.get("fingerprint", "")
        fingerprint_short = fingerprint[-30:] if len(fingerprint) > 30 else fingerprint
        
        rows.append({
            "ts": event.get("ts", "")[:19] if event.get("ts") else "",
            "event_type": event.get("event_type", ""),
            "symbol": event.get("symbol", ""),
            "tf": event.get("timeframe", ""),
            "profile_id": event.get("profile_id", ""),
            "order_id": event.get("order_id", ""),
            "exec_mode": event.get("exec_mode", ""),
            "allow": "✅" if event.get("allow") else ("❌" if event.get("allow") is False else "-"),
            "success": "✅" if event.get("success") else ("❌" if event.get("success") is False else "-"),
            "reason": event.get("reason", ""),
            "fingerprint": fingerprint_short,
        })
    
    return rows
