"""
Daily 30% Target Simulator
==========================

Simulates an aggressive daily 30% profit target strategy across all available coins.

Usage:
    python src/tezaver/simulation/daily_30_simulator.py --coins 100 --days 365
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

# Setup path
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tezaver.core.config import DEFAULT_COINS
from tezaver.data.history_service import load_existing_history
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class TradeResult:
    """Result of a single trade."""
    date: str
    symbol: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    outcome: str  # 'TP', 'SL', 'TRAILING', 'EOD'
    holding_bars: int


@dataclass
class SimulationConfig:
    """Configuration for the simulation."""
    daily_target_pct: float = 0.30  # 30%
    stop_loss_pct: float = -0.10    # -10%
    trailing_trigger_pct: float = 0.15  # Activate trailing at 15%
    trailing_stop_pct: float = 0.05    # Lock in 5% below peak
    initial_capital: float = 1000.0
    timeframe: str = "15m"
    bars_per_day: int = 96  # 15m bars in a day


@dataclass
class SimulationResult:
    """Final result of the simulation."""
    total_days: int = 0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    initial_capital: float = 1000.0
    final_capital: float = 1000.0
    max_drawdown_pct: float = 0.0
    best_day_pct: float = 0.0
    worst_day_pct: float = 0.0
    trades: List[TradeResult] = field(default_factory=list)
    daily_equity: List[Tuple[str, float]] = field(default_factory=list)


def detect_rally_signal(df: pd.DataFrame, bar_idx: int) -> float:
    """
    Simple rally signal detector based on volume spike and momentum.
    Returns a score between 0 and 1 (higher = stronger signal).
    """
    if bar_idx < 20:
        return 0.0
    
    window = df.iloc[bar_idx-20:bar_idx]
    current = df.iloc[bar_idx]
    
    # Volume spike check
    avg_volume = window['volume'].mean()
    current_volume = current['volume']
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
    
    # Price momentum (last 5 bars)
    momentum_window = df.iloc[bar_idx-5:bar_idx+1]
    price_change = (momentum_window['close'].iloc[-1] - momentum_window['close'].iloc[0]) / momentum_window['close'].iloc[0]
    
    # Combine into score
    if volume_ratio > 2.0 and price_change > 0.01:  # Volume 2x + positive momentum
        score = min(1.0, (volume_ratio - 2.0) / 3.0 + price_change * 10)
        return score
    
    return 0.0


def simulate_trade(df: pd.DataFrame, entry_idx: int, config: SimulationConfig) -> Optional[TradeResult]:
    """
    Simulate a single trade from entry point.
    Returns TradeResult or None if trade couldn't be executed.
    """
    if entry_idx >= len(df) - 1:
        return None
    
    entry_bar = df.iloc[entry_idx]
    entry_price = entry_bar['close']
    entry_date = entry_bar['datetime'].strftime('%Y-%m-%d %H:%M') if pd.notna(entry_bar['datetime']) else str(entry_idx)
    
    max_price_seen = entry_price
    trailing_active = False
    trailing_stop_price = 0.0
    
    # Look ahead up to 1 day (96 bars for 15m)
    max_lookahead = min(config.bars_per_day, len(df) - entry_idx - 1)
    
    for i in range(1, max_lookahead + 1):
        current_bar = df.iloc[entry_idx + i]
        high = current_bar['high']
        low = current_bar['low']
        close = current_bar['close']
        
        # Update max price
        if high > max_price_seen:
            max_price_seen = high
        
        # Check Take Profit
        pnl_at_high = (high - entry_price) / entry_price
        if pnl_at_high >= config.daily_target_pct:
            exit_price = entry_price * (1 + config.daily_target_pct)
            return TradeResult(
                date=entry_date,
                symbol="",
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_pct=config.daily_target_pct,
                outcome='TP',
                holding_bars=i
            )
        
        # Check Stop Loss
        pnl_at_low = (low - entry_price) / entry_price
        if pnl_at_low <= config.stop_loss_pct:
            exit_price = entry_price * (1 + config.stop_loss_pct)
            return TradeResult(
                date=entry_date,
                symbol="",
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_pct=config.stop_loss_pct,
                outcome='SL',
                holding_bars=i
            )
        
        # Trailing Stop Logic
        current_gain = (max_price_seen - entry_price) / entry_price
        if current_gain >= config.trailing_trigger_pct:
            trailing_active = True
            trailing_stop_price = max_price_seen * (1 - config.trailing_stop_pct)
        
        if trailing_active and low <= trailing_stop_price:
            exit_price = trailing_stop_price
            pnl = (exit_price - entry_price) / entry_price
            return TradeResult(
                date=entry_date,
                symbol="",
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_pct=pnl,
                outcome='TRAILING',
                holding_bars=i
            )
    
    # End of day exit
    final_bar = df.iloc[entry_idx + max_lookahead]
    exit_price = final_bar['close']
    pnl = (exit_price - entry_price) / entry_price
    
    return TradeResult(
        date=entry_date,
        symbol="",
        entry_price=entry_price,
        exit_price=exit_price,
        pnl_pct=pnl,
        outcome='EOD',
        holding_bars=max_lookahead
    )


def run_daily_simulation(
    coins: List[str],
    config: SimulationConfig,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> SimulationResult:
    """
    Run the daily 30% target simulation across all coins.
    """
    result = SimulationResult(initial_capital=config.initial_capital, final_capital=config.initial_capital)
    capital = config.initial_capital
    peak_capital = capital
    
    # Load all coin data
    logger.info(f"Loading data for {len(coins)} coins...")
    coin_data: Dict[str, pd.DataFrame] = {}
    
    for symbol in coins:
        df = load_existing_history(symbol, config.timeframe)
        if df is not None and not df.empty:
            if 'datetime' not in df.columns:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            coin_data[symbol] = df
    
    if not coin_data:
        logger.error("No coin data loaded!")
        return result
    
    logger.info(f"Loaded data for {len(coin_data)} coins.")
    
    # Determine date range
    all_dates = set()
    for symbol, df in coin_data.items():
        dates = df['datetime'].dt.date.unique()
        all_dates.update(dates)
    
    trading_days = sorted(all_dates)
    
    if start_date:
        trading_days = [d for d in trading_days if d >= start_date.date()]
    if end_date:
        trading_days = [d for d in trading_days if d <= end_date.date()]
    
    logger.info(f"Simulating {len(trading_days)} trading days from {trading_days[0]} to {trading_days[-1]}...")
    
    # Daily simulation loop
    for day_idx, current_date in enumerate(trading_days):
        if day_idx % 100 == 0:
            logger.info(f"Progress: Day {day_idx}/{len(trading_days)} | Capital: ${capital:.2f}")
        
        # Find best signal across all coins for today
        best_signal = 0.0
        best_symbol = None
        best_entry_idx = None
        best_df = None
        
        for symbol, df in coin_data.items():
            day_mask = df['datetime'].dt.date == current_date
            day_df = df[day_mask]
            
            if len(day_df) < 20:
                continue
            
            # Check first few hours for entry (first 24 bars = 6 hours for 15m)
            day_start_idx = df.index[day_mask].min()
            
            for offset in range(min(24, len(day_df))):
                bar_idx = day_start_idx + offset
                if bar_idx >= len(df):
                    continue
                    
                signal = detect_rally_signal(df, bar_idx)
                if signal > best_signal:
                    best_signal = signal
                    best_symbol = symbol
                    best_entry_idx = bar_idx
                    best_df = df
        
        # Execute trade if we have a signal
        if best_signal > 0.3 and best_df is not None:  # Minimum signal threshold
            trade = simulate_trade(best_df, best_entry_idx, config)
            
            if trade:
                trade.symbol = best_symbol
                result.trades.append(trade)
                result.total_trades += 1
                
                # Update capital
                pnl_amount = capital * trade.pnl_pct
                capital += pnl_amount
                
                if trade.pnl_pct > 0:
                    result.wins += 1
                else:
                    result.losses += 1
                
                # Track best/worst day
                if trade.pnl_pct > result.best_day_pct:
                    result.best_day_pct = trade.pnl_pct
                if trade.pnl_pct < result.worst_day_pct:
                    result.worst_day_pct = trade.pnl_pct
        
        # Update equity tracking
        result.daily_equity.append((str(current_date), capital))
        
        # Update peak and drawdown
        if capital > peak_capital:
            peak_capital = capital
        
        current_drawdown = (peak_capital - capital) / peak_capital if peak_capital > 0 else 0
        if current_drawdown > result.max_drawdown_pct:
            result.max_drawdown_pct = current_drawdown
    
    # Finalize result
    result.total_days = len(trading_days)
    result.final_capital = capital
    result.win_rate = result.wins / result.total_trades if result.total_trades > 0 else 0.0
    
    return result


def print_report(result: SimulationResult, config: SimulationConfig):
    """Print a formatted simulation report."""
    print("\n" + "=" * 60)
    print("  %30 GÜNLÜK HEDEF SİMÜLASYONU - SONUÇ RAPORU")
    print("=" * 60)
    
    print(f"\n📊 GENEL İSTATİSTİKLER:")
    print(f"   Toplam Gün: {result.total_days}")
    print(f"   Toplam İşlem: {result.total_trades}")
    print(f"   Kazanan: {result.wins} | Kaybeden: {result.losses}")
    print(f"   Kazanma Oranı: {result.win_rate*100:.1f}%")
    
    print(f"\n💰 SERMAYE PERFORMANSI:")
    print(f"   Başlangıç: ${result.initial_capital:,.2f}")
    print(f"   Final: ${result.final_capital:,.2f}")
    total_return = (result.final_capital - result.initial_capital) / result.initial_capital * 100
    print(f"   Toplam Getiri: {total_return:+.1f}%")
    print(f"   Max Drawdown: {result.max_drawdown_pct*100:.1f}%")
    
    print(f"\n📈 GÜNLÜK PERFORMANS:")
    print(f"   En İyi Gün: {result.best_day_pct*100:+.1f}%")
    print(f"   En Kötü Gün: {result.worst_day_pct*100:+.1f}%")
    
    print(f"\n⚙️ PARAMETRELER:")
    print(f"   Hedef TP: {config.daily_target_pct*100:.0f}%")
    print(f"   Stop Loss: {config.stop_loss_pct*100:.0f}%")
    print(f"   Trailing: {config.trailing_trigger_pct*100:.0f}% tetik, {config.trailing_stop_pct*100:.0f}% stop")
    
    print("\n" + "=" * 60)
    
    # Outcome breakdown
    if result.trades:
        outcomes = {}
        for t in result.trades:
            outcomes[t.outcome] = outcomes.get(t.outcome, 0) + 1
        
        print("\n🎯 ÇIKIŞ TİPLERİ:")
        for outcome, count in sorted(outcomes.items(), key=lambda x: -x[1]):
            pct = count / result.total_trades * 100
            print(f"   {outcome}: {count} ({pct:.1f}%)")
    
    print("\n" + "=" * 60)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Daily 30% Target Simulator")
    parser.add_argument("--coins", type=int, default=100, help="Number of coins to use (default: 100)")
    parser.add_argument("--days", type=int, default=365, help="Lookback days (default: 365)")
    parser.add_argument("--target", type=float, default=0.30, help="Daily target % (default: 0.30)")
    parser.add_argument("--sl", type=float, default=0.10, help="Stop loss % (default: 0.10)")
    parser.add_argument("--capital", type=float, default=1000, help="Initial capital (default: 1000)")
    args = parser.parse_args()
    
    # Setup config
    config = SimulationConfig(
        daily_target_pct=args.target,
        stop_loss_pct=-abs(args.sl),
        initial_capital=args.capital
    )
    
    # Select coins
    coins = DEFAULT_COINS[:args.coins]
    
    # Date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=args.days)
    
    logger.info(f"Starting simulation: {len(coins)} coins, {args.days} days, target {args.target*100}%")
    
    # Run simulation
    result = run_daily_simulation(coins, config, start_date, end_date)
    
    # Print report
    print_report(result, config)
    
    # Save results
    output_path = project_root / "data" / "simulation_results"
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save trades to CSV
    if result.trades:
        trades_df = pd.DataFrame([
            {
                'date': t.date,
                'symbol': t.symbol,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'pnl_pct': t.pnl_pct,
                'outcome': t.outcome,
                'holding_bars': t.holding_bars
            }
            for t in result.trades
        ])
        trades_path = output_path / f"daily30_trades_{timestamp}.csv"
        trades_df.to_csv(trades_path, index=False)
        logger.info(f"Trades saved to: {trades_path}")
    
    # Save equity curve
    if result.daily_equity:
        equity_df = pd.DataFrame(result.daily_equity, columns=['date', 'equity'])
        equity_path = output_path / f"daily30_equity_{timestamp}.csv"
        equity_df.to_csv(equity_path, index=False)
        logger.info(f"Equity curve saved to: {equity_path}")


if __name__ == "__main__":
    main()
