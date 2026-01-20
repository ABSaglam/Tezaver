#!/usr/bin/env python3
"""
🎯 RALLI_ASM_15M v4 — COMMITTED_EARLY Extension

NEW STATE: COMMITTED_EARLY
- Early but cautious rally touch
- Reduced conditions (no EMA50 requirement, RSI 55-65)
- Can transition to COMMITTED_FULL or exit via EXHAUSTED

STATE FLOW:
IDLE → AWAKENING → CANDIDATE → CONFIRMED → COMMITTED_EARLY → COMMITTED_FULL → EXTENSION → EXHAUSTED
                                         ↘ COMMITTED_FULL (direct path still exists)
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
    COMMITTED_EARLY = "COMMITTED_EARLY"
    COMMITTED_FULL = "COMMITTED_FULL"
    EXTENSION = "EXTENSION"
    EXHAUSTED = "EXHAUSTED"

class RalliASM15M_v4:
    """8-State Machine with COMMITTED_EARLY"""
    
    def __init__(self, df, verbose=True):
        self.df = df.copy()
        self.state = State.IDLE
        self.entry_price = None
        self.entry_idx = None
        self.state_duration = 0
        self.trades = []
        self.logs = []
        self.verbose = verbose
        
        self.committed_this_session = False
        self.confirmed_duration = 0  # Track time in CONFIRMED
        
        # EXHAUSTED tracking
        self.entry_high = None
        self.last_swing_high = None
        self.last_swing_high_idx = None
        self.pullback_start_idx = None
        self.in_pullback = False
        self.new_high_made = False
        
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
    
    def _is_committed_early(self, idx):
        """
        COMMITTED_EARLY: Early but cautious entry
        - Reduced conditions vs COMMITTED_FULL
        - No EMA50 requirement
        - RSI 55-65 (tighter range, earlier zone)
        """
        if idx < 10:
            return False
        
        # Require minimum 3 candles in CONFIRMED
        if self.confirmed_duration < 3:
            return False
        
        row = self.df.iloc[idx]
        last_5 = self.df.iloc[idx-4:idx+1]
        
        # 1. EMA9 > EMA21 (no EMA50 requirement)
        ema_aligned = row['ema9'] > row['ema21']
        
        # 2. Price above EMA9 now
        above_ema9 = row['close'] > row['ema9']
        
        # 3. Was below EMA9 recently (EMA reclaim pattern)
        was_below_ema9 = (last_5['close'] < last_5['ema9']).any()
        
        # 4. RSI 55-65 (earlier zone than COMMITTED_FULL)
        rsi_early_zone = 55 <= row['rsi'] <= 65
        
        # 5. Volume >= 1.3
        vol_ok = row['vol_ratio'] >= 1.3
        
        return all([ema_aligned, above_ema9, was_below_ema9, rsi_early_zone, vol_ok])
    
    def _is_committed_full(self, idx):
        """
        COMMITTED_FULL: Full conviction entry (original COMMITTED logic)
        - Full EMA alignment (9 > 21 > 50)
        - RSI 55-75
        - Volume > 1.0
        """
        if idx < 10:
            return False
        row = self.df.iloc[idx]
        last_5 = self.df.iloc[idx-4:idx+1]
        
        above_ema9 = row['close'] > row['ema9']
        was_below_ema9 = (last_5['close'] < last_5['ema9']).any()
        previous_high = last_5['high'].max()
        high_challenged = row['high'] >= previous_high * 0.995
        full_alignment = row['ema9'] > row['ema21'] > row['ema50']
        vol_ok = row['vol_ratio'] > 1.0
        
        return all([above_ema9, was_below_ema9, high_challenged, full_alignment, vol_ok])
    
    def _check_exhausted(self, idx):
        """Same EXHAUSTED logic for both COMMITTED_EARLY and COMMITTED_FULL"""
        if self.entry_idx is None:
            return False, ""
        
        row = self.df.iloc[idx]
        candles_since_entry = idx - self.entry_idx
        
        if row['high'] > (self.last_swing_high or 0):
            self.last_swing_high = row['high']
            self.last_swing_high_idx = idx
            self.new_high_made = True
            self.in_pullback = False
            self.pullback_start_idx = None
        
        if not self.in_pullback and row['close'] < row['ema9']:
            self.in_pullback = True
            self.pullback_start_idx = idx
        
        if self.in_pullback and row['close'] > row['ema9']:
            self.in_pullback = False
            self.pullback_start_idx = None
        
        # CONDITION 1: LOWER HIGH
        if self.new_high_made and self.last_swing_high_idx is not None:
            candles_since_last_high = idx - self.last_swing_high_idx
            if candles_since_last_high >= 3:
                if row['is_green'] and row['range'] > row['atr'] * 0.5:
                    if row['high'] < self.last_swing_high * 0.998:
                        return True, f"LOWER HIGH: {row['high']:.4f} < {self.last_swing_high:.4f}"
        
        # CONDITION 2: LOSS OF RECOVERY SPEED
        if self.in_pullback and self.pullback_start_idx is not None:
            pullback_duration = idx - self.pullback_start_idx
            if pullback_duration >= 5:
                return True, f"LOSS OF RECOVERY: {pullback_duration} candles"
        
        # CONDITION 3: TIME DECAY
        if candles_since_entry >= 10:
            current_max_high = self.df.iloc[self.entry_idx:idx+1]['high'].max()
            meaningful_gain = (current_max_high / self.entry_high - 1) * 100
            if meaningful_gain < 0.5:
                return True, f"TIME DECAY: {candles_since_entry} candles, {meaningful_gain:.2f}% gain"
        
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
                reason = "Range/Volume expansion"
        
        elif self.state == State.AWAKENING:
            if self._is_candidate(idx):
                self.state = State.CANDIDATE
                self.state_duration = 1
                reason = "Structure aligned"
            elif not self._is_awakening(idx):
                self.state = State.IDLE
                self.state_duration = 0
                reason = "Awakening lost"
            else:
                self.state_duration += 1
        
        elif self.state == State.CANDIDATE:
            if self._is_confirmed(idx):
                self.state = State.CONFIRMED
                self.state_duration = 1
                self.confirmed_duration = 1
                reason = "Directional bias preserved"
            elif not self._is_candidate(idx):
                if self._is_awakening(idx):
                    self.state = State.AWAKENING
                else:
                    self.state = State.IDLE
                self.state_duration = 0
                reason = "Candidate lost"
            else:
                self.state_duration += 1
        
        elif self.state == State.CONFIRMED:
            # Check for COMMITTED_EARLY first (easier conditions)
            if self._is_committed_early(idx) and not self.committed_this_session:
                self.state = State.COMMITTED_EARLY
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
                reason = f"EARLY_TOUCH @ {row['close']:.4f}"
            # Check for direct COMMITTED_FULL
            elif self._is_committed_full(idx) and not self.committed_this_session:
                self.state = State.COMMITTED_FULL
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
                reason = f"FULL_CONVICTION @ {row['close']:.4f}"
            elif not self._is_confirmed(idx):
                if self._is_candidate(idx):
                    self.state = State.CANDIDATE
                elif self._is_awakening(idx):
                    self.state = State.AWAKENING
                else:
                    self.state = State.IDLE
                self.state_duration = 0
                self.confirmed_duration = 0
                reason = "Confirmed lost"
            else:
                self.state_duration += 1
                self.confirmed_duration += 1
        
        elif self.state == State.COMMITTED_EARLY:
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
                    'exit_reason': exhaust_reason,
                    'entry_type': 'EARLY_TOUCH'
                })
                self.entry_price = None
                self.entry_idx = None
            # Check for upgrade to COMMITTED_FULL
            elif self._is_committed_full(idx):
                self.state = State.COMMITTED_FULL
                reason = "Upgraded to FULL_CONVICTION"
            else:
                self.state_duration += 1
                if self.state_duration > 8:
                    self.state = State.EXTENSION
                    reason = "Entering EXTENSION"
        
        elif self.state == State.COMMITTED_FULL:
            is_exhausted, exhaust_reason = self._check_exhausted(idx)
            if is_exhausted:
                self.state = State.EXHAUSTED
                action = "SELL"
                pnl = (row['close'] / self.entry_price - 1) * 100
                reason = f"{exhaust_reason}. Exit @ {row['close']:.4f}, PnL: {pnl:+.2f}%"
                entry_type = 'FULL_CONVICTION' if prev_state == State.CONFIRMED else 'EARLY_UPGRADED'
                self.trades.append({
                    'entry_time': self.df.iloc[self.entry_idx]['datetime'],
                    'exit_time': row['datetime'],
                    'entry_price': self.entry_price,
                    'exit_price': row['close'],
                    'pnl_pct': pnl,
                    'candles_held': idx - self.entry_idx,
                    'exit_reason': exhaust_reason,
                    'entry_type': entry_type
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
                # Determine entry type from existing trade if not set
                entry_type = 'EXTENDED'
                self.trades.append({
                    'entry_time': self.df.iloc[self.entry_idx]['datetime'],
                    'exit_time': row['datetime'],
                    'entry_price': self.entry_price,
                    'exit_price': row['close'],
                    'pnl_pct': pnl,
                    'candles_held': idx - self.entry_idx,
                    'exit_reason': exhaust_reason,
                    'entry_type': entry_type
                })
                self.entry_price = None
                self.entry_idx = None
            else:
                self.state_duration += 1
        
        elif self.state == State.EXHAUSTED:
            self.state = State.IDLE
            self.state_duration = 0
            self.committed_this_session = False
            self.confirmed_duration = 0
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
    
    print(f"🎯 RALLI_ASM_15M v4 — COMMITTED_EARLY Extension")
    print(f"Test: {symbol} on {test_date}")
    print("="*70)
    
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    df = pd.read_parquet(path)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('datetime').reset_index(drop=True)
    
    start = pd.Timestamp(test_date) - timedelta(days=1)
    end = pd.Timestamp(test_date) + timedelta(days=2)
    mask = (df['datetime'] >= start) & (df['datetime'] < end)
    test_df = df[mask].reset_index(drop=True)
    
    print("\n📜 STATE LOG:")
    print("-"*70)
    asm = RalliASM15M_v4(test_df, verbose=True)
    signals = asm.run_simulation(start_idx=50)
    
    print("\n" + "="*70)
    print("📈 TRADES:")
    for t in asm.trades:
        status = "✅" if t['pnl_pct'] > 0 else "❌"
        print(f"{status} [{t['entry_type']}] {t['entry_time']} → {t['exit_time']}")
        print(f"   Entry: {t['entry_price']:.4f} | Exit: {t['exit_price']:.4f}")
        print(f"   PnL: {t['pnl_pct']:+.2f}% | Candles: {t['candles_held']}")
        print(f"   Exit: {t['exit_reason']}")

if __name__ == "__main__":
    main()
