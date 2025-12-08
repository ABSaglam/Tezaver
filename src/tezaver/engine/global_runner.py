"""
Tezaver Global Runner (The World Engine) - M25
==============================================

This module manages the simulation of the entire market (Global Mode).
It:
1. Loads history for multiple coins.
2. Aligns them on a single timeline.
3. Steps through time, ticking the engine for each active coin.
"""

import pandas as pd
from typing import List, Dict, Generator, Any
from datetime import datetime
import streamlit as st # For progress updates if run from UI

from tezaver.engine.unified_engine import UnifiedEngine
from tezaver.data.history_loader import load_single_coin_history

class GlobalSimulationRunner:
    def __init__(self, engine: UnifiedEngine, symbols: List[str], timeframe: str = "1h", window_size: int = 50):
        self.engine = engine
        self.symbols = symbols
        self.timeframe = timeframe
        self.window_size = window_size
        self.data_store: Dict[str, pd.DataFrame] = {}
        self.timeline: pd.DatetimeIndex = None
        
    def load_data(self, limit_bars: int = 1000, progress_callback=None):
        """
        Loads data for all symbols and builds the common timeline.
        """
        all_indices = set()
        loaded_count = 0
        
        for symbol in self.symbols:
            df = load_single_coin_history(symbol, self.timeframe)
            if df is not None and not df.empty:
                # Optimized: Minimal columns
                df = df[['open', 'high', 'low', 'close', 'volume']].sort_index()
                
                # Slice to limit
                if limit_bars:
                    df = df.iloc[-limit_bars:]
                    
                self.data_store[symbol] = df
                for idx in df.index:
                    all_indices.add(idx)
                    
                loaded_count += 1
                if progress_callback:
                    progress_callback(loaded_count / len(self.symbols))
                    
        # Build master timeline
        self.timeline = pd.DatetimeIndex(sorted(list(all_indices)))
        return len(self.timeline)

    def run(self, step_callback=None):
        """
        Executes the simulation loop.
        
        Args:
            step_callback: func(timestamp, portfolio_value, logs) -> should_stop (bool)
        """
        if self.timeline is None or self.timeline.empty:
            return
            
        for i, timestamp in enumerate(self.timeline):
            # Check if lookback window is sufficient from timeline start
            # (In reality we need data BEFORE the simulation start, but for MVP we skip first N bars)
            if i < self.window_size:
                continue
                
            current_prices = {}
            step_logs = []
            
            # For each coin, if it has data at this timestamp
            # NOTE: DataFrame indexing in loop is slow. For 400 coins X 1000 bars = 400k Lookups.
            # Optimization for v2: Pre-align or use numpy arrays.
            # For MVP (mac m1/m2/m3): It should be acceptable for < 20 coins demo. 
            # For 400 coins, we need vectorization or chunking.
            
            for symbol in self.symbols:
                df = self.data_store.get(symbol)
                if df is None: continue
                
                # Check if timestamp exists in this coin's data
                # Using 'asof' or exact match? 'asof' simulates real-time stream better.
                try:
                    # Get window ending at timestamp
                    # slice logic: df.loc[:timestamp].tail(window_size)
                    # This is heavy.
                    # Faster: use integer location if index is aligned. 
                    # But index is ragged (some coins missing bars).
                    
                    # Robust method:
                    if timestamp not in df.index:
                        continue
                        
                    current_prices[symbol] = df.loc[timestamp]['close']
                    
                    # Pass window to engine
                    # Slicing by time is robust but slow-ish
                    window = df.loc[:timestamp].tail(self.window_size)
                    
                    if len(window) < self.window_size:
                        continue
                        
                    result = self.engine.tick(symbol, self.timeframe, window)
                    
                    if result.get("execution"):
                        exe = result["execution"]
                        if exe.success:
                            step_logs.append(f"✅ {symbol} {exe.action} {exe.filled_qty} @ {exe.filled_price}")
                            
                except KeyError:
                    continue
                except Exception as e:
                    print(f"Error {symbol} @ {timestamp}: {e}")
                    
            # Update Callback (UI)
            if step_callback:
                # Estimate portfolio value
                # We need Strategy/Executor to expose value calculation
                # MatrixExecutor has get_portfolio_value_usdt(prices)
                
                val = self.engine.executor.get_portfolio_value_usdt(current_prices)
                stop = step_callback(timestamp, val, step_logs)
                if stop:
                    break
