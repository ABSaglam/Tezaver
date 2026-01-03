"""
ATR Parameter Optimizer (Grid Search)
=====================================

This script finds the best Risk:Reward parameters (ATR Stop/Profit) for a given cipher/coin.
It avoids re-scanning historical data by training once and reusing signals.

Usage:
    python scripts/optimize_atr.py --symbol BTCUSDT --cipher <ID> [--days 730]
"""

import sys
import argparse
import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
from itertools import product
from tabulate import tabulate

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src"))

from tezaver.core.logging_utils import get_logger
from tezaver.smyrna.backtest_engine import BacktestEngine, BacktestConfig, BacktestResult
from run_cipher_backtest_2y import BacktestRunner

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ATROptimizer")

RESULTS_DIR = project_root / ".tezaver_matrix" / "foundry" / "backtests" / "optimization"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Optimize ATR Parameters")
    parser.add_argument("--symbol", type=str, required=True, help="Symbol to optimize (e.g. BTCUSDT)")
    parser.add_argument("--days", type=int, default=730, help="Days to backtest")
    parser.add_argument("--cipher", type=str, required=False, help="Cipher ID (optional)")
    return parser.parse_args()

def main():
    args = parse_arguments()
    symbol = args.symbol
    
    # 1. Initialize Runner and Data (The Heavy Lift)
    logger.info(f"Initializing optimization for {symbol}...")
    runner = BacktestRunner(cipher_path=args.cipher)
    
    if runner.model is None:
        runner.train_model()
        
    logger.info(f"Scanning {symbol} (Last {args.days} days)...")
    signals, price_data = runner.scan_coin(symbol, "15m", args.days)
    
    if signals.empty:
        logger.error("No signals generated! Optimization aborted.")
        return
        
    # Ensure Index Alignment
    if 'open_time' in price_data.columns:
        price_data = price_data.set_index('open_time')
        signals = signals.set_index(price_data.index)
        
    # Check for ATR column
    atr_col = 'atr_14'
    if atr_col not in price_data.columns:
        logger.error(f"ATR column '{atr_col}' not found in price data. Cannot optimize.")
        return

    # 2. Define Grid
    stop_range = np.arange(1.5, 5.5, 0.5)   # 1.5, 2.0, ..., 5.0
    profit_range = np.arange(2.0, 11.0, 1.0) # 2.0, 3.0, ..., 10.0
    
    grid = list(product(stop_range, profit_range))
    logger.info(f"Starting Grid Search: {len(grid)} combinations...")
    
    results = []
    
    # 3. Grid Search Loop
    for stop_mult, profit_mult in grid:
        # Config per iteration
        config = BacktestConfig(
            use_atr_stops=True,
            atr_stop_mult=stop_mult,
            atr_profit_mult=profit_mult,
            atr_column=atr_col,
            initial_capital=10000.0
        )
        
        engine = BacktestEngine(config=config)
        
        # Run Backtest (Fast)
        res = engine.run_backtest(signals, price_data)
        
        results.append({
            "stop_mult": stop_mult,
            "profit_mult": profit_mult,
            "profit_factor": res.profit_factor,
            "total_pnl": res.total_pnl,
            "win_rate": res.win_rate,
            "trades": res.total_trades,
            "max_dd": res.max_drawdown_pct,
            "rr_ratio": profit_mult / stop_mult # Theoretical R:R
        })
        
        # Optional: Print progress for long runs
        # print(f"Tested Stop={stop_mult}, Profit={profit_mult} -> PF: {res.profit_factor:.2f}")

    # 4. Analysis & Ranking
    df_results = pd.DataFrame(results)
    
    # Sort by Profit Factor
    df_results = df_results.sort_values("profit_factor", ascending=False)
    
    best = df_results.iloc[0]
    
    # 5. Reporting
    cipher_id = runner.cipher['cipher_id']
    report_file = RESULTS_DIR / f"opt_atr_{cipher_id}_{symbol}.md"
    
    logger.info(f"Optimization Complete. Best: Stop={best.stop_mult}x, Profit={best.profit_mult}x (PF: {best.profit_factor:.2f})")
    
    with open(report_file, 'w') as f:
        f.write(f"# ATR Optimization Report: {symbol}\n\n")
        f.write(f"- **Cipher:** {cipher_id}\n")
        f.write(f"- **Period:** {args.days} days\n")
        f.write(f"- **Best Parameters:** Stop `{best.stop_mult}x` / Profit `{best.profit_mult}x`\n")
        f.write(f"- **Best Profit Factor:** {best.profit_factor:.2f}\n")
        f.write(f"- **Best PnL:** ${best.total_pnl:.2f}\n\n")
        
        f.write("## Top 10 Configurations\n\n")
        
        # Format table
        top_10 = df_results.head(10)[['stop_mult', 'profit_mult', 'rr_ratio', 'profit_factor', 'total_pnl', 'win_rate', 'trades', 'max_dd']]
        table = tabulate(top_10, headers='keys', tablefmt='github', floatfmt=".2f", showindex=False)
        f.write(table)
        
        f.write("\n\n## Heatmap Data (Top 50)\n")
        f.write(df_results.head(50).to_json(orient="records"))

    print(f"\nOptimization Report saved to: {report_file}")
    print("\nTop 5 Results:")
    print(df_results.head(5)[['stop_mult', 'profit_mult', 'profit_factor', 'total_pnl']].to_string(index=False))

if __name__ == "__main__":
    main()
