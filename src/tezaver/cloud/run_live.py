"""
CLOUD-1000: Cloud Service Runner
CLI entry point for cloud trading service.

Usage:
    python -m tezaver.cloud.run_live --symbols BTCUSDT --tf 15m --mode PAPER
"""
import argparse
import sys
from tezaver.cloud.core.cloud_engine import CloudEngine


def main():
    parser = argparse.ArgumentParser(
        description="Tezaver Cloud Trading Service",
        prog="tezaver.cloud.run_live"
    )
    
    parser.add_argument(
        "--symbols",
        type=str,
        default="BTCUSDT",
        help="Comma-separated symbols (e.g., BTCUSDT,ETHUSDT)"
    )
    
    parser.add_argument(
        "--tf",
        type=str,
        default="15m",
        help="Timeframe (15m, 1h, 4h)"
    )
    
    parser.add_argument(
        "--mode",
        type=str,
        default="PAPER",
        choices=["PAPER", "LIVE"],
        help="Trading mode"
    )
    
    parser.add_argument(
        "--data-mode",
        type=str,
        default="REPLAY",
        choices=["REPLAY", "POLL"],
        help="Data feed mode"
    )
    
    parser.add_argument(
        "--max-bars",
        type=int,
        default=None,
        help="Maximum bars to process (for testing)"
    )
    
    parser.add_argument(
        "--fee-pct",
        type=float,
        default=0.001,
        help="Fee percentage"
    )
    
    parser.add_argument(
        "--slippage-pct",
        type=float,
        default=0.0005,
        help="Slippage percentage"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="out/cloud_runs",
        help="Output directory for artifacts"
    )
    
    args = parser.parse_args()
    
    # Parse symbols
    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    
    print(f"=== Tezaver Cloud Service ===")
    print(f"Symbols: {symbols}")
    print(f"Timeframe: {args.tf}")
    print(f"Mode: {args.mode}")
    print(f"Data Mode: {args.data_mode}")
    print(f"Max Bars: {args.max_bars or 'unlimited'}")
    print(f"=============================")
    
    # Create and run engine
    engine = CloudEngine(
        symbols=symbols,
        tf=args.tf,
        mode=args.mode,
        data_mode=args.data_mode,
        output_dir=args.output_dir,
        fee_pct=args.fee_pct,
        slippage_pct=args.slippage_pct
    )
    
    result = engine.run(max_bars=args.max_bars)
    
    print(f"=== Run Complete ===")
    print(f"Run ID: {result['run_id']}")
    print(f"Status: {result['status']}")
    print(f"Bars: {result['bar_count']}")
    print(f"Trades: {result['trade_count']}")
    print(f"Artifacts: {result['artifacts_dir']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
