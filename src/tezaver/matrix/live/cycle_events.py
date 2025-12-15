"""
Live Cycle Events Parser - NDJSON reader for cycle telemetry.

Reads data/logs/live_events.ndjson and extracts cycle data:
- CYCLE_START, CYCLE_DONE, CYCLE_TIMEOUT
- ORDER_FETCH_OPEN, ORDER_FETCH_CLOSE
- TRADE_AUDIT_V2_DONE
- POSITION_SNAPSHOT_CLOSE
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CycleAlertLevel(Enum):
    """Alert level for a cycle - single source of truth."""
    OK = "OK"
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass
class CycleRecord:
    """Single cycle data extracted from NDJSON."""
    cycle_idx: int
    symbol: str
    timeframe: str
    
    # Timestamps
    start_ts: Optional[str] = None
    done_ts: Optional[str] = None
    
    # Order IDs
    open_order_id: Optional[str] = None
    close_order_id: Optional[str] = None
    
    # Execution
    eff_wait: int = 0
    eff_lag: float = 0.0
    residual_after: float = 0.0
    cycle_bars: int = 0
    exec_mode: str = ""
    
    # Status
    status: str = "UNKNOWN"  # DONE, TIMEOUT
    timeout_reason: Optional[str] = None
    
    # Audit V2 (if available)
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    qty: Optional[float] = None
    gross_pnl: Optional[float] = None
    fee: Optional[float] = None
    net_pnl: Optional[float] = None
    
    # Order statuses
    open_status: Optional[str] = None
    close_status: Optional[str] = None
    
    # Position after close
    pos_after: Optional[float] = None
    
    # Policy config (for reference)
    dust_policy: str = "IGNORE"
    dust_threshold: float = 0.002
    
    # Flags (legacy)
    reduce_only: bool = True
    has_warnings: bool = False
    warnings: List[str] = field(default_factory=list)
    
    # Alert fields (new)
    alert_level: CycleAlertLevel = CycleAlertLevel.OK
    block_reasons: List[str] = field(default_factory=list)
    warn_reasons: List[str] = field(default_factory=list)


def parse_ndjson_file(filepath: Path) -> List[Dict[str, Any]]:
    """Parse NDJSON file and return list of events."""
    events = []
    parse_errors = 0
    
    if not filepath.exists():
        return events
    
    with open(filepath, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                events.append(event)
            except json.JSONDecodeError:
                parse_errors += 1
    
    return events


def filter_events(
    events: List[Dict[str, Any]],
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    event_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Filter events by symbol, timeframe, and event types."""
    filtered = []
    
    for event in events:
        if symbol and event.get("symbol") != symbol:
            continue
        if timeframe and event.get("timeframe") != timeframe:
            continue
        if event_types and event.get("event_type") not in event_types:
            continue
        filtered.append(event)
    
    return filtered


def group_by_cycle(events: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    """Group events by cycle_idx."""
    cycles: Dict[int, List[Dict[str, Any]]] = {}
    
    for event in events:
        cycle_idx = event.get("cycle_idx")
        if cycle_idx is not None:
            if cycle_idx not in cycles:
                cycles[cycle_idx] = []
            cycles[cycle_idx].append(event)
    
    return cycles


def build_cycle_record(cycle_idx: int, events: List[Dict[str, Any]]) -> CycleRecord:
    """Build a CycleRecord from a list of events for a single cycle."""
    record = CycleRecord(
        cycle_idx=cycle_idx,
        symbol="",
        timeframe="",
    )
    
    for event in events:
        event_type = event.get("event_type", "")
        
        # Extract symbol/tf from any event
        if not record.symbol:
            record.symbol = event.get("symbol", "")
        if not record.timeframe:
            record.timeframe = event.get("timeframe", "")
        
        if event_type == "CYCLE_START":
            record.start_ts = event.get("ts")
        
        elif event_type == "CYCLE_DONE":
            record.done_ts = event.get("ts")
            record.status = "DONE"
            record.open_order_id = str(event.get("open_order_id", ""))
            record.close_order_id = str(event.get("close_order_id", ""))
            record.eff_wait = event.get("eff_wait", 0)
            record.eff_lag = event.get("eff_lag", 0.0)
            record.residual_after = event.get("residual_after", 0.0)
            record.cycle_bars = event.get("cycle_bars", 0)
            record.exec_mode = event.get("exec_mode", "")
        
        elif event_type == "CYCLE_TIMEOUT":
            record.done_ts = event.get("ts")
            record.status = "TIMEOUT"
            record.timeout_reason = event.get("reason", "")
            record.open_order_id = str(event.get("open_order_id", ""))
            record.close_order_id = str(event.get("close_order_id", ""))
            record.cycle_bars = event.get("cycle_bars", 0)
        
        elif event_type == "TRADE_AUDIT_V2_DONE":
            record.entry_price = event.get("entry_price")
            record.exit_price = event.get("exit_price")
            record.qty = event.get("qty")
            record.gross_pnl = event.get("gross_pnl_usdt")
            record.fee = event.get("fee_usdt")
            record.net_pnl = event.get("net_pnl_usdt")
            record.open_status = event.get("status_open")
            record.close_status = event.get("status_close")
        
        elif event_type == "POSITION_SNAPSHOT_CLOSE":
            record.pos_after = event.get("pos_amt_now")
        
        elif event_type == "ORDER_FETCH_OPEN":
            if not record.open_status:
                record.open_status = event.get("status")
        
        elif event_type == "ORDER_FETCH_CLOSE":
            if not record.close_status:
                record.close_status = event.get("status")
    
    # Check for warnings (legacy)
    record.warnings = []
    
    if record.pos_after is not None and abs(record.pos_after) > 0.0001:
        record.warnings.append(f"pos_after={record.pos_after} (not zero)")
        record.has_warnings = True
    
    if record.open_status and record.open_status != "FILLED":
        record.warnings.append(f"open_status={record.open_status}")
        record.has_warnings = True
    
    if record.close_status and record.close_status != "FILLED":
        record.warnings.append(f"close_status={record.close_status}")
        record.has_warnings = True
    
    if record.status == "TIMEOUT":
        record.warnings.append(f"TIMEOUT: {record.timeout_reason}")
        record.has_warnings = True
    
    # Compute alert level
    compute_alert_level(record)
    
    return record


def compute_alert_level(record: CycleRecord, cycle_timeout_bars: int = 10) -> None:
    """
    Compute alert level for a cycle record.
    
    BLOCK rules (critical violations):
    - reduce_only is False on CLOSE
    - status_open != FILLED OR status_close != FILLED
    - pos_after != 0.0 (abs > 1e-9) AND not cleaned
    - missing audit fields when REAL mode
    
    WARN rules (minor issues):
    - residual_after > dust_threshold (but cleaned)
    - cycle_bars close to timeout threshold (>= 80%)
    - status == TIMEOUT
    """
    record.block_reasons = []
    record.warn_reasons = []
    
    # BLOCK checks
    if not record.reduce_only:
        record.block_reasons.append("reduce_only=False (CLOSE not reduceOnly)")
    
    if record.open_status and record.open_status != "FILLED":
        record.block_reasons.append(f"open_status={record.open_status} (not FILLED)")
    
    if record.close_status and record.close_status != "FILLED":
        record.block_reasons.append(f"close_status={record.close_status} (not FILLED)")
    
    if record.pos_after is not None and abs(record.pos_after) > 1e-9:
        # Check if dust policy cleaned it (would need cleanup info)
        # For now, any non-zero pos_after is BLOCK
        record.block_reasons.append(f"pos_after={record.pos_after:.6f} (not zero)")
    
    # Missing audit in REAL mode
    if record.exec_mode in ["real_testnet", "real_mainnet"]:
        if record.status == "DONE" and record.close_order_id:
            if record.entry_price is None or record.exit_price is None:
                record.block_reasons.append("missing audit: entry/exit price")
            if record.fee is None or record.net_pnl is None:
                record.block_reasons.append("missing audit: fee/net_pnl")
    
    # WARN checks
    if record.residual_after > record.dust_threshold:
        record.warn_reasons.append(f"residual={record.residual_after:.6f} > threshold={record.dust_threshold}")
    
    if cycle_timeout_bars > 0 and record.cycle_bars >= int(cycle_timeout_bars * 0.8):
        record.warn_reasons.append(f"cycle_bars={record.cycle_bars}/{cycle_timeout_bars} (>=80%)")
    
    if record.status == "TIMEOUT":
        record.warn_reasons.append(f"TIMEOUT: {record.timeout_reason}")
    
    # Determine alert level
    if record.block_reasons:
        record.alert_level = CycleAlertLevel.BLOCK
    elif record.warn_reasons:
        record.alert_level = CycleAlertLevel.WARN
    else:
        record.alert_level = CycleAlertLevel.OK


def load_cycle_records(
    ndjson_path: Path,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    last_n: Optional[int] = None,
) -> List[CycleRecord]:
    """Load and parse cycle records from NDJSON file."""
    events = parse_ndjson_file(ndjson_path)
    
    # Filter for cycle-related events
    cycle_event_types = [
        "CYCLE_START",
        "CYCLE_DONE",
        "CYCLE_TIMEOUT",
        "TRADE_AUDIT_V2_DONE",
        "POSITION_SNAPSHOT_CLOSE",
        "ORDER_FETCH_OPEN",
        "ORDER_FETCH_CLOSE",
    ]
    
    filtered = filter_events(events, symbol, timeframe, cycle_event_types)
    grouped = group_by_cycle(filtered)
    
    records = []
    for cycle_idx, cycle_events in sorted(grouped.items()):
        record = build_cycle_record(cycle_idx, cycle_events)
        records.append(record)
    
    # Sort by done_ts desc (newest first)
    records.sort(key=lambda r: r.done_ts or r.start_ts or "", reverse=True)
    
    if last_n:
        records = records[:last_n]
    
    return records


def compute_aggregates(records: List[CycleRecord]) -> Dict[str, Any]:
    """Compute aggregate statistics from cycle records."""
    if not records:
        return {
            "total_cycles": 0,
            "done_cycles": 0,
            "timeout_cycles": 0,
            "win_count": 0,
            "loss_count": 0,
            "winrate": 0.0,
            "total_gross": 0.0,
            "total_fee": 0.0,
            "total_net": 0.0,
            "avg_eff_lag": 0.0,
            "max_drawdown": 0.0,
            "warning_count": 0,
        }
    
    total_cycles = len(records)
    done_cycles = sum(1 for r in records if r.status == "DONE")
    timeout_cycles = sum(1 for r in records if r.status == "TIMEOUT")
    
    # Net PnL analysis
    wins = [r for r in records if r.net_pnl is not None and r.net_pnl > 0]
    losses = [r for r in records if r.net_pnl is not None and r.net_pnl <= 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    winrate = (win_count / (win_count + loss_count) * 100) if (win_count + loss_count) > 0 else 0.0
    
    total_gross = sum(r.gross_pnl or 0 for r in records)
    total_fee = sum(r.fee or 0 for r in records)
    total_net = sum(r.net_pnl or 0 for r in records)
    
    # Avg eff_lag
    lags = [r.eff_lag for r in records if r.eff_lag > 0]
    avg_eff_lag = sum(lags) / len(lags) if lags else 0.0
    
    # Max drawdown (cumulative net)
    sorted_by_time = sorted([r for r in records if r.done_ts], key=lambda r: r.done_ts or "")
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in sorted_by_time:
        if r.net_pnl is not None:
            cumulative += r.net_pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
    
    warning_count = sum(1 for r in records if r.has_warnings)
    
    # Alert counts
    ok_count = sum(1 for r in records if r.alert_level == CycleAlertLevel.OK)
    warn_count = sum(1 for r in records if r.alert_level == CycleAlertLevel.WARN)
    block_count = sum(1 for r in records if r.alert_level == CycleAlertLevel.BLOCK)
    
    # Worst level
    if block_count > 0:
        worst_level = CycleAlertLevel.BLOCK
    elif warn_count > 0:
        worst_level = CycleAlertLevel.WARN
    else:
        worst_level = CycleAlertLevel.OK
    
    return {
        "total_cycles": total_cycles,
        "done_cycles": done_cycles,
        "timeout_cycles": timeout_cycles,
        "win_count": win_count,
        "loss_count": loss_count,
        "winrate": winrate,
        "total_gross": total_gross,
        "total_fee": total_fee,
        "total_net": total_net,
        "avg_eff_lag": avg_eff_lag,
        "max_drawdown": max_dd,
        "warning_count": warning_count,
        "ok_count": ok_count,
        "warn_count": warn_count,
        "block_count": block_count,
        "worst_level": worst_level,
    }


def format_cycles_table(records: List[CycleRecord]) -> str:
    """Format cycle records as a text table."""
    if not records:
        return "No cycle records found."
    
    lines = []
    header = f"{'Idx':>3} | {'Alert':>5} | {'Status':>7} | {'Open ID':>12} | {'Close ID':>12} | {'Entry':>10} | {'Exit':>10} | {'Net':>10} | {'Bars':>4} | {'Lag':>6}"
    lines.append(header)
    lines.append("-" * len(header))
    
    for r in records:
        entry = f"{r.entry_price:.2f}" if r.entry_price else "N/A"
        exit_p = f"{r.exit_price:.2f}" if r.exit_price else "N/A"
        net = f"{r.net_pnl:.4f}" if r.net_pnl is not None else "N/A"
        
        # Alert emoji
        if r.alert_level == CycleAlertLevel.BLOCK:
            alert = "⛔BLK"
        elif r.alert_level == CycleAlertLevel.WARN:
            alert = "⚠️WRN"
        else:
            alert = "✅ OK"
        
        line = f"{r.cycle_idx:>3} | {alert:>5} | {r.status:>7} | {r.open_order_id[:12]:>12} | {r.close_order_id[:12] if r.close_order_id else 'N/A':>12} | {entry:>10} | {exit_p:>10} | {net:>10} | {r.cycle_bars:>4} | {r.eff_lag:>6.0f}"
        lines.append(line)
    
    return "\n".join(lines)


def format_aggregates(agg: Dict[str, Any]) -> str:
    """Format aggregates as text."""
    lines = [
        "",
        "=== ALERT SUMMARY ===",
        f"✅ OK: {agg.get('ok_count', 0)} | ⚠️ WARN: {agg.get('warn_count', 0)} | ⛔ BLOCK: {agg.get('block_count', 0)}",
        "",
        "=== AGGREGATES ===",
        f"Total Cycles: {agg['total_cycles']} (Done: {agg['done_cycles']}, Timeout: {agg['timeout_cycles']})",
        f"Win/Loss: {agg['win_count']}/{agg['loss_count']} ({agg['winrate']:.1f}% winrate)",
        f"Total Gross: {agg['total_gross']:.6f} USDT",
        f"Total Fee: {agg['total_fee']:.6f} USDT",
        f"Total Net: {agg['total_net']:.6f} USDT",
        f"Avg Eff Lag: {agg['avg_eff_lag']:.1f}s",
        f"Max Drawdown: {agg['max_drawdown']:.6f} USDT",
    ]
    return "\n".join(lines)


@dataclass
class EquityPoint:
    """Single point in equity curve."""
    cycle_idx: int
    ts: str
    net_pnl: float
    equity: float
    cum_return_pct: float
    has_net: bool  # True if net_pnl was available


def compute_equity_curve(
    records: List[CycleRecord],
    equity_start: float = 100.0,
) -> List[EquityPoint]:
    """
    Compute equity curve from cycle records.
    
    Args:
        records: List of CycleRecord (should be sorted by time asc)
        equity_start: Starting equity
    
    Returns:
        List of EquityPoint
    """
    # Sort by time ascending
    sorted_records = sorted(
        [r for r in records if r.status == "DONE"],
        key=lambda r: r.done_ts or r.start_ts or ""
    )
    
    equity = equity_start
    points = []
    
    for r in sorted_records:
        has_net = r.net_pnl is not None
        net = r.net_pnl if has_net else 0.0
        equity += net
        cum_return_pct = ((equity - equity_start) / equity_start) * 100
        
        points.append(EquityPoint(
            cycle_idx=r.cycle_idx,
            ts=r.done_ts or "",
            net_pnl=net,
            equity=equity,
            cum_return_pct=cum_return_pct,
            has_net=has_net,
        ))
    
    return points


def compute_risk_metrics(
    records: List[CycleRecord],
    equity_points: List[EquityPoint],
    equity_start: float = 100.0,
) -> Dict[str, Any]:
    """
    Compute risk metrics from cycle records and equity curve.
    
    Returns dict with:
    - mdd: Max drawdown (absolute)
    - mdd_pct: Max drawdown (%)
    - profit_factor: sum wins / abs sum losses
    - avg_net, median_net, std_net
    - avg_bars, avg_lag
    - alert counts
    """
    import statistics
    
    # Filter DONE cycles
    done_records = [r for r in records if r.status == "DONE"]
    
    if not done_records:
        return {
            "mdd": 0.0,
            "mdd_pct": 0.0,
            "profit_factor": 0.0,
            "avg_net": 0.0,
            "median_net": 0.0,
            "std_net": 0.0,
            "avg_bars": 0.0,
            "avg_lag": 0.0,
            "total_cycles": 0,
        }
    
    # MDD on equity curve
    peak = equity_start
    max_dd = 0.0
    for pt in equity_points:
        if pt.equity > peak:
            peak = pt.equity
        dd = peak - pt.equity
        if dd > max_dd:
            max_dd = dd
    
    mdd_pct = (max_dd / equity_start) * 100 if equity_start > 0 else 0.0
    
    # Profit factor
    wins = [r.net_pnl for r in done_records if r.net_pnl is not None and r.net_pnl > 0]
    losses = [r.net_pnl for r in done_records if r.net_pnl is not None and r.net_pnl <= 0]
    
    sum_wins = sum(wins) if wins else 0.0
    sum_losses = abs(sum(losses)) if losses else 0.0
    profit_factor = sum_wins / sum_losses if sum_losses > 0 else (float('inf') if sum_wins > 0 else 0.0)
    
    # Net stats
    nets = [r.net_pnl for r in done_records if r.net_pnl is not None]
    avg_net = statistics.mean(nets) if nets else 0.0
    median_net = statistics.median(nets) if nets else 0.0
    std_net = statistics.stdev(nets) if len(nets) > 1 else 0.0
    
    # Bars and lag
    bars = [r.cycle_bars for r in done_records if r.cycle_bars > 0]
    lags = [r.eff_lag for r in done_records if r.eff_lag > 0]
    avg_bars = statistics.mean(bars) if bars else 0.0
    avg_lag = statistics.mean(lags) if lags else 0.0
    
    return {
        "mdd": max_dd,
        "mdd_pct": mdd_pct,
        "profit_factor": profit_factor,
        "avg_net": avg_net,
        "median_net": median_net,
        "std_net": std_net,
        "avg_bars": avg_bars,
        "avg_lag": avg_lag,
        "total_cycles": len(done_records),
    }


def format_equity_table(points: List[EquityPoint]) -> str:
    """Format equity curve as text table."""
    if not points:
        return "No equity points."
    
    lines = []
    header = f"{'Idx':>3} | {'Timestamp':>25} | {'Net':>10} | {'Equity':>10} | {'Cum%':>8}"
    lines.append(header)
    lines.append("-" * len(header))
    
    for pt in points:
        net_str = f"{pt.net_pnl:.4f}" if pt.has_net else "N/A"
        line = f"{pt.cycle_idx:>3} | {pt.ts[:25]:>25} | {net_str:>10} | {pt.equity:>10.4f} | {pt.cum_return_pct:>7.2f}%"
        lines.append(line)
    
    return "\n".join(lines)


def format_risk_metrics(metrics: Dict[str, Any]) -> str:
    """Format risk metrics as text."""
    pf_str = f"{metrics['profit_factor']:.2f}" if metrics['profit_factor'] != float('inf') else "∞"
    lines = [
        "",
        "=== RISK METRICS ===",
        f"Max Drawdown: {metrics['mdd']:.4f} USDT ({metrics['mdd_pct']:.2f}%)",
        f"Profit Factor: {pf_str}",
        f"Avg Net: {metrics['avg_net']:.4f} USDT",
        f"Median Net: {metrics['median_net']:.4f} USDT",
        f"Std Dev: {metrics['std_net']:.4f}",
        f"Avg Bars: {metrics['avg_bars']:.1f}",
        f"Avg Lag: {metrics['avg_lag']:.1f}s",
    ]
    return "\n".join(lines)


# =============================================================================
# Timeline Drilldown Functions
# =============================================================================

# Event types relevant for timeline
TIMELINE_EVENT_TYPES = [
    "CYCLE_START",
    "CYCLE_DONE",
    "CYCLE_TIMEOUT",
    "ROUTER_POLICY_STATE",
    "STRATEGY_SIGNAL",
    "ORDER_SUBMIT",
    "ORDER_RESULT",
    "ORDER_FETCH_OPEN",
    "ORDER_FETCH_CLOSE",
    "POSITION_SNAPSHOT_CLOSE",
    "TRADE_AUDIT_V2_DONE",
    "NEW_CLOSED_BAR",
]


def redact_event_secrets(event: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive fields from event."""
    redacted = event.copy()
    
    # Fields to redact
    secret_fields = ["api_key", "api_secret", "secret", "password", "auth", "token"]
    
    for key in list(redacted.keys()):
        if any(sf in key.lower() for sf in secret_fields):
            redacted[key] = "[REDACTED]"
    
    return redacted


def get_cycle_events(
    ndjson_path: Path,
    cycle_idx: int,
    symbol: Optional[str] = None,
    max_events: int = 50,
) -> List[Dict[str, Any]]:
    """
    Get all events for a specific cycle_idx.
    
    Returns events sorted by ts, then event_type.
    """
    events = parse_ndjson_file(ndjson_path)
    
    cycle_events = []
    for event in events:
        if event.get("cycle_idx") == cycle_idx:
            if symbol and event.get("symbol") != symbol:
                continue
            cycle_events.append(event)
    
    # Sort by ts, then event_type
    cycle_events.sort(key=lambda e: (e.get("ts", ""), e.get("event_type", "")))
    
    # Limit
    if len(cycle_events) > max_events:
        cycle_events = cycle_events[:max_events]
    
    # Redact
    return [redact_event_secrets(e) for e in cycle_events]


def format_cycle_timeline(events: List[Dict[str, Any]], cycle_idx: int) -> str:
    """Format cycle events as a timeline."""
    if not events:
        return f"No events found for cycle {cycle_idx}."
    
    lines = [
        f"",
        f"=== CYCLE {cycle_idx} TIMELINE ===",
        f"{'Timestamp':<28} | {'Event Type':<25} | Key Fields",
        "-" * 90,
    ]
    
    for event in events:
        ts = event.get("ts", "")[:27]
        event_type = event.get("event_type", "")[:25]
        
        # Extract key fields based on event type
        key_fields = []
        
        if event_type == "CYCLE_START":
            key_fields.append(f"config={event.get('config', {})}")
        elif event_type == "CYCLE_DONE":
            key_fields.append(f"open={event.get('open_order_id')}")
            key_fields.append(f"close={event.get('close_order_id')}")
            key_fields.append(f"bars={event.get('cycle_bars')}")
        elif event_type == "CYCLE_TIMEOUT":
            key_fields.append(f"reason={event.get('reason')}")
            key_fields.append(f"phase={event.get('phase')}")
        elif event_type == "ORDER_RESULT":
            key_fields.append(f"action={event.get('action')}")
            key_fields.append(f"order_id={event.get('order_id')}")
            key_fields.append(f"success={event.get('success')}")
        elif event_type == "ORDER_FETCH_OPEN" or event_type == "ORDER_FETCH_CLOSE":
            key_fields.append(f"order_id={event.get('order_id')}")
            key_fields.append(f"status={event.get('status')}")
        elif event_type == "TRADE_AUDIT_V2_DONE":
            key_fields.append(f"entry={event.get('entry_price')}")
            key_fields.append(f"exit={event.get('exit_price')}")
            key_fields.append(f"net={event.get('net_pnl_usdt')}")
        elif event_type == "POSITION_SNAPSHOT_CLOSE":
            key_fields.append(f"pos={event.get('pos_amt_now')}")
        elif event_type == "NEW_CLOSED_BAR":
            key_fields.append(f"close={event.get('close')}")
        elif event_type == "ROUTER_POLICY_STATE":
            key_fields.append(f"state={event.get('state')}")
            key_fields.append(f"action={event.get('action')}")
        elif event_type == "STRATEGY_SIGNAL":
            key_fields.append(f"signal={event.get('signal')}")
        else:
            # Generic: show first 3 non-standard fields
            skip_keys = {"ts", "event_type", "cycle_idx", "symbol", "timeframe"}
            for k, v in list(event.items())[:5]:
                if k not in skip_keys:
                    key_fields.append(f"{k}={v}")
        
        key_str = ", ".join(key_fields)[:50]
        lines.append(f"{ts:<28} | {event_type:<25} | {key_str}")
    
    return "\n".join(lines)


def export_cycles_json(records: List[CycleRecord], filepath: Path) -> None:
    """Export cycle records to JSON file."""
    import json
    
    data = []
    for r in records:
        data.append({
            "cycle_idx": r.cycle_idx,
            "symbol": r.symbol,
            "timeframe": r.timeframe,
            "start_ts": r.start_ts,
            "done_ts": r.done_ts,
            "open_order_id": r.open_order_id,
            "close_order_id": r.close_order_id,
            "status": r.status,
            "entry_price": r.entry_price,
            "exit_price": r.exit_price,
            "qty": r.qty,
            "gross_pnl": r.gross_pnl,
            "fee": r.fee,
            "net_pnl": r.net_pnl,
            "eff_wait": r.eff_wait,
            "eff_lag": r.eff_lag,
            "cycle_bars": r.cycle_bars,
            "residual_after": r.residual_after,
            "pos_after": r.pos_after,
            "reduce_only": r.reduce_only,
            "alert_level": r.alert_level.value,
            "block_reasons": r.block_reasons,
            "warn_reasons": r.warn_reasons,
        })
    
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


# =============================================================================
# Incident Bundle Export
# =============================================================================

@dataclass
class IncidentBundleSpec:
    """Specification for incident bundle export."""
    symbol: str
    timeframe: str
    cycle_idx: int
    ndjson_path: str = "data/logs/live_events.ndjson"
    equity_start: float = 100.0
    out_dir: str = "data/incidents"
    include_event_types: Optional[List[str]] = None
    grep: Optional[str] = None
    only_relevant: bool = False


# Core event types for only_relevant filter
RELEVANT_EVENT_TYPES = [
    "CYCLE_START", "CYCLE_DONE", "CYCLE_TIMEOUT",
    "ROUTER_TICK", "LIVE_POLICY_TICK",
    "ROUTER_CLUSTER_GUARDRAIL", "STRATEGY_SIGNAL",
    "ORDER_SUBMIT", "ORDER_RESULT",
    "ORDER_FETCH_OPEN", "ORDER_FETCH_CLOSE",
    "POSITION_SNAPSHOT_CLOSE", "TRADE_AUDIT_V2_DONE",
]


def render_timeline_table(events: List[Dict[str, Any]]) -> str:
    """Render timeline events as a human-readable table."""
    lines = [
        "Timestamp                    | Event Type                | Key Fields",
        "-" * 90,
    ]
    
    for evt in events:
        ts = evt.get("ts", "")[:27]
        evt_type = evt.get("event_type", "")[:25]
        
        # Extract key fields
        key_parts = []
        if evt.get("order_id"):
            key_parts.append(f"order_id={evt.get('order_id')}")
        if evt.get("status"):
            key_parts.append(f"status={evt.get('status')}")
        if evt.get("exec_mode"):
            key_parts.append(f"exec_mode={evt.get('exec_mode')}")
        if evt.get("allow") is not None:
            key_parts.append(f"allow={evt.get('allow')}")
        if evt.get("signal"):
            key_parts.append(f"signal={evt.get('signal')}")
        if evt.get("residual") is not None:
            key_parts.append(f"residual={evt.get('residual')}")
        if evt.get("pos_amt_now") is not None:
            key_parts.append(f"pos_after={evt.get('pos_amt_now')}")
        if evt.get("reduce_only") is not None:
            key_parts.append(f"reduce_only={evt.get('reduce_only')}")
        if evt.get("net_pnl_usdt") is not None:
            key_parts.append(f"net_pnl={evt.get('net_pnl_usdt')}")
        
        key_str = ", ".join(key_parts)[:50] if key_parts else "-"
        lines.append(f"{ts:<28} | {evt_type:<25} | {key_str}")
    
    return "\n".join(lines)


def write_readme(
    spec: IncidentBundleSpec,
    record: CycleRecord,
    events: List[Dict[str, Any]],
    files: List[str],
) -> str:
    """Generate README.txt content for incident bundle."""
    alert_str = record.alert_level.value
    
    # Suggested actions
    suggested = []
    if record.alert_level == CycleAlertLevel.BLOCK:
        if any("reduce_only" in r.lower() for r in record.block_reasons):
            suggested.append("Enforce reduceOnly=True for all CLOSE orders")
        if any("pos_after" in r.lower() for r in record.block_reasons):
            suggested.append("Tighten dust policy or investigate gateway")
        if any("status" in r.lower() for r in record.block_reasons):
            suggested.append("Check order execution logs for failures")
        if any("audit" in r.lower() for r in record.block_reasons):
            suggested.append("Enable --audit flag for complete cycle data")
    elif record.alert_level == CycleAlertLevel.WARN:
        if any("residual" in r.lower() for r in record.warn_reasons):
            suggested.append("Consider adjusting dust threshold")
        if any("timeout" in r.lower() for r in record.warn_reasons):
            suggested.append("Review timeout configuration")
    
    lines = [
        "=" * 60,
        "INCIDENT BUNDLE",
        "=" * 60,
        "",
        f"Symbol: {spec.symbol}",
        f"Timeframe: {spec.timeframe}",
        f"Cycle Index: {spec.cycle_idx}",
        f"Alert Level: {alert_str}",
        "",
        "--- CYCLE SUMMARY ---",
        f"Status: {record.status}",
        f"Open Order ID: {record.open_order_id}",
        f"Close Order ID: {record.close_order_id}",
        f"Entry Price: {record.entry_price}",
        f"Exit Price: {record.exit_price}",
        f"Net PnL: {record.net_pnl}",
        f"Cycle Bars: {record.cycle_bars}",
        "",
        "--- ALERT SUMMARY ---",
    ]
    
    if record.block_reasons:
        lines.append("BLOCK Reasons:")
        for reason in record.block_reasons:
            lines.append(f"  - {reason}")
    if record.warn_reasons:
        lines.append("WARN Reasons:")
        for reason in record.warn_reasons:
            lines.append(f"  - {reason}")
    if not record.block_reasons and not record.warn_reasons:
        lines.append("No violations.")
    
    if suggested:
        lines.append("")
        lines.append("Suggested Actions:")
        for action in suggested:
            lines.append(f"  - {action}")
    
    lines.extend([
        "",
        "--- BUNDLE CONTENTS ---",
    ])
    for f in files:
        lines.append(f"  - {f}")
    
    lines.extend([
        "",
        "--- REPRODUCTION ---",
        f"CLI Command:",
        f"  PYTHONPATH=src python -m tezaver.matrix.live.live_loop report_cycles \\",
        f"    --symbols {spec.symbol} --tf {spec.timeframe} --cycle-idx {spec.cycle_idx} \\",
        f"    --show-timeline --only-relevant",
        "",
        "--- SOURCE ---",
        f"NDJSON Path: {spec.ndjson_path}",
        f"Total Events in Cycle: {len(events)}",
        "",
        "=" * 60,
    ])
    
    return "\n".join(lines)


def build_incident_bundle(spec: IncidentBundleSpec) -> Dict[str, Any]:
    """
    Build incident bundle for a specific cycle.
    
    Returns dict with:
    - success: bool
    - bundle_path: str
    - files: list of file names
    - alert: str (OK/WARN/BLOCK)
    - error: str (if any)
    """
    import os
    from datetime import datetime
    
    ndjson_path = Path(spec.ndjson_path)
    
    # Validate NDJSON exists
    if not ndjson_path.exists():
        return {
            "success": False,
            "error": f"NDJSON file not found: {ndjson_path}",
            "bundle_path": None,
            "files": [],
            "alert": None,
        }
    
    # Parse and filter events
    all_events = parse_ndjson_file(ndjson_path)
    
    # Get events for target cycle
    cycle_events = [e for e in all_events if e.get("cycle_idx") == spec.cycle_idx]
    
    if not cycle_events:
        return {
            "success": False,
            "error": f"No events found for cycle_idx={spec.cycle_idx}",
            "bundle_path": None,
            "files": [],
            "alert": None,
        }
    
    # Filter by symbol
    cycle_events = [e for e in cycle_events if e.get("symbol") == spec.symbol]
    
    # Apply include_event_types filter
    if spec.include_event_types:
        cycle_events = [e for e in cycle_events if e.get("event_type") in spec.include_event_types]
    
    # Apply grep filter
    if spec.grep:
        filtered = []
        for e in cycle_events:
            event_str = json.dumps(e, default=str)
            if spec.grep.lower() in event_str.lower():
                filtered.append(e)
        cycle_events = filtered
    
    # Apply only_relevant filter
    if spec.only_relevant:
        cycle_events = [e for e in cycle_events if e.get("event_type") in RELEVANT_EVENT_TYPES]
    
    # Sort by ts
    cycle_events.sort(key=lambda e: e.get("ts", ""))
    
    # Redact all events
    redacted_events = [redact_event_secrets(e) for e in cycle_events]
    
    # Build CycleRecord - filter events by symbol/timeframe first
    symbol_filtered_events = [e for e in all_events if e.get("symbol") == spec.symbol and e.get("timeframe") == spec.timeframe]
    grouped = group_by_cycle(symbol_filtered_events)
    if spec.cycle_idx not in grouped:
        return {
            "success": False,
            "error": f"No grouped events found for cycle_idx={spec.cycle_idx}",
            "bundle_path": None,
            "files": [],
            "alert": None,
        }
    
    record = build_cycle_record(spec.cycle_idx, grouped[spec.cycle_idx])
    
    # Create bundle folder
    ts_compact = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    folder_name = f"{spec.symbol}_{spec.timeframe}_cycle_{spec.cycle_idx}_{ts_compact}"
    bundle_path = Path(spec.out_dir) / folder_name
    bundle_path.mkdir(parents=True, exist_ok=True)
    
    files_created = []
    
    # 1. cycle_record.json
    record_dict = {
        "cycle_idx": record.cycle_idx,
        "symbol": record.symbol,
        "timeframe": record.timeframe,
        "start_ts": record.start_ts,
        "done_ts": record.done_ts,
        "open_order_id": record.open_order_id,
        "close_order_id": record.close_order_id,
        "status": record.status,
        "entry_price": record.entry_price,
        "exit_price": record.exit_price,
        "qty": record.qty,
        "gross_pnl": record.gross_pnl,
        "fee": record.fee,
        "net_pnl": record.net_pnl,
        "eff_wait": record.eff_wait,
        "eff_lag": record.eff_lag,
        "cycle_bars": record.cycle_bars,
        "residual_after": record.residual_after,
        "pos_after": record.pos_after,
        "reduce_only": record.reduce_only,
        "alert_level": record.alert_level.value,
        "block_reasons": record.block_reasons,
        "warn_reasons": record.warn_reasons,
    }
    record_path = bundle_path / "cycle_record.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(record_dict, f, indent=2, ensure_ascii=False)
    files_created.append("cycle_record.json")
    
    # 2. timeline.jsonl
    timeline_path = bundle_path / "timeline.jsonl"
    with open(timeline_path, "w", encoding="utf-8") as f:
        for evt in redacted_events:
            f.write(json.dumps(evt, ensure_ascii=False, default=str) + "\n")
    files_created.append("timeline.jsonl")
    
    # 3. timeline_table.txt
    table_path = bundle_path / "timeline_table.txt"
    with open(table_path, "w", encoding="utf-8") as f:
        f.write(render_timeline_table(redacted_events))
    files_created.append("timeline_table.txt")
    
    # 4. equity_slice.csv
    records_up_to = load_cycle_records(ndjson_path, spec.symbol, spec.timeframe, last_n=100)
    records_up_to = [r for r in records_up_to if r.cycle_idx <= spec.cycle_idx]
    equity_points = compute_equity_curve(records_up_to, spec.equity_start)
    
    equity_path = bundle_path / "equity_slice.csv"
    with open(equity_path, "w", encoding="utf-8") as f:
        f.write("cycle_idx,timestamp,net_pnl,equity,cum_return_pct\n")
        for pt in equity_points:
            f.write(f"{pt.cycle_idx},{pt.ts},{pt.net_pnl},{pt.equity},{pt.cum_return_pct}\n")
    files_created.append("equity_slice.csv")
    
    # 5. README.txt
    readme_content = write_readme(spec, record, redacted_events, files_created)
    readme_path = bundle_path / "README.txt"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    files_created.append("README.txt")
    
    return {
        "success": True,
        "bundle_path": str(bundle_path),
        "files": files_created,
        "alert": record.alert_level.value,
        "error": None,
    }
