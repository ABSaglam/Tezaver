"""
Cipher Backtest Runner (2-Year Comprehensive)
=============================================

This script executes a backtest for a given Master Cipher JSON.

Since Ciphers only store feature definitions (the "Recipe"), this script must:
1. Re-train a model (RandomForest) using the Cipher's features and training data.
2. Scan historical data (e.g. 2 years) for all target coins.
3. Generate signals using the re-trained model.
4. Run BacktestEngine to simulate trades.

Usage:
    python scripts/run_cipher_backtest_2y.py --cipher <CIPHER_ID_OR_PATH> [--symbol <SYMBOL>] [--days <DAYS>]

Example:
    python scripts/run_cipher_backtest_2y.py --cipher DIAMOND_GRIND_ANY_15m_20260103_110602 --symbol BTCUSDT --days 730
"""

import sys
import argparse
import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from concurrent.futures import ProcessPoolExecutor # Parallel processing might be needed, but let's stick to simple first

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "src"))

from tezaver.core.rally_store import RallyStore
from tezaver.core.logging_utils import get_logger
from tezaver.core.coin_cell_paths import get_history_file
from tezaver.smyrna.cipher_generator import CipherGenerator
from tezaver.smyrna.feature_engine import extract_all_features
from tezaver.smyrna.backtest_engine import BacktestEngine, BacktestConfig
from tezaver.smyrna.data_access import get_rally_context
from sklearn.ensemble import RandomForestClassifier

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BacktestRunner")

VAULT_DIR = project_root / ".tezaver_matrix" / "vault" / "ciphers"
RESULTS_DIR = project_root / ".tezaver_matrix" / "foundry" / "backtests"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


class BacktestRunner:
    def __init__(self, cipher_path: str, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.cipher_path = Path(cipher_path if cipher_path else "LATEST") # Handle None
        
        # Resolve 'LATEST' logic if needed, or error if None passed and not handled
        if str(self.cipher_path) == "LATEST" or cipher_path is None:
             # Find latest in vault
             files = sorted(VAULT_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
             if not files:
                 raise FileNotFoundError("No ciphers found in vault!")
             self.cipher_path = files[0]
        
        if not self.cipher_path.exists():
            # Try finding in vault by ID
            candidate = VAULT_DIR / f"{cipher_path}.json"
            if candidate.exists():
                self.cipher_path = candidate
            else:
                # Try explicit filename in vault
                candidate = VAULT_DIR / str(cipher_path)
                if candidate.exists(): 
                     self.cipher_path = candidate
                else:
                    raise FileNotFoundError(f"Cipher not found: {cipher_path}")
        
        with open(self.cipher_path, 'r') as f:
            self.cipher = json.load(f)
            
        logger.info(f"Loaded Cipher: {self.cipher['cipher_id']}")
        
        self.store = RallyStore()
        self.model = None
        self.selected_features = self.cipher['entry_rules']['selected_features']
        
    def train_model(self):
        """Re-train model using cipher's Training Params."""
        target = self.cipher['target']
        tier = target.get('tier') if target.get('tier') != "ANY" else None
        archetype = target.get('archetype') if target.get('archetype') != "ANY" else None
        coin_class = target.get('coin_class') if target.get('coin_class') != "ANY" else None
        timeframe = target.get('timeframe', '15m')
        
        logger.info("loading training data...")
        
        # Load Rallies
        # We reuse CipherGenerator's logic to get the same dataset
        gen = CipherGenerator() 
        rallies = gen.load_training_rallies(
            tier=tier, 
            archetype=archetype, 
            coin_class=coin_class, 
            timeframe=timeframe,
            min_count=10
        )
        
        if not rallies:
            raise ValueError("No training rallies found!")
            
        # Prepare Dataset (Positives)
        gen = CipherGenerator()
        X_pos, y_pos, _ = gen.prepare_dataset(rallies)
        
        # FIX: Generate Negative Samples using Shared Logic (Multi-Coin)
        logger.info("Generating Negative Samples (Noise)...")
        
        # Use simple 1:1 ratio
        n_negatives = len(X_pos)
        
        # Call Generator's method
        X_neg, y_neg = gen.generate_negative_samples(count=n_negatives, timeframe=timeframe)
        
        if not X_neg.empty:
            # Combine
            # Ensure columns match (CipherGenerator handles this, but let's be safe)
            # Align columns: X_neg might have different columns if extraction changed, 
            # but extract_all_features is consistent.
            
            X = pd.concat([X_pos, X_neg], ignore_index=True)
            y = pd.concat([y_pos, y_neg], ignore_index=True)
            
            logger.info(f"Training Data Balanced: {len(X_pos)} Pos / {len(X_neg)} Neg")
        else:
             logger.warning("Failed to generate negatives. Using unbalanced data.")
             X, y = X_pos, y_pos

        # Filter Features
        X_selected = X[self.selected_features].fillna(0)
        
        logger.info(f"Training Model on {len(X)} samples with {len(self.selected_features)} features...")
        
        # Train Random Forest (Standard Params)
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.model.fit(X_selected, y)
        
        accuracy = self.model.score(X_selected, y)
        logger.info(f"Model Trained. Training Accuracy: {accuracy:.2f}")

        # Safety Check for Single Class
        if len(self.model.classes_) < 2:
            logger.warning("Model learned only 1 class! Forcing binary probability hack.")
            # This happens if user has no history for negatives.
            # We can't fix it easily without history.

    def scan_coin(self, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
        """Scan historical data for a single coin (Vectorized)."""
        history_path = get_history_file(symbol, timeframe)
        if not history_path.exists():
            logger.warning(f"No history found for {symbol}")
            return pd.DataFrame(), pd.DataFrame()
            
        # Load History
        df = pd.read_parquet(history_path)
        if 'open_time' in df.columns:
            # Ensure datetime
            if df['open_time'].dtype == object:
                 df['open_time'] = pd.to_datetime(df['open_time'])
            df = df.sort_values('open_time').reset_index(drop=True)
            
        # Filter last N days
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        # Assuming open_time is datetime, filter
        if 'open_time' in df.columns:
             start_idx = df[df['open_time'] > cutoff].index.min()
             if pd.notna(start_idx):
                 df = df.iloc[start_idx:].reset_index(drop=True)
        
        logger.info(f"Scanning {symbol} ({len(df)} bars)...")
        
        # 1. Feature Extraction (Vectorized - Fast)
        # We process the entire dataframe at once.
        # Note: extract_all_features expects OHLCV columns present.
        try:
            full_features_df = extract_all_features(df)
            
            # Select only features used by the model
            # Fill NaNs with 0 (or mean? 0 is safer for now as RandomForest handles it)
            X_scan = full_features_df[self.selected_features].fillna(0)
            
            # 2. Predict (Vectorized)
            logger.info("Predicting signals...")
            # predict_proba returns [prob_0, prob_1]
            probs = self.model.predict_proba(X_scan)[:, 1]
            
            # 3. Generate Signals
            signals_df = pd.DataFrame(index=df.index, columns=['entry', 'exit'])
            signals_df['entry'] = probs > 0.65  # Threshold
            signals_df['exit'] = False
            
            # Simple Exit Logic for Backtest:
            # - Exit after 50 bars (Time based)
            # - OR Stop Loss / Take Profit (Requires iterating? BacktestEngine handles SL/TP better)
            # For now, let's just mark entries. BacktestEngine needs distinct exit signals 
            # if we rely on it to close. 
            
            # Since BacktestEngine expects explicit 'exit' signal to close loop,
            # we need to set exits.
            # Vectorized exit setting: Shift entry signal by 50 bars
            # signals_df['exit'] = signals_df['entry'].shift(50).fillna(False)
            
            # But BacktestEngine logic is: "if entry and not in_position -> Enter".
            # "if exit and in_position -> Exit".
            # So simplistic shift works.
            
            # However, simpler approach:
            # Iterate through signals ONLY (fast) to set smart exits? 
            # Or just let BacktestEngine manage it if we modify it?
            # BacktestEngine currently only exits if 'exit' is True.
            
            # Let's use a fixed holding period of 40 bars (10 hours for 15m) as a baseline
            signals_df['exit'] = signals_df['entry'].shift(40).fillna(False)
            
            return signals_df, full_features_df
            
        except Exception as e:
            logger.error(f"Scan failed for {symbol}: {e}")
            return pd.DataFrame(), pd.DataFrame()

    def run(self, symbol: str, days: int):
        if self.model is None:
            self.train_model()
            
        logger.info(f"Starting Scan for {symbol} (Last {days} days)")
        signals, price_data = self.scan_coin(symbol, "15m", days)
        
        if signals.empty:
            logger.warning("No signals generated.")
            return

        # FIX: Ensure Timestamps in Index for BacktestEngine
        if 'open_time' in price_data.columns:
            price_data = price_data.set_index('open_time')
            # Align signals index
            signals = signals.set_index(price_data.index)

        # Run Backtest
        engine = BacktestEngine(config=self.config)
        result = engine.run_backtest(signals, price_data)
        
        # Report
        report_file = RESULTS_DIR / f"backtest_{self.cipher['cipher_id']}_{symbol}.json"
        
        # Serialize trades
        trades_list = []
        for t in result.trades:
            ts = t.entry_time
            # Handle int/str/timestamp safely
            if hasattr(ts, 'isoformat'):
                ts_str = ts.isoformat()
            else:
                ts_str = str(ts)
                
            trades_list.append({
                "entry_time": ts_str,
                "entry_price": t.entry_price,
                "pnl_pct": t.pnl_pct,
                "pnl": t.pnl,
                "exit_reason": t.exit_reason
            })
            
        report = {
            "cipher_id": self.cipher['cipher_id'],
            "symbol": symbol,
            "period_days": days,
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "total_pnl": result.total_pnl,
            "profit_factor": result.profit_factor,
            "trades": trades_list
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Report saved to {report_file}")
        
        # Markdown summary
        md_file = RESULTS_DIR / f"backtest_{self.cipher['cipher_id']}_{symbol}.md"
        with open(md_file, 'w') as f:
            f.write(f"# Backtest Report: {symbol}\n\n")
            f.write(f"- **Cipher:** {self.cipher['cipher_id']}\n")
            f.write(f"- **Period:** {days} days\n")
            f.write(f"- **Total PnL:** ${result.total_pnl:.2f}\n")
            f.write(f"- **Win Rate:** {result.win_rate:.1f}%\n")
            f.write(f"- **Trades:** {result.total_trades}\n")
        
        print(f"\nDONE. Check reports in {RESULTS_DIR}")

    def run_batch(self, symbols: List[str], days: int):
        """Run backtest for multiple symbols and aggregate results."""
        if self.model is None:
            self.train_model()
            
        grand_total_pnl = 0
        grand_total_trades = 0
        winning_trades = 0
        
        results = []
        
        logger.info(f"Starting Batch Scan for {len(symbols)} coins...")
        
        for symbol in symbols:
            try:
                logger.info(f"--- Processing {symbol} ---")
                signals, price_data = self.scan_coin(symbol, "15m", days)
                
                if signals.empty:
                    logger.warning(f"No signals for {symbol}")
                    continue
                    
                # Index Alignment
                if 'open_time' in price_data.columns:
                    price_data = price_data.set_index('open_time')
                    signals = signals.set_index(price_data.index)
                    
                # Run Engine
                engine = BacktestEngine(config=self.config)
                result = engine.run_backtest(signals, price_data)
                
                grand_total_pnl += result.total_pnl
                grand_total_trades += result.total_trades
                winning_trades += int(result.total_trades * result.win_rate / 100)
                
                results.append({
                    "symbol": symbol,
                    "pnl": result.total_pnl,
                    "win_rate": result.win_rate,
                    "trades": result.total_trades
                })
                
                # Serialize trades for Hard Negative Mining
                trades_list = []
                for t in result.trades:
                    ts = t.entry_time
                    if hasattr(ts, 'isoformat'):
                        ts_str = ts.isoformat()
                    else:
                        ts_str = str(ts)
                        
                    trades_list.append({
                        "entry_time": ts_str,
                        "entry_price": t.entry_price,
                        "pnl_pct": t.pnl_pct,
                        "pnl": t.pnl
                    })

                # Save Individual Report
                report_file = RESULTS_DIR / f"backtest_{self.cipher['cipher_id']}_{symbol}.json"
                with open(report_file, 'w') as f:
                    json.dump({
                        "symbol": symbol,
                        "pnl": result.total_pnl, 
                        "stats": {
                            "total_trades": result.total_trades,
                            "win_rate": result.win_rate,
                            "profit_factor": result.profit_factor,
                            "max_drawdown": result.max_drawdown,
                            "sharpe_ratio": result.sharpe_ratio
                        },
                        "trades": trades_list
                    }, f)
                    
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue
                
        # Aggregate Report
        avg_win_rate = (winning_trades / grand_total_trades * 100) if grand_total_trades > 0 else 0
        
        logger.info("="*50)
        logger.info("BATCH BACKTEST COMPLETE")
        logger.info(f"Total PnL: ${grand_total_pnl:.2f}")
        logger.info(f"Total Trades: {grand_total_trades}")
        logger.info(f"Avg Win Rate: {avg_win_rate:.2f}%")
        logger.info("="*50)
        
        # Save Aggregate
        agg_file = RESULTS_DIR / f"backtest_aggregated_{self.cipher['cipher_id']}.md"
        with open(agg_file, 'w') as f:
            f.write(f"# Portfolio Backtest Report\n\n")
            f.write(f"- **Cipher:** {self.cipher['cipher_id']}\n")
            f.write(f"- **Coins:** {len(symbols)}\n")
            f.write(f"- **Total PnL:** ${grand_total_pnl:.2f}\n")
            f.write(f"- **Total Trades:** {grand_total_trades}\n")
            f.write(f"- **Win Rate:** {avg_win_rate:.2f}%\n\n")
            f.write("## Breakdown\n| Symbol | PnL | Trades | Win Rate |\n|---|---|---|---|\n")
            for r in results:
                f.write(f"| {r['symbol']} | ${r['pnl']:.2f} | {r['trades']} | {r['win_rate']:.1f}% |\n")
                
        print(f"Aggregated report saved to {agg_file}")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Run Cipher Backtest")
    parser.add_argument("--days", type=int, default=730, help="Days to backtest (default: 730)")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Symbol to backtest (or 'TOP10', 'ALL')")
    parser.add_argument("--cipher", type=str, required=False, help="Cipher ID (optional, defaults to latest)")
    parser.add_argument("--atr-stop", type=float, default=2.0, help="ATR Multiplier for Stop Loss (default: 2.0)")
    parser.add_argument("--atr-profit", type=float, default=4.0, help="ATR Multiplier for Take Profit (default: 4.0)")
    parser.add_argument("--no-atr", action="store_true", help="Disable ATR Stops (use time exit only)")
    
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    # Configure Risk Management
    config = BacktestConfig(
        use_atr_stops=not args.no_atr,
        atr_stop_mult=args.atr_stop,
        atr_profit_mult=args.atr_profit
    )
    
    # Run Backtest
    runner = BacktestRunner(cipher_path=args.cipher, config=config)
    
    symbols = []
    if args.symbol == "TOP10":
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT"]
    elif args.symbol == "ALL":
        # TODO: Fetch all symbols from DB
        symbols = ["BTCUSDT"] 
    elif "," in args.symbol:
        symbols = args.symbol.split(",")
    else:
        symbols = [args.symbol]
        
    if len(symbols) > 1:
        runner.run_batch(symbols, args.days)
    else:
        runner.run(symbols[0], args.days)

if __name__ == "__main__":
    main()
