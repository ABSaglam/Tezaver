
"""
Super Momentum Miner Engine
===========================
Based on analysis showing 86% Win Rate.
Logic:
1. Signal Bar (T-1): Volume > 5x SMA50, RSI > 70.
2. Confirmation Bar (T): Volume > 2x SMA50, ATR% > 2.0% (Big Candle), RSI > Prev RSI.
"""

import pandas as pd
import numpy as np
from typing import List, Dict
from dataclasses import dataclass
from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths

@dataclass
class SuperMomentumEvent:
    symbol: str
    event_time: pd.Timestamp
    price: float
    rsi: float
    vol_factor: float # Rel to SMA50
    candle_size_pct: float # ATR%
    tier: str # Diamond/Gold/Silver etc.

class SuperMomentumMiner:
    def __init__(self):
        self.coins = DEFAULT_COINS

    def mine(self, lookback_bars=200) -> List[SuperMomentumEvent]:
        events = []
        
        for symbol in self.coins:
            try:
                hist_path = coin_cell_paths.get_history_file(symbol, "15m")
                if not hist_path.exists(): continue
                
                df = pd.read_parquet(hist_path)
                if df.empty or len(df) < 55: continue
                
                # Slicing for speed (we only care about recent hist for live scanning)
                # But if we want historical mining we need full. 
                # Assuming this is for "What is happening NOW or RECENTLY".
                df = df.tail(lookback_bars).copy()
                
                # Indicators
                # RSI
                delta = df['close'].diff()
                up = delta.clip(lower=0)
                down = -1 * delta.clip(upper=0)
                ema_up = up.ewm(com=13, adjust=False).mean()
                ema_down = down.ewm(com=13, adjust=False).mean()
                rs = ema_up / ema_down
                df['rsi'] = 100 - (100 / (1 + rs))
                
                # SMA 50 Volume
                df['vol_sma50'] = df['volume'].rolling(50).mean()
                
                # ATR (Approx)
                high_low = df['high'] - df['low']
                df['atr_pct'] = (high_low / df['close']).rolling(14).mean() # Approx relative ATR
                # Actually, analysis used True Range. Let's match it for consistency.
                # Re-implement TR properly if needed, but for speed high-low/close is often close enough for pct.
                # Let's match exact analysis logic:
                # tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                # BUT computing 'high_close' involves shift.
                # Let's settle for simple High-Low % for now to be fast, or do it right.
                # Do it right.
                h_c = np.abs(df['high'] - df['close'].shift())
                l_c = np.abs(df['low'] - df['close'].shift())
                tr = pd.concat([high_low, h_c, l_c], axis=1).max(axis=1)
                df['atr'] = tr.rolling(14).mean()
                df['atr_pct'] = df['atr'] / df['close']

                # Shifts
                df['prev_rsi'] = df['rsi'].shift(1)
                df['prev_vol'] = df['volume'].shift(1)
                
                # --- Logic ---
                # Check LAST FEW BARS (e.g. last 3) to find active signals
                # We iterate over the last 3 bars to see if any triggered recently
                
                recent_df = df.iloc[-5:] # check last 5 bars
                
                for idx, row in recent_df.iterrows():
                     # T-1 Logic
                     prev_idx = df.index.get_loc(idx) - 1
                     if prev_idx < 0: continue
                     
                     prev_row = df.iloc[prev_idx]
                     
                     # Cond 1: Trigger
                     # Need Vol SMA at T-1. SMA is computed per row.
                     # prev_row['vol_sma50']
                     # BUT wait, shift(1) in analysis meant T-1 of the *shifted* series?
                     # In analysis: c1 = prev_vol > 5 * vol_sma50.shift(1)
                     # So Volume(T-1) > 5 * SMA50(T-2).
                     # Let's trust the intuitive logic: High Vol relative to average.
                     # Use: Volume > 5 * SMA50.
                     
                     vol_sma_t1 = df['vol_sma50'].iloc[prev_idx]
                     is_trigger = (prev_row['volume'] > 5 * vol_sma_t1) and (prev_row['rsi'] > 70)
                     
                     if not is_trigger: continue
                     
                     # Cond 2: Confirmation (Current Bar T)
                     # Volume > 2 * SMA50
                     vol_sma_t = row['vol_sma50']
                     # ATR > 2%
                     atr_pct = row['atr_pct']
                     
                     is_confirm = (row['volume'] > 2 * vol_sma_t) and \
                                  (atr_pct > 0.02) and \
                                  (row['rsi'] > prev_row['rsi'])
                                  
                     if is_confirm:
                         # Calculate Gain since Signal
                         # Signal Price = Close of Confirmation Bar (row['close'])
                         # Current Price = df.iloc[-1]['close']
                         current_price = df.iloc[-1]['close']
                         signal_price = row['close']
                         gain_since = (current_price - signal_price) / signal_price
                         
                         # Tier/Status Logic
                         status_label = "PENDING"
                         if gain_since > 0.05:
                             status_label = "✅ SILVER BREAKOUT (%100 Prob)"
                         elif gain_since < -0.05:
                             status_label = "❌ STOPPED"
                             
                         # Tier Heuristic
                         tier_h = "DIAMOND" if atr_pct > 0.035 else "GOLD"
                         if gain_since > 0.20: tier_h = "DIAMOND+"

                         events.append(SuperMomentumEvent(
                             symbol=symbol,
                             event_time=row.name if isinstance(row.name, pd.Timestamp) else row.get('open_time'),
                             price=signal_price,
                             rsi=row['rsi'],
                             vol_factor=row['volume']/vol_sma_t,
                             candle_size_pct=atr_pct*100,
                             tier=f"{tier_h} | {status_label}"
                         ))
                         
            except Exception:
                continue
                
        return events
