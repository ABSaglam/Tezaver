#!/usr/bin/env python3
"""
🎯 RALLI_ASM_15M v3 — 7 State Machine

PHILOSOPHY: "Geç kal ama yanlış girme."
Early entries are forbidden. Late is acceptable, false is NOT.

STATE FLOW:
IDLE → AWAKENING → CANDIDATE → CONFIRMED → COMMITTED (BUY) → EXTENSION → EXHAUSTED (SELL) → IDLE

HARD RULES:
- COMMITTED must be reached THROUGH CONFIRMED
- Direct AWAKENING → COMMITTED is FORBIDDEN
- Multiple COMMITTED signals in same session are NOT allowed
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from enum import Enum

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

class State(Enum):
    IDLE = "IDLE"
    AWAKENING = "AWAKENING"
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    COMMITTED = "COMMITTED"
    EXTENSION = "EXTENSION"
    EXHAUSTED = "EXHAUSTED"

class RalliASM15M_v3:
    """
    7-State Behavioral State Machine
    """
    
    def __init__(self, df, verbose=True):
        self.df = df.copy()
        self.state = State.IDLE
        self.entry_price = None
        self.entry_idx = None
        self.state_duration = 0
        self.trades = []
        self.logs = []
        self.verbose = verbose
        
        # Tracking for CONFIRMED -> COMMITTED
        self.local_high = None
        self.local_low = None
        self.pullback_detected = False
        self.ema_reclaimed = False
        
        # Session control
        self.committed_this_session = False
        
        self._calculate_indicators()
    
    def _log(self, msg):
        if self.verbose:
            print(msg)
        self.logs.append(msg)
    
    def _calculate_indicators(self):
        df = self.df
        
        # EMAs
        df['ema9'] = df['close'].ewm(span=9).mean()
        df['ema21'] = df['close'].ewm(span=21).mean()
        df['ema50'] = df['close'].ewm(span=50).mean()
        
        # ATR
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(14).mean()
        df['atr_ma'] = df['atr'].rolling(50).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # RSI Slope (momentum direction)
        df['rsi_slope'] = df['rsi'].diff(3)
        
        # Volume
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma']
        
        # Candle info
        df['is_green'] = df['close'] > df['open']
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        
        # Rolling high/low for structure
        df['high_3'] = df['high'].rolling(3).max()
        df['low_3'] = df['low'].rolling(3).min()
        
        self.df = df
    
    def _is_awakening(self, idx):
        """
        AWAKENING: First signs of expansion (range or volume)
        - ATR expanding OR volume spike
        - No directional bias required yet
        """
        if idx < 5:
            return False
        row = self.df.iloc[idx]
        prev = self.df.iloc[idx-3]
        
        # Range expansion
        range_expanding = row['atr'] > prev['atr'] * 1.1
        
        # Volume spike
        volume_spike = row['vol_ratio'] > 1.3
        
        return range_expanding or volume_spike
    
    def _is_candidate(self, idx):
        """
        CANDIDATE: Structure aligns upward, momentum exists
        - EMA9 > EMA21
        - RSI > 50 and rising
        - NOT proof of persistence yet
        """
        if idx < 5:
            return False
        row = self.df.iloc[idx]
        
        # Structure alignment
        ema_aligned = row['ema9'] > row['ema21']
        
        # Momentum exists
        rsi_bullish = row['rsi'] > 50 and row['rsi_slope'] > 0
        
        # Above EMA21
        above_ema21 = row['close'] > row['ema21']
        
        return ema_aligned and rsi_bullish and above_ema21
    
    def _is_confirmed(self, idx):
        """
        CONFIRMED: Same directional bias for N consecutive candles (N >= 3)
        - Pullbacks occur but DO NOT break previous local low
        - Momentum returns quickly
        """
        if idx < 8:
            return False
        
        row = self.df.iloc[idx]
        last_3 = self.df.iloc[idx-2:idx+1]
        last_5 = self.df.iloc[idx-4:idx+1]
        
        # All last 3 candles above EMA21
        all_above_ema21 = (last_3['close'] > last_3['ema21']).all()
        
        # At least 2 of last 3 are green (momentum preserved)
        green_count = last_3['is_green'].sum()
        momentum_preserved = green_count >= 2
        
        # Current low > lowest low of last 5 (structure not broken)
        current_low = row['low']
        recent_low = last_5['low'].min()
        structure_intact = current_low >= recent_low * 0.99  # 1% tolerance
        
        # RSI still bullish
        rsi_ok = row['rsi'] > 50
        
        return all_above_ema21 and momentum_preserved and structure_intact and rsi_ok
    
    def _is_committed(self, idx):
        """
        COMMITTED: Market shows "insistence"
        - Price reclaims short EMA after pullback
        - Previous high is challenged or broken
        """
        if idx < 10:
            return False
        
        row = self.df.iloc[idx]
        prev_row = self.df.iloc[idx-1]
        last_5 = self.df.iloc[idx-4:idx+1]
        
        # 1. Price is above EMA9 now
        above_ema9 = row['close'] > row['ema9']
        
        # 2. Was below EMA9 recently (within last 5 candles) - pullback happened
        was_below_ema9 = (last_5['close'] < last_5['ema9']).any()
        
        # 3. EMA reclaim: current close above EMA9, previous was below or at EMA9
        ema_reclaim = above_ema9 and (prev_row['close'] <= prev_row['ema9'] * 1.002)
        
        # 4. Previous local high challenged: current high >= max high of last 5
        previous_high = last_5['high'].max()
        high_challenged = row['high'] >= previous_high * 0.995  # 0.5% tolerance
        
        # 5. Full EMA alignment (9 > 21 > 50)
        full_alignment = row['ema9'] > row['ema21'] > row['ema50']
        
        # 6. Volume confirmation
        vol_ok = row['vol_ratio'] > 1.0
        
        # All conditions met = INSISTENCE
        insistence = all([
            above_ema9,
            was_below_ema9,
            high_challenged,
            full_alignment,
            vol_ok
        ])
        
        return insistence
    
    def _is_exhausted(self, idx):
        """
        EXHAUSTED: Rally is over
        - Failed attempt to make new high
        - Momentum divergence OR EMA structure breaks
        """
        if idx < 5:
            return False
        
        row = self.df.iloc[idx]
        prev_row = self.df.iloc[idx-1]
        last_3 = self.df.iloc[idx-2:idx+1]
        
        # 1. EMA9 < EMA21 (structure break)
        ema_break = row['ema9'] < row['ema21']
        
        # 2. Close < EMA21 (lost support)
        below_ema21 = row['close'] < row['ema21']
        
        # 3. Three consecutive red candles
        three_red = (~last_3['is_green']).all()
        
        # 4. RSI divergence (price up but RSI falling)
        rsi_divergence = row['rsi'] < 50 and row['rsi_slope'] < -3
        
        # 5. Lower high (failed to make new high)
        # Compare current high with high 5 candles ago
        if idx >= 5:
            prev_high_5 = self.df.iloc[idx-5]['high']
            lower_high = row['high'] < prev_high_5 and prev_row['high'] < prev_high_5
        else:
            lower_high = False
        
        return ema_break or below_ema21 or three_red or rsi_divergence
    
    def process_candle(self, idx):
        """Process single candle through state machine"""
        row = self.df.iloc[idx]
        ts = row['datetime'] if 'datetime' in row else f"idx:{idx}"
        action = "WAIT"
        reason = ""
        
        prev_state = self.state
        
        # STATE TRANSITIONS
        if self.state == State.IDLE:
            if self._is_awakening(idx):
                self.state = State.AWAKENING
                self.state_duration = 1
                reason = "Range/Volume expansion detected"
        
        elif self.state == State.AWAKENING:
            if self._is_candidate(idx):
                self.state = State.CANDIDATE
                self.state_duration = 1
                reason = "Structure aligned upward, momentum exists"
            elif not self._is_awakening(idx):
                self.state = State.IDLE
                self.state_duration = 0
                reason = "Awakening conditions lost"
            else:
                self.state_duration += 1
        
        elif self.state == State.CANDIDATE:
            if self._is_confirmed(idx):
                self.state = State.CONFIRMED
                self.state_duration = 1
                self.local_high = row['high']
                self.local_low = row['low']
                reason = "Directional bias preserved for 3+ candles"
            elif not self._is_candidate(idx):
                # Regress
                if self._is_awakening(idx):
                    self.state = State.AWAKENING
                else:
                    self.state = State.IDLE
                self.state_duration = 0
                reason = "Candidate conditions lost, regressing"
            else:
                self.state_duration += 1
        
        elif self.state == State.CONFIRMED:
            if self._is_committed(idx) and not self.committed_this_session:
                self.state = State.COMMITTED
                self.state_duration = 1
                self.entry_price = row['close']
                self.entry_idx = idx
                self.committed_this_session = True
                action = "BUY"
                reason = f"INSISTENCE: EMA reclaim after pullback, high challenged. Entry @ {row['close']:.4f}"
            elif not self._is_confirmed(idx):
                # Check if we should regress
                if self._is_candidate(idx):
                    self.state = State.CANDIDATE
                elif self._is_awakening(idx):
                    self.state = State.AWAKENING
                else:
                    self.state = State.IDLE
                self.state_duration = 0
                reason = "Confirmed conditions lost, regressing"
            else:
                self.state_duration += 1
                # Update local high/low
                if row['high'] > self.local_high:
                    self.local_high = row['high']
                if row['low'] < self.local_low:
                    self.local_low = row['low']
        
        elif self.state == State.COMMITTED:
            if self._is_exhausted(idx):
                self.state = State.EXHAUSTED
                action = "SELL"
                pnl = (row['close'] / self.entry_price - 1) * 100
                reason = f"EXHAUSTED: Structure break or momentum loss. Exit @ {row['close']:.4f}, PnL: {pnl:+.2f}%"
                self.trades.append({
                    'entry_time': self.df.iloc[self.entry_idx]['datetime'] if 'datetime' in self.df.columns else self.entry_idx,
                    'exit_time': row['datetime'] if 'datetime' in row else idx,
                    'entry_price': self.entry_price,
                    'exit_price': row['close'],
                    'pnl_pct': pnl,
                    'candles_held': idx - self.entry_idx
                })
                self.entry_price = None
                self.entry_idx = None
            else:
                self.state_duration += 1
                if self.state_duration > 8:
                    self.state = State.EXTENSION
                    reason = "Trend continuing, entering EXTENSION"
        
        elif self.state == State.EXTENSION:
            if self._is_exhausted(idx):
                self.state = State.EXHAUSTED
                action = "SELL"
                pnl = (row['close'] / self.entry_price - 1) * 100
                reason = f"EXHAUSTED in EXTENSION. Exit @ {row['close']:.4f}, PnL: {pnl:+.2f}%"
                self.trades.append({
                    'entry_time': self.df.iloc[self.entry_idx]['datetime'] if 'datetime' in self.df.columns else self.entry_idx,
                    'exit_time': row['datetime'] if 'datetime' in row else idx,
                    'entry_price': self.entry_price,
                    'exit_price': row['close'],
                    'pnl_pct': pnl,
                    'candles_held': idx - self.entry_idx
                })
                self.entry_price = None
                self.entry_idx = None
            else:
                self.state_duration += 1
        
        elif self.state == State.EXHAUSTED:
            self.state = State.IDLE
            self.state_duration = 0
            self.committed_this_session = False  # Reset for next session
            reason = "Returning to IDLE, session reset"
        
        # Log state transition
        if prev_state != self.state or action != "WAIT":
            self._log(f"[{ts}] {prev_state.value} → {self.state.value} | {reason}")
        
        return {
            'state': self.state.value,
            'action': action,
            'price': row['close'],
            'reason': reason
        }
    
    def run_simulation(self, start_idx=100, end_idx=None):
        if end_idx is None:
            end_idx = len(self.df)
        
        results = []
        for idx in range(start_idx, end_idx):
            result = self.process_candle(idx)
            if result['action'] in ['BUY', 'SELL']:
                results.append({
                    'idx': idx,
                    'datetime': self.df.iloc[idx]['datetime'] if 'datetime' in self.df.columns else None,
                    **result
                })
        
        return results

def main():
    symbol = 'ALGOUSDT'
    test_date = '2024-12-02'
    
    print(f"🎯 RALLI_ASM_15M v3 — TEST")
    print(f"Coin: {symbol}")
    print(f"Test Date: {test_date}")
    print("="*70)
    
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    df = pd.read_parquet(path)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # 3 day window around test date
    start = pd.Timestamp(test_date) - timedelta(days=1)
    end = pd.Timestamp(test_date) + timedelta(days=2)
    mask = (df['datetime'] >= start) & (df['datetime'] < end)
    test_df = df[mask].reset_index(drop=True)
    
    print(f"Test Period: {test_df['datetime'].min()} to {test_df['datetime'].max()}")
    print(f"Candles: {len(test_df)}")
    print("\n" + "="*70)
    print("📜 STATE TRANSITION LOG:")
    print("="*70)
    
    asm = RalliASM15M_v3(test_df, verbose=True)
    signals = asm.run_simulation(start_idx=50)
    
    print("\n" + "="*70)
    print("📈 TRADES:")
    print("="*70)
    for trade in asm.trades:
        status = "✅" if trade['pnl_pct'] > 0 else "❌"
        print(f"{status} {trade['entry_time']} -> {trade['exit_time']}")
        print(f"   Entry: {trade['entry_price']:.4f} | Exit: {trade['exit_price']:.4f} | PnL: {trade['pnl_pct']:+.2f}% | Candles: {trade['candles_held']}")
    
    if asm.trades:
        total_pnl = sum(t['pnl_pct'] for t in asm.trades)
        win_rate = sum(1 for t in asm.trades if t['pnl_pct'] > 0) / len(asm.trades) * 100
        print(f"\n📋 SUMMARY:")
        print(f"  Total Trades: {len(asm.trades)}")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Total PnL: {total_pnl:+.2f}%")
    else:
        print("\n⚠️ No trades in test period (as expected if conditions not met)")

if __name__ == "__main__":
    main()
