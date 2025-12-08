"""
Tezaver Sim v1 - Simulation Engine
==================================

Core logic for backtesting rally strategies on historical event data.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any, Optional
from datetime import datetime

from tezaver.core import coin_cell_paths
from tezaver.core.logging_utils import get_logger
from tezaver.snapshots.snapshot_engine import load_features
from tezaver.sim.sim_config import RallySimConfig

logger = get_logger(__name__)

def load_rally_events(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Load rally events for the given symbol and timeframe.
    Supports "15m" (Fast15) and "1h"/"4h" (Time-Labs).
    """
    try:
        if timeframe == "15m":
            path = coin_cell_paths.get_fast15_rallies_path(symbol)
        else:
            path = coin_cell_paths.get_time_labs_rallies_path(symbol, timeframe)
            
        if not path.exists():
            logger.warning(f"Rally events not found: {path}")
            return pd.DataFrame()
            
        df = pd.read_parquet(path)
        
        # Ensure quality fields exist (fill defaults if missing)
        if 'quality_score' not in df.columns:
            df['quality_score'] = 0.0
        if 'rally_shape' not in df.columns:
            df['rally_shape'] = 'unknown'
            
        return df
    except Exception as e:
        logger.error(f"Error loading rally events: {e}")
        return pd.DataFrame()

def load_price_series(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Load OHLCV price series for simulation validation.
    Returns DataFrame with 'timestamp' index and 'open','high','low','close' columns.
    """
    try:
        # Use load_features as standard data loader
        df = load_features(symbol, timeframe)
        
        if df.empty:
            return pd.DataFrame()
            
        # Standardize timestamp
        if 'timestamp' not in df.columns:
            if 'open_time' in df.columns:
                df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
            else:
                df['timestamp'] = pd.to_datetime(df.index)
        elif df['timestamp'].dtype == 'int64':
             df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        else:
             df['timestamp'] = pd.to_datetime(df['timestamp'])
             
        # Set index for easy lookup
        df = df.set_index('timestamp').sort_index()
        
        # Ensure required columns
        req_cols = ['open', 'high', 'low', 'close']
        if not all(c in df.columns for c in req_cols):
            logger.error(f"Missing OHLC columns in price data for {symbol}")
            return pd.DataFrame()
            
        return df[req_cols]
        
    except Exception as e:
        logger.error(f"Error loading price series: {e}")
        return pd.DataFrame()

def filter_events(events: pd.DataFrame, cfg: RallySimConfig) -> pd.DataFrame:
    """
    Filter rally events based on configuration criteria.
    """
    if events.empty:
        return events
        
    df = events.copy()
    
    # Quality Filter
    if cfg.min_quality_score > 0:
        df = df[df['quality_score'] >= cfg.min_quality_score]
        
    # Shape Filter
    if cfg.allowed_shapes:
        df = df[df['rally_shape'].isin(cfg.allowed_shapes)]
        
    # Min Gain Filter (Future looking - cheating? No, checking theoretical quality of signal set)
    # Actually, in a sim, we usually filter by INPUT signals. 
    # 'future_max_gain_pct' is a LABEL. Filtering by label implies "Perfect Foresight" testing?
    # The prompt asked: "Eğer cfg.min_future_max_gain_pct verilmişse: future_max_gain_pct >= val"
    # This allows user to see "How would I perform if I only took the rallies that actually worked?" 
    # useful for analyzing "potential" vs "realized". We will implement as requested.
    if cfg.min_future_max_gain_pct is not None:
        df = df[df['future_max_gain_pct'] >= cfg.min_future_max_gain_pct]
        
    # Context Filters (Trend Soul 4h)
    if cfg.require_trend_soul_4h_gt is not None:
        if 'trend_soul_4h' in df.columns:
            df = df[df['trend_soul_4h'] > cfg.require_trend_soul_4h_gt]
            
    # Context Filters (RSI 1d)
    if cfg.require_rsi_1d_gt is not None:
        if 'rsi_1d' in df.columns:
            df = df[df['rsi_1d'] > cfg.require_rsi_1d_gt]
            
    return df

def simulate_trades(events: pd.DataFrame, prices: pd.DataFrame, cfg: RallySimConfig) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run trade simulation.
    
    Returns:
        trades_df: List of executed trades
        equity_df: Equity curve over time
    """
    if events.empty or prices.empty:
        return pd.DataFrame(), pd.DataFrame()
        
    trades = []
    equity = cfg.initial_equity
    equity_history = [{'timestamp': prices.index[0], 'equity': equity}]
    
    # Sort events by time
    events = events.sort_values('event_time')
    
    for _, event in events.iterrows():
        entry_time = pd.to_datetime(event['event_time'])
        
        # Check if we have price data at entry
        if entry_time not in prices.index:
            continue
            
        entry_price = float(prices.loc[entry_time, 'close'])
        
        # Determine TP/SL levels
        # Long trade only
        tp_price = entry_price * (1 + cfg.tp_pct)
        sl_price = entry_price * (1 - cfg.sl_pct)
        
        # Walk forward
        # Get price slice after entry
        future_prices = prices.loc[entry_time:].iloc[1 : cfg.max_horizon_bars + 1]
        
        exit_reason = "TIMEOUT"
        exit_time = future_prices.index[-1] if not future_prices.empty else entry_time
        exit_price = float(future_prices.iloc[-1]['close']) if not future_prices.empty else entry_price
        
        for ts, bar in future_prices.iterrows():
            low = float(bar['low'])
            high = float(bar['high'])
            close = float(bar['close'])
            
            # Check SL first (conservative)
            if low <= sl_price:
                exit_reason = "SL"
                exit_price = sl_price # Execute at SL level
                exit_time = ts
                break
            
            # Check TP
            if high >= tp_price:
                exit_reason = "TP"
                exit_price = tp_price # Execute at TP level
                exit_time = ts
                break
                
        # Calculate Result
        gross_return_pct = (exit_price - entry_price) / entry_price
        
        # Calculate PnL
        # Position sizing: risk_per_trade_pct of CURRENT equity
        # Risk amount = equity * risk_pct
        # Position size = Risk amount / (Entry - SL) * Entry  <-- Classic sizing
        # OR simple sizing: allocate X% of equity to trade? 
        # Prompt says: "risk_per_trade_pct kadar pozisyon büyüklüğü" (position size = risk_per_trade_pct)?
        # Usually "Risk X%" means "Risk losing X% of account".
        # But "risk_per_trade_pct kadar pozisyon büyüklüğü" implies Position Size = Equity * risk_pct.
        # This is strictly "Allocation %" not "Risk %".
        # Given "tp_pct" and "sl_pct" are fixed, Risk% would be Allocation * sl_pct.
        # Let's assume user means Allocation Size = Equity * risk_per_trade_pct because sim config calls it "risk_per_trade_pct" but usually that implies risk.
        # Let's interpret strictly as "Allocation". If I put 100% of equity into a trade, and SL is 2%, I lose 2%.
        # If I put 1% of equity (Position Size), and SL is 2%, I lose 0.02%. That's very conservative.
        # Most likely "Risk Per Trade" means "Amount I am willing to lose".
        # So Position Size = (Equity * Risk_Per_Trade) / SL_Pct.
        # e.g. Equity 10000, Risk 1% (100$), SL 2%. Position = 100 / 0.02 = 5000$.
        # Let's use this standard Risk-Based Sizing.
        
        risk_amount = equity * cfg.risk_per_trade_pct
        if cfg.sl_pct > 0:
            position_size = risk_amount / cfg.sl_pct
        else:
            position_size = equity # Fallback if SL is 0? Unlikely.
            
        # Cap position size at current equity? (No margin)
        position_size = min(position_size, equity) 
        
        pnl = position_size * gross_return_pct
        equity += pnl
        
        # Record trade
        trades.append({
            'symbol': cfg.symbol,
            'event_time': entry_time,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'gross_return_pct': gross_return_pct,
            'pnl': pnl,
            'exit_reason': exit_reason,
            'event_tf': event.get('event_tf', cfg.timeframe),
            'rally_shape': event.get('rally_shape', 'unk'),
            'quality_score': event.get('quality_score', 0),
            'rally_bucket': event.get('rally_bucket', 'unk'),
            'equity_after': equity
        })
        
        # Update equity history
        equity_history.append({'timestamp': exit_time, 'equity': equity})
        
    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_history)
    
    # Resample equity curve to ensure smooth chart? 
    # For now event-based is fine.
    
    return trades_df, equity_df

def summarize_results(
    trades_df: pd.DataFrame, 
    equity_df: pd.DataFrame,
    preset_id: Optional[str] = None,
    customized_from: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate summary metrics from simulation results.
    """
    base_results = {
        "preset_id": preset_id,
        "customized_from": customized_from
    }

    if trades_df.empty:
        return {
            **base_results,
            "num_trades": 0,
            "win_rate": 0.0,
            "avg_gain_pct": 0.0,
            "avg_loss_pct": 0.0,
            "expectancy_R": 0.0,
            "max_drawdown_pct": 0.0,
            "final_equity": equity_df.iloc[-1]['equity'] if not equity_df.empty else 0.0,
            "total_pnl_pct": 0.0
        }
        
    num_trades = len(trades_df)
    wins = trades_df[trades_df['pnl'] > 0]
    losses = trades_df[trades_df['pnl'] <= 0]
    
    win_rate = len(wins) / num_trades
    
    avg_gain = wins['gross_return_pct'].mean() if not wins.empty else 0.0
    avg_loss = losses['gross_return_pct'].mean() if not losses.empty else 0.0
    
    # Expectancy (WinRate * AvgWin) - (LossRate * AvgLoss) -> Simple Return Expectancy
    loss_rate = 1.0 - win_rate
    # AvgLoss comes as negative usually, so we add. 
    # But if avg_loss is e.g. -0.02.
    expectancy = (win_rate * avg_gain) + (loss_rate * avg_loss)
    
    # Max Drawdown
    if not equity_df.empty:
        eq_curve = equity_df['equity']
        running_max = eq_curve.cummax()
        drawdown = (eq_curve - running_max) / running_max
        max_dd = drawdown.min() # Negative value
    else:
        max_dd = 0.0
        
    final_equity = equity_df.iloc[-1]['equity']
    
    return {
        **base_results,
        "num_trades": num_trades,
        "win_rate": win_rate,
        "avg_gain_pct": avg_gain,
        "avg_loss_pct": avg_loss,
        "expectancy_R": expectancy, # Strictly this is expectancy per trade in % term
        "max_drawdown_pct": max_dd,
        "final_equity": final_equity,
        "total_pnl_pct": (final_equity - equity_df.iloc[0]['equity']) / equity_df.iloc[0]['equity']
    }
