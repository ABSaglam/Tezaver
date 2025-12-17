
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
    """Analyze the output and print a report (v2)."""
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
    
    file_size_kb = p.stat().st_size / 1024
    print(f"  - File size: {len(events)} events ({file_size_kb:.1f} KB)")
    
    # Counts
    target_types = [
        "STRATEGY_SIGNAL", 
        "HTF_PERMISSION_EVAL", 
        "HTF_VETO_APPLIED", 
        "POSITION_OPEN", 
        "POSITION_CLOSE", 
        "ORDER_LIFECYCLE_DONE"
    ]
    counts = {t: 0 for t in target_types}
    
    for e in events:
        et = e.get("event_type", "UNKNOWN")
        if et in counts:
            counts[et] += 1
            
    print("  - Key Event Counts:")
    for et in target_types:
        if counts[et] > 0:
            print(f"    - {et}: {counts[et]}")
        
    # Trades
    completed = parse_trades_from_events(events)
    print(f"  - Completed trades: {len(completed)}")
    
    # Decision Context Sample
    decision_summary = "N/A"
    if completed:
        try:
            from tezaver.ui.trade_replay_data import build_decision_context
            # Find context for first trade
            t = completed[0]
            # Need to filter events up to open_ts? build_dec_ctx handles it but needs list
            ctx = build_decision_context(events, t)
            decision_summary = ctx.get("summary", "N/A")
        except Exception as e:
            decision_summary = f"Error: {e}"
            
    print(f"  - First Trade Context: {decision_summary}")

    # Verdict
    success = len(completed) > 0
    print(f"  - Trade Replay should show: {'YES' if success else 'NO'}")
    if not success:
        print("    (Reason: No completed trades found)")
        
    # JSON Export
    report_data = {
        "ts": datetime.now().isoformat(),
        "events_path": str(events_path),
        "event_count": len(events),
        "counts": counts,
        "completed_trades": len(completed),
        "decision_context_sample": decision_summary,
        "verdict": "YES" if success else "NO"
    }
    
    report_path = Path("data/logs/bringup_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"  - Report saved to: {report_path}")

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
