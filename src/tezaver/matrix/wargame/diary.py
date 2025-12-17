# Matrix Diary v1
"""
Readable telemetry output for War Game and Live trading.

Provides human-friendly console output of Matrix events.
"""

from typing import Dict, Any, List, Optional

from tezaver.matrix.core.telemetry import MatrixEvent, MatrixEventType
from tezaver.matrix.wargame.reports import WargameReport


def format_event_line(evt: Dict[str, Any]) -> str:
    """
    Convert a single MatrixEvent dict to a short, readable line.
    
    Args:
        evt: Event dict (from MatrixEvent.to_dict() or report.events)
        
    Returns:
        Single-line formatted string for terminal output.
    """
    # Handle both MatrixEvent objects and dicts
    if isinstance(evt, MatrixEvent):
        evt = evt.to_dict()
    
    tick = evt.get("tick_index", "-")
    if tick is None:
        tick = "-"
    
    etype = evt.get("event_type", "UNKNOWN")
    sym = evt.get("symbol", "")
    tf = evt.get("timeframe", "")
    
    # Handle flattened events (M3b): use evt as details if 'details' key missing or empty
    details = evt.get("details")
    if not isinstance(details, dict) or not details:
        details = evt
    
    # Format based on event type
    if etype == "TICK_START":
        note = details.get("note", "")
        return f"TICK {tick:>3} | {'TICK_START':11} | {sym} {tf} | {note}"
    
    elif etype == "TICK_END":
        note = details.get("note", "")
        return f"TICK {tick:>3} | {'TICK_END':11} | {sym} {tf} | {note}"
    
    elif etype == "SIGNAL":
        count = details.get("signal_count", len(details.get("signals", [])))
        signals = details.get("signals", [])
        first_type = signals[0].get("type", "-") if signals else "-"
        return f"TICK {tick:>3} | {'SIGNAL':11} | {sym} {tf} | count={count}, first={first_type}"
    
    elif etype == "DECISION":
        if details.get("decision") is None:
            reason = details.get("reason", "no_trade")
            return f"TICK {tick:>3} | {'DECISION':11} | {sym} {tf} | {reason}"
        else:
            action = details.get("action", "-")
            qty = details.get("quantity", "-")
            tp = details.get("tp_pct", details.get("tp", "-"))
            sl = details.get("sl_pct", details.get("sl", "-"))
            return f"TICK {tick:>3} | {'DECISION':11} | {sym} {tf} | {action} qty={qty}, tp={tp}, sl={sl}"
    
    elif etype == "GUARDRAIL_V2":
        allow = details.get("allow", "-")
        reason = details.get("reason_code", details.get("reason", "-"))
        status = details.get("profile_status", "-")
        return f"TICK {tick:>3} | {'GUARDRAIL_V2':11} | {sym} {tf} | allow={allow}, status={status}, reason={reason}"
    
    elif etype == "GUARDRAIL_V1":
        allow = details.get("allow", "-")
        reason = details.get("reason_code", details.get("reason", "-"))
        return f"TICK {tick:>3} | {'GUARDRAIL_V1':11} | {sym} {tf} | allow={allow}, reason={reason}"
    
    elif etype == "EXECUTION":
        pnl = details.get("pnl", "-")
        eq_after = details.get("equity_after", "-")
        if pnl != "-" and pnl is not None:
            pnl = f"{pnl:+.4f}"
        if eq_after != "-" and eq_after is not None:
            eq_after = f"{eq_after:.2f}"
        return f"TICK {tick:>3} | {'EXECUTION':11} | {sym} {tf} | pnl={pnl}, equity_after={eq_after}"
    
    else:
        # Generic format for INFO and other types
        return f"TICK {tick:>3} | {etype:11} | {sym} {tf} | {details}"


def format_events_as_lines(events: List[Dict[str, Any]]) -> List[str]:
    """
    Convert event list to readable lines for UI display.
    
    Args:
        events: List of event dicts (from report.events)
        
    Returns:
        List of formatted line strings.
    """
    lines: List[str] = []
    for evt in events:
        line = format_event_line(evt)
        lines.append(line)
    return lines


def print_wargame_diary(report: WargameReport) -> None:
    """
    Print War Game telemetry events as a readable 'Matrix Diary'.
    
    Args:
        report: WargameReport containing events from telemetry.
    """
    # Calculate PnL percentage
    pnl_pct = (report.capital_end / report.capital_start - 1.0) * 100.0 if report.capital_start > 0 else 0.0
    
    # Print header
    print("=" * 70)
    print("Matrix Diary v1 – Silver 15m Wargame")
    print("=" * 70)
    print(f"Profile  : {report.profile_id}")
    print(f"Capital  : {report.capital_start:.2f} → {report.capital_end:.2f} ({pnl_pct:+.2f}%)")
    print(f"Trades   : {report.trade_count}")
    print(f"Max DD   : {report.max_drawdown_pct * 100:.2f}%")
    print(f"Events   : {len(report.events or [])}")
    print("=" * 70)
    print()
    
    # Check for events
    if not report.events:
        print("[INFO] Bu War Game için telemetry event bulunamadı.")
        return
    
    # Print each event
    for evt in report.events:
        line = format_event_line(evt)
        print(line)
    
    # Print summary
    print()
    print("-" * 70)
    
    # Count event types
    event_counts: Dict[str, int] = {}
    for evt in report.events:
        etype = evt.get("event_type", "UNKNOWN") if isinstance(evt, dict) else evt.event_type.value
        event_counts[etype] = event_counts.get(etype, 0) + 1
    
    summary_parts = [f"{k}={v}" for k, v in sorted(event_counts.items())]
    print(f"Event Summary: {', '.join(summary_parts)}")
    print("-" * 70)
