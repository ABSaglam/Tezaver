#!/usr/bin/env python3
"""
🎯 RALLİ KAPISI RK15 — ALGO 15M ASM (v2)

DEĞİŞİKLİK: SQUEEZED artık zorunlu değil.
COMMITTED koşulları sağlanırsa doğrudan giriş.

DURUM AKIŞI (v2):
- IDLE → COMMITTED (doğrudan, koşullar sağlanırsa)
- COMMITTED → EXTENSION → EXHAUSTED → IDLE

FELSEFE: Geç kal ama yanlış girme.
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
    COMMITTED = "COMMITTED"
    EXTENSION = "EXTENSION"
    EXHAUSTED = "EXHAUSTED"

class RalliASM15M_v2:
    """Ralli Kapısı RK15 v2 — Basitleştirilmiş Durum Makinesi"""
    
    def __init__(self, df):
        self.df = df.copy()
        self.state = State.IDLE
        self.entry_price = None
        self.entry_idx = None
        self.state_duration = 0
        self.trades = []
        self._cooldown = 0  # Satış sonrası bekleme
        
        self._calculate_indicators()
    
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
        
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma']
        
        df['is_green'] = df['close'] > df['open']
        
        self.df = df
    
    def _is_committed(self, idx):
        """COMMITTED koşulları — KİLİT GİRİŞ ŞARTLARI"""
        if idx < 8:
            return False
        row = self.df.iloc[idx]
        
        # 1. Tam EMA hizası
        ema_aligned = row['ema9'] > row['ema21'] > row['ema50']
        
        # 2. ATR sağlıklı (değiştirildi: sadece ATR > ATR_MA * 0.9, sıkışma şartı kaldırıldı)
        if pd.isna(row['atr_ma']):
            return False
        atr_healthy = row['atr'] > row['atr_ma'] * 0.9
        
        # 3. RSI goldilocks (55-75)
        rsi_ok = 55 < row['rsi'] < 75
        
        # 4. Hacim teyidi
        vol_ok = row['vol_ratio'] > 1.5
        
        # 5. Yapısal bütünlük: Son 8 mumun 5'i yeşil
        last_8 = self.df.iloc[idx-7:idx+1]
        green_count = last_8['is_green'].sum()
        structure_ok = green_count >= 5
        
        # 6. Fiyat anchor üstünde
        above_anchor = row['close'] > row['ema50']
        
        return all([ema_aligned, atr_healthy, rsi_ok, vol_ok, structure_ok, above_anchor])
    
    def _is_exhausted(self, idx):
        """EXHAUSTED koşulları"""
        if idx < 4:
            return False
        row = self.df.iloc[idx]
        prev_2 = self.df.iloc[idx-2]
        prev_4 = self.df.iloc[idx-4]
        
        # Tetikleyici 1: Aşırı alım çöküşü
        overbought_crash = row['rsi'] > 80 and row['rsi'] < prev_2['rsi']
        
        # Tetikleyici 2: Blow-off top
        blowoff = row['vol_ratio'] > 4.0 and not row['is_green']
        
        # Tetikleyici 3: Trend kırılması
        trend_break = row['ema9'] < row['ema21']
        
        # Tetikleyici 4: Momentum kaybı (3 kırmızı mum)
        last_3 = self.df.iloc[idx-2:idx+1]
        red_streak = (~last_3['is_green']).all()
        
        # Tetikleyici 5: Yapısal bozulma
        structural_break = row['close'] < row['ema50']
        
        return any([overbought_crash, blowoff, trend_break, red_streak, structural_break])
    
    def process_candle(self, idx):
        row = self.df.iloc[idx]
        action = "WAIT"
        
        if self._cooldown > 0:
            self._cooldown -= 1
            return {'state': self.state.value, 'action': action, 'price': row['close']}
        
        if self.state == State.IDLE:
            if self._is_committed(idx):
                self.state = State.COMMITTED
                self.state_duration = 1
                self.entry_price = row['close']
                self.entry_idx = idx
                action = "BUY"
        
        elif self.state == State.COMMITTED:
            if self._is_exhausted(idx):
                self.state = State.EXHAUSTED
                action = "SELL"
                pnl = (row['close'] / self.entry_price - 1) * 100
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
                self._cooldown = 8  # 2 saat bekleme
            else:
                self.state_duration += 1
                if self.state_duration > 8:
                    self.state = State.EXTENSION
        
        elif self.state == State.EXTENSION:
            if self._is_exhausted(idx):
                self.state = State.EXHAUSTED
                action = "SELL"
                pnl = (row['close'] / self.entry_price - 1) * 100
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
                self._cooldown = 8
            else:
                self.state_duration += 1
        
        elif self.state == State.EXHAUSTED:
            self.state = State.IDLE
            self.state_duration = 0
        
        return {
            'state': self.state.value,
            'action': action,
            'price': row['close']
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
    
    print(f"🎯 RALLİ KAPISI RK15 v2 — TEST")
    print(f"Coin: {symbol}")
    print(f"Test Date: {test_date}")
    print("="*60)
    
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
    
    asm = RalliASM15M_v2(test_df)
    signals = asm.run_simulation(start_idx=50)
    
    print("\n📊 SIGNALS:")
    for sig in signals:
        print(f"  {sig['datetime']} | {sig['state']} | {sig['action']} @ {sig['price']:.4f}")
    
    print("\n📈 TRADES:")
    for trade in asm.trades:
        status = "✅" if trade['pnl_pct'] > 0 else "❌"
        print(f"  {status} Entry: {trade['entry_price']:.4f} -> Exit: {trade['exit_price']:.4f} | PnL: {trade['pnl_pct']:+.2f}% | Candles: {trade['candles_held']}")
    
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
