#!/usr/bin/env python3
"""
🎯 RALLI_ASM_15M v3+ — Refined EXHAUSTED Logic

EXIT PRINCIPLE: Exit when rally loses "insistence", NOT when trend collapses.

EXHAUSTED CONDITIONS:
1) LOWER HIGH: High attempt fails to make new high
2) LOSS OF RECOVERY SPEED: Pullback fails to recover within 4-5 candles
3) TIME DECAY: No meaningful new high after 8-10 candles

NO FIXED %, NO TRAILING, NO INDICATOR-ONLY EXIT.
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

class RalliASM15M_v3plus:
    """
    7-State Machine with Refined EXHAUSTED Logic
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
        
        # COMMITTED tracking
        self.committed_this_session = False
        
        # EXHAUSTED tracking
        self.entry_high = None           # High at entry
        self.last_swing_high = None      # Most recent swing high
        self.last_swing_high_idx = None  # Index of last swing high
        self.pullback_start_idx = None   # When pullback started
        self.in_pullback = False         # Currently in pullback?
        self.new_high_made = False       # Has new high been made since entry?
        
        self._calculate_indicators()
    
    def _log(self, msg):
        if self.verbose:
            print(msg)
        self.logs.append(msg)
    
    def _calculate_indicators(self):
        df = self.df
        
        df['ema9'] = df['close'].ewm(span=9).mean()
        df['ema21'] = df['close'].ewm(span=21).mean()
        df['ema50'] = df['close'].ewm(span=50).mean()
        
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(14).mean()
        df['atr_ma'] = df['atr'].rolling(50).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi_slope'] = df['rsi'].diff(3)
        
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma']
        
        df['is_green'] = df['close'] > df['open']
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        
        self.df = df
    
    def _is_awakening(self, idx):
        if idx < 5:
            return False
        row = self.df.iloc[idx]
        prev = self.df.iloc[idx-3]
        range_expanding = row['atr'] > prev['atr'] * 1.1
        volume_spike = row['vol_ratio'] > 1.3
        return range_expanding or volume_spike
    
    def _is_candidate(self, idx):
        if idx < 5:
            return False
        row = self.df.iloc[idx]
        ema_aligned = row['ema9'] > row['ema21']
        rsi_bullish = row['rsi'] > 50 and row['rsi_slope'] > 0
        above_ema21 = row['close'] > row['ema21']
        return ema_aligned and rsi_bullish and above_ema21
    
    def _is_confirmed(self, idx):
        if idx < 8:
            return False
        row = self.df.iloc[idx]
        last_3 = self.df.iloc[idx-2:idx+1]
        last_5 = self.df.iloc[idx-4:idx+1]
        all_above_ema21 = (last_3['close'] > last_3['ema21']).all()
        green_count = last_3['is_green'].sum()
        momentum_preserved = green_count >= 2
        current_low = row['low']
        recent_low = last_5['low'].min()
        structure_intact = current_low >= recent_low * 0.99
        rsi_ok = row['rsi'] > 50
        return all_above_ema21 and momentum_preserved and structure_intact and rsi_ok
    
    def _is_committed(self, idx):
        if idx < 10:
            return False
        row = self.df.iloc[idx]
        prev_row = self.df.iloc[idx-1]
        last_5 = self.df.iloc[idx-4:idx+1]
        
        above_ema9 = row['close'] > row['ema9']
        was_below_ema9 = (last_5['close'] < last_5['ema9']).any()
        previous_high = last_5['high'].max()
        high_challenged = row['high'] >= previous_high * 0.995
        full_alignment = row['ema9'] > row['ema21'] > row['ema50']
        vol_ok = row['vol_ratio'] > 1.0
        
        return all([above_ema9, was_below_ema9, high_challenged, full_alignment, vol_ok])
    
    def _check_exhausted(self, idx):
        """
        REFINED EXHAUSTED LOGIC
        Returns (is_exhausted: bool, reason: str)
        """
        if self.entry_idx is None:
            return False, ""
        
        row = self.df.iloc[idx]
        candles_since_entry = idx - self.entry_idx
        
        # Track swing highs
        if row['high'] > (self.last_swing_high or 0):
            self.last_swing_high = row['high']
            self.last_swing_high_idx = idx
            self.new_high_made = True
            self.in_pullback = False
            self.pullback_start_idx = None
        
        # Detect pullback start (close below EMA9)
        if not self.in_pullback and row['close'] < row['ema9']:
            self.in_pullback = True
            self.pullback_start_idx = idx
        
        # Pullback recovery check
        if self.in_pullback and row['close'] > row['ema9']:
            self.in_pullback = False
            self.pullback_start_idx = None
        
        # ========== CONDITION 1: LOWER HIGH ==========
        # After entry, if we made a new high, then attempted another high but failed
        if self.new_high_made and self.last_swing_high_idx is not None:
            candles_since_last_high = idx - self.last_swing_high_idx
            
            # If 3+ candles since last high and current high is lower
            if candles_since_last_high >= 3:
                # Check if this is a high attempt (green candle with decent range)
                if row['is_green'] and row['range'] > row['atr'] * 0.5:
                    # Is this high lower than last swing high?
                    if row['high'] < self.last_swing_high * 0.998:  # 0.2% tolerance
                        return True, f"LOWER HIGH: Current high {row['high']:.4f} < Last swing high {self.last_swing_high:.4f}"
        
        # ========== CONDITION 2: LOSS OF RECOVERY SPEED ==========
        if self.in_pullback and self.pullback_start_idx is not None:
            pullback_duration = idx - self.pullback_start_idx
            
            # Normal pullback should recover in 2-3 candles
            # If pullback lasts 5+ candles, exit
            if pullback_duration >= 5:
                return True, f"LOSS OF RECOVERY SPEED: Pullback lasted {pullback_duration} candles without recovery"
        
        # ========== CONDITION 3: TIME DECAY ==========
        # After 10 candles, if no meaningful new high (at least 0.5% above entry high)
        if candles_since_entry >= 10:
            current_max_high = self.df.iloc[self.entry_idx:idx+1]['high'].max()
            meaningful_gain = (current_max_high / self.entry_high - 1) * 100
            
            if meaningful_gain < 0.5:  # Less than 0.5% gain in 10 candles
                return True, f"TIME DECAY: {candles_since_entry} candles, only {meaningful_gain:.2f}% gain"
        
        return False, ""
    
    def process_candle(self, idx):
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
                reason = "Structure aligned upward"
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
                reason = "Directional bias preserved"
            elif not self._is_candidate(idx):
                if self._is_awakening(idx):
                    self.state = State.AWAKENING
                else:
                    self.state = State.IDLE
                self.state_duration = 0
                reason = "Candidate conditions lost"
            else:
                self.state_duration += 1
        
        elif self.state == State.CONFIRMED:
            if self._is_committed(idx) and not self.committed_this_session:
                self.state = State.COMMITTED
                self.state_duration = 1
                self.entry_price = row['close']
                self.entry_idx = idx
                self.entry_high = row['high']
                self.last_swing_high = row['high']
                self.last_swing_high_idx = idx
                self.new_high_made = False
                self.in_pullback = False
                self.pullback_start_idx = None
                self.committed_this_session = True
                action = "BUY"
                reason = f"INSISTENCE detected. Entry @ {row['close']:.4f}"
            elif not self._is_confirmed(idx):
                if self._is_candidate(idx):
                    self.state = State.CANDIDATE
                elif self._is_awakening(idx):
                    self.state = State.AWAKENING
                else:
                    self.state = State.IDLE
                self.state_duration = 0
                reason = "Confirmed conditions lost"
            else:
                self.state_duration += 1
        
        elif self.state == State.COMMITTED:
            is_exhausted, exhaust_reason = self._check_exhausted(idx)
            if is_exhausted:
                self.state = State.EXHAUSTED
                action = "SELL"
                pnl = (row['close'] / self.entry_price - 1) * 100
                reason = f"{exhaust_reason}. Exit @ {row['close']:.4f}, PnL: {pnl:+.2f}%"
                self.trades.append({
                    'entry_time': self.df.iloc[self.entry_idx]['datetime'],
                    'exit_time': row['datetime'],
                    'entry_price': self.entry_price,
                    'exit_price': row['close'],
                    'pnl_pct': pnl,
                    'candles_held': idx - self.entry_idx,
                    'exit_reason': exhaust_reason
                })
                self.entry_price = None
                self.entry_idx = None
            else:
                self.state_duration += 1
                if self.state_duration > 8:
                    self.state = State.EXTENSION
                    reason = "Entering EXTENSION"
        
        elif self.state == State.EXTENSION:
            is_exhausted, exhaust_reason = self._check_exhausted(idx)
            if is_exhausted:
                self.state = State.EXHAUSTED
                action = "SELL"
                pnl = (row['close'] / self.entry_price - 1) * 100
                reason = f"{exhaust_reason}. Exit @ {row['close']:.4f}, PnL: {pnl:+.2f}%"
                self.trades.append({
                    'entry_time': self.df.iloc[self.entry_idx]['datetime'],
                    'exit_time': row['datetime'],
                    'entry_price': self.entry_price,
                    'exit_price': row['close'],
                    'pnl_pct': pnl,
                    'candles_held': idx - self.entry_idx,
                    'exit_reason': exhaust_reason
                })
                self.entry_price = None
                self.entry_idx = None
            else:
                self.state_duration += 1
        
        elif self.state == State.EXHAUSTED:
            self.state = State.IDLE
            self.state_duration = 0
            self.committed_this_session = False
            self.entry_high = None
            self.last_swing_high = None
            self.last_swing_high_idx = None
            self.new_high_made = False
            self.in_pullback = False
            self.pullback_start_idx = None
            reason = "Session reset"
        
        if prev_state != self.state or action != "WAIT":
            self._log(f"[{ts}] {prev_state.value} → {self.state.value} | {reason}")
        
        return {'state': self.state.value, 'action': action, 'price': row['close'], 'reason': reason}
    
    def run_simulation(self, start_idx=100, end_idx=None):
        if end_idx is None:
            end_idx = len(self.df)
        results = []
        for idx in range(start_idx, end_idx):
            result = self.process_candle(idx)
            if result['action'] in ['BUY', 'SELL']:
                results.append({'idx': idx, 'datetime': self.df.iloc[idx]['datetime'], **result})
        return results

def main():
    symbol = 'ALGOUSDT'
    test_date = '2024-12-02'
    
    print(f"🎯 RALLI_ASM_15M v3+ — REFINED EXHAUSTED TEST")
    print(f"Coin: {symbol}")
    print(f"Test Date: {test_date}")
    print("="*70)
    
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    df = pd.read_parquet(path)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('datetime').reset_index(drop=True)
    
    start = pd.Timestamp(test_date) - timedelta(days=1)
    end = pd.Timestamp(test_date) + timedelta(days=2)
    mask = (df['datetime'] >= start) & (df['datetime'] < end)
    test_df = df[mask].reset_index(drop=True)
    
    print(f"Test Period: {test_df['datetime'].min()} to {test_df['datetime'].max()}")
    print(f"Candles: {len(test_df)}")
    print("\n" + "="*70)
    print("📜 STATE TRANSITION LOG:")
    print("="*70)
    
    asm = RalliASM15M_v3plus(test_df, verbose=True)
    signals = asm.run_simulation(start_idx=50)
    
    print("\n" + "="*70)
    print("📈 TRADES:")
    print("="*70)
    for trade in asm.trades:
        status = "✅" if trade['pnl_pct'] > 0 else "❌"
        print(f"{status} {trade['entry_time']} -> {trade['exit_time']}")
        print(f"   Entry: {trade['entry_price']:.4f} | Exit: {trade['exit_price']:.4f}")
        print(f"   PnL: {trade['pnl_pct']:+.2f}% | Candles: {trade['candles_held']}")
        print(f"   Exit Reason: {trade['exit_reason']}")
    
    if asm.trades:
        total_pnl = sum(t['pnl_pct'] for t in asm.trades)
        win_rate = sum(1 for t in asm.trades if t['pnl_pct'] > 0) / len(asm.trades) * 100
        print(f"\n📋 SUMMARY:")
        print(f"  Total Trades: {len(asm.trades)}")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Total PnL: {total_pnl:+.2f}%")
    else:
        print("\n⚠️ No trades in test period")

if __name__ == "__main__":
    main()
