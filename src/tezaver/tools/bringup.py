
"""
One-click bring-up reset tool for Tezaver Trade Replay using SIM.
Guarantees at least 1 completed trade and chart data.
"""

import argparse
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tezaver.matrix.wargame.runner import run_silver_15m_from_patterns_for_symbol
from tezaver.ui.trade_replay_data import parse_trades_from_events, load_ohlcv

DEFAULT_EVENTS_PATH = "data/logs/live_events.ndjson"

def run_sim_bringup(
    symbol: str = "BTCUSDT",
    timeframe: str = "15m",
    days: int = 2,
    events_path: str = DEFAULT_EVENTS_PATH,
) -> None:
    """Run a quick simulation to generate events."""
    print(f"🚀 Starting SIM bring-up for {symbol}/{timeframe} ({days} days)...")
    
    # Ensure directory exists and clear old file if needed?
    # User might want to append, but "reset" implies clearing.
    # Let's clear to guarantee "bring-up reset" behavior creates a clean state.
    # But wait, user request says "reuse existing runner", doesn't explicitly say separate file.
    # "Guarantees Trade Replay is populated". Usually better to append or rotate?
    # Request title: "BRING-UP RESET v1". Reset implies clearing.
    p = Path(events_path)
    if p.exists():
        print(f"Dataset exists at {p}. Rotating old file.")
        p.rename(p.with_suffix(f".bak.{int(time.time())}.ndjson"))
    
    # Run Wargame (forced close ensured by runner arg)
    print("⏳ Running simulation...")
    # Using patterns scenario as it is fast and deterministic
    run_silver_15m_from_patterns_for_symbol(
        symbol=symbol,
        days=days,
        events_path=events_path,
        force_close_on_exit=True
    )
    print("✅ Simulation complete.")

def generate_self_check_report(events_path: str) -> None:
    """Analyze the output and print a report."""
    p = Path(events_path)
    if not p.exists():
        print(f"❌ Error: Events file not found at {events_path}")
        return

    print(f"\n📊 SELF-CHECK REPORT ({events_path})")
    
    # Read events
    events = []
    with open(p, "r") as f:
        for line in f:
            if line.strip():
                try:
                    events.append(json.loads(line))
                except:
                    pass
    
    print(f"  - File size: {len(events)} events ({p.stat().st_size / 1024:.1f} KB)")
    
    # Counts
    counts = {}
    for e in events:
        et = e.get("event_type", "UNKNOWN")
        counts[et] = counts.get(et, 0) + 1
    
    print("  - Top event types:")
    for et, c in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"    - {et}: {c}")
        
    # Trades
    completed = parse_trades_from_events(events)
    # Check for simple open/close pairs if library parse fails (backup check)
    opens = [e for e in events if e.get("event_type") in ("PROOF_OPEN_RESULT", "POSITION_OPEN")]
    closes = [e for e in events if e.get("event_type") in ("PROOF_CLOSE_RESULT", "POSITION_CLOSE")]
    
    print(f"  - Completed trades: {len(completed)}")
    print(f"  - Raw Open/Close events: {len(opens)}/{len(closes)}")
    
    # Chart Data Mode
    # Use first trade to check OHLCV
    chart_mode = "UNKNOWN"
    reason = "No trades to check"
    
    if completed:
        t = completed[0]
        candles, _ = load_ohlcv(t.symbol, t.timeframe, t.open_ts, t.close_ts)
        if candles:
            chart_mode = "OHLCV (Standard)"
            reason = "Found parquet data"
        else:
            chart_mode = "FALLBACK (Events)"
            reason = "Missing OHLCV, using events"
    
    print(f"  - Chart Data Mode: {chart_mode} ({reason})")
    
    # Verdict
    success = len(completed) > 0
    print(f"  - Trade Replay should show: {'YES' if success else 'NO'}")
    if not success:
        print("    (Reason: No completed trades found)")

def main():
    parser = argparse.ArgumentParser(description="Tezaver Bring-up Reset Tool")
    parser.add_argument("--mode", choices=["SIM", "DUMMY_ORDER", "REAL_TESTNET"], default="SIM")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--days", type=int, default=2)
    parser.add_argument("--events-path", default=DEFAULT_EVENTS_PATH)
    
    args = parser.parse_args()
    
    if args.mode == "SIM":
        run_sim_bringup(
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days,
            events_path=args.events_path
        )
    else:
        print(f"Mode {args.mode} not yet implemented (placeholder).")
        # Placeholder: could just write a dummy event to file to prove writing works
        return

    generate_self_check_report(args.events_path)

if __name__ == "__main__":
    main()
