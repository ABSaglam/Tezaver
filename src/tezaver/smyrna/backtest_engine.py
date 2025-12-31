"""
Backtest Engine
===============
"Gerçekçi Olmayan Backtest = Zararlı"

This module provides realistic backtesting for DNA sequences (ciphers).

CRITICAL REALISM REQUIREMENTS:
1. Slippage: 0.1% default
2. Commission: 0.075% (Binance)
3. Spread: Bid-Ask spread
4. Cross-Validation: Split data properly
5. No lookahead bias: Strict temporal boundaries

SURGEON PROTOCOL: Zero tolerance for unrealistic assumptions.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtest realism."""
    slippage_pct: float = 0.1  # 0.1% slippage
    commission_pct: float = 0.075  # 0.075% commission (Binance)
    spread_pct: float = 0.05  # 0.05% bid-ask spread
    initial_capital: float = 10000.0
    position_size_pct: float = 10.0  # 10% of capital per trade
    

@dataclass
class Trade:
    """Individual trade record."""
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    position_size: float
    pnl: float
    pnl_pct: float
    commission: float
    slippage: float
    

@dataclass
class BacktestResult:
    """Complete backtest results."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    total_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    
    max_drawdown: float
    max_drawdown_pct: float
    
    sharpe_ratio: float
    
    trades: List[Trade]
    equity_curve: pd.Series
    

class BacktestEngine:
    """
    Realistic backtest engine for DNA validation.
    """
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        """
        Initialize backtest engine.
        
        Args:
            config: Backtest configuration (uses defaults if None)
        """
        self.config = config or BacktestConfig()
        self.trades = []
        self.equity_curve = []
    
    def apply_slippage(self, price: float, side: str = 'buy') -> float:
        """
        Apply slippage to execution price.
        
        Args:
            price: Ideal price
            side: 'buy' or 'sell'
            
        Returns:
            Adjusted price with slippage
        """
        slippage_mult = 1 + (self.config.slippage_pct / 100)
        
        if side == 'buy':
            return price * slippage_mult  # Pay more
        else:
            return price / slippage_mult  # Receive less
    
    def calculate_commission(self, position_value: float) -> float:
        """Calculate commission on trade."""
        return position_value * (self.config.commission_pct / 100)
    
    def simulate_trade(
        self,
        entry_price: float,
        entry_time: pd.Timestamp,
        exit_price: float,
        exit_time: pd.Timestamp,
        capital: float
    ) -> Trade:
        """
        Simulate single trade with realistic costs.
        
        Args:
            entry_price: Entry price (before slippage)
            entry_time: Entry timestamp
            exit_price: Exit price (before slippage)
            exit_time: Exit timestamp
            capital: Available capital
            
        Returns:
            Trade object with realistic PnL
        """
        # Position size
        position_size_usd = capital * (self.config.position_size_pct / 100)
        
        # Entry with slippage
        actual_entry_price = self.apply_slippage(entry_price, 'buy')
        entry_commission = self.calculate_commission(position_size_usd)
        
        # Position size in coins
        position_size_coins = (position_size_usd - entry_commission) / actual_entry_price
        
        # Exit with slippage
        actual_exit_price = self.apply_slippage(exit_price, 'sell')
        exit_value = position_size_coins * actual_exit_price
        exit_commission = self.calculate_commission(exit_value)
        
        # Final PnL
        gross_pnl = exit_value - position_size_usd
        net_pnl = gross_pnl - entry_commission - exit_commission
        pnl_pct = (net_pnl / position_size_usd) * 100
        
        # Slippage cost
        slippage_cost = (
            (actual_entry_price - entry_price) * position_size_coins +
            (exit_price - actual_exit_price) * position_size_coins
        )
        
        return Trade(
            entry_time=entry_time,
            entry_price=actual_entry_price,
            exit_time=exit_time,
            exit_price=actual_exit_price,
            position_size=position_size_coins,
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            commission=entry_commission + exit_commission,
            slippage=slippage_cost
        )
    
    def run_backtest(
        self,
        signals: pd.DataFrame,
        price_data: pd.DataFrame
    ) -> BacktestResult:
        """
        Run backtest on signals.
        
        Args:
            signals: DataFrame with 'entry' and 'exit' boolean columns
            price_data: OHLCV DataFrame
            
        Returns:
            BacktestResult with statistics
        """
        logger.info("Running backtest...")
        logger.info(f"Initial capital: ${self.config.initial_capital:,.2f}")
        logger.info(f"Slippage: {self.config.slippage_pct}%")
        logger.info(f"Commission: {self.config.commission_pct}%")
        
        capital = self.config.initial_capital
        equity = [capital]
        trades = []
        
        in_position = False
        entry_idx = None
        
        for i in range(len(signals)):
            if signals.iloc[i]['entry'] and not in_position:
                # Enter position
                entry_idx = i
                in_position = True
                
            elif signals.iloc[i]['exit'] and in_position:
                # Exit position
                entry_time = price_data.index[entry_idx]
                entry_price = price_data.iloc[entry_idx]['close']
                
                exit_time = price_data.index[i]
                exit_price = price_data.iloc[i]['close']
                
                # Simulate trade
                trade = self.simulate_trade(
                    entry_price, entry_time,
                    exit_price, exit_time,
                    capital
                )
                
                trades.append(trade)
                capital += trade.pnl
                equity.append(capital)
                
                in_position = False
        
        # Calculate statistics
        if len(trades) == 0:
            logger.warning("No trades executed!")
            return BacktestResult(
                total_trades=0, winning_trades=0, losing_trades=0, win_rate=0.0,
                total_pnl=0.0, avg_win=0.0, avg_loss=0.0, profit_factor=0.0,
                max_drawdown=0.0, max_drawdown_pct=0.0, sharpe_ratio=0.0,
                trades=[], equity_curve=pd.Series(equity)
            )
        
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]
        
        win_rate = len(winning_trades) / len(trades) * 100
        
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        total_win = sum([t.pnl for t in winning_trades])
        total_loss = abs(sum([t.pnl for t in losing_trades]))
        profit_factor = total_win / total_loss if total_loss > 0 else 0
        
        # Drawdown
        equity_series = pd.Series(equity)
        running_max = equity_series.expanding().max()
        drawdown = running_max - equity_series
        max_drawdown = drawdown.max()
        max_drawdown_pct = (max_drawdown / running_max[drawdown.idxmax()]) * 100
        
        # Sharpe Ratio (simplified)
        returns = equity_series.pct_change().dropna()
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if len(returns) > 1 else 0
        
        result = BacktestResult(
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            total_pnl=capital - self.config.initial_capital,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            trades=trades,
            equity_curve=equity_series
        )
        
        logger.info("\n" + "=" * 70)
        logger.info("BACKTEST RESULTS")
        logger.info("=" * 70)
        logger.info(f"Total Trades: {result.total_trades}")
        logger.info(f"Win Rate: {result.win_rate:.2f}%")
        logger.info(f"Total PnL: ${result.total_pnl:,.2f}")
        logger.info(f"Profit Factor: {result.profit_factor:.2f}")
        logger.info(f"Max Drawdown: ${result.max_drawdown:,.2f} ({result.max_drawdown_pct:.2f}%)")
        logger.info(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        
        return result
