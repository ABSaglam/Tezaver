#!/usr/bin/env python3
"""
🎯 RALLİ KAPISI RK15 — ALGO 15M ASM

ÖN KOŞUL: Bu sistem SADECE ayas_tunnel_daily = PASS olduğunda çalışır.

DURUM SETİ:
- IDLE: Beklemede
- SQUEEZED: Sıkışma (volatilite düşük)
- AWAKENING: Uyanış (ilk hareket sinyalleri)
- COMMITTED: Kararlılık → BUY
- EXTENSION: Uzatma (trend devam)
- EXHAUSTED: Tükeniş → SELL

FELSEFE: Geç kal ama yanlış girme.
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from enum import Enum

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

class State(Enum):
    IDLE = "IDLE"
    SQUEEZED = "SQUEEZED"
    AWAKENING = "AWAKENING"
    COMMITTED = "COMMITTED"
    EXTENSION = "EXTENSION"
    EXHAUSTED = "EXHAUSTED"

class RalliASM15M:
    """Ralli Kapısı RK15 — 15M Durum Makinesi"""
    
    def __init__(self, df):
        self.df = df.copy()
        self.state = State.IDLE
        self.entry_price = None
        self.entry_idx = None
        self.state_duration = 0
        self.trades = []
        
        self._calculate_indicators()
    
    def _calculate_indicators(self):
        """Tüm gerekli indikatörleri hesapla"""
        df = self.df
        
        # EMA'lar
        df['ema9'] = df['close'].ewm(span=9).mean()
        df['ema21'] = df['close'].ewm(span=21).mean()
        df['ema50'] = df['close'].ewm(span=50).mean()
        
        # ATR (14 periyot)
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(14).mean()
        df['atr_ma'] = df['atr'].rolling(50).mean()
        
        # RSI (14 periyot)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volume Ratio
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma']
        
        # Mum Rengi
        df['is_green'] = df['close'] > df['open']
        
        self.df = df
    
    def _is_squeezed(self, idx):
        """ATR sıkışması tespiti"""
        row = self.df.iloc[idx]
        if pd.isna(row['atr_ma']):
            return False
        return row['atr'] < row['atr_ma'] * 0.7
    
    def _is_awakening(self, idx):
        """Uyanış koşulları"""
        if idx < 4:
            return False
        row = self.df.iloc[idx]
        prev = self.df.iloc[idx-4]
        
        # ATR artıyor
        atr_rising = row['atr'] > prev['atr']
        
        # EMA kısa > uzun
        ema_aligned = row['ema9'] > row['ema21']
        
        # Hacim yüksek
        vol_high = row['vol_ratio'] > 1.2
        
        # RSI yükseliyor
        rsi_rising = row['rsi'] > 50 and row['rsi'] > prev['rsi']
        
        return atr_rising and ema_aligned and vol_high and rsi_rising
    
    def _is_committed(self, idx):
        """COMMITTED koşulları — KİLİT GİRİŞ ŞARTLARI"""
        if idx < 8:
            return False
        row = self.df.iloc[idx]
        
        # 1. Tam EMA hizası: EMA9 > EMA21 > EMA50
        ema_aligned = row['ema9'] > row['ema21'] > row['ema50']
        
        # 2. ATR sağlıklı
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
        """EXHAUSTED koşulları — ÇIKIŞ TETİKLEYİCİLERİ"""
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
        
        # Tetikleyici 6: ATR çöküşü
        atr_collapse = row['atr'] < prev_4['atr'] * 0.6 if not pd.isna(prev_4['atr']) else False
        
        return any([overbought_crash, blowoff, trend_break, red_streak, structural_break, atr_collapse])
    
    def process_candle(self, idx):
        """Tek bir mum için state machine işle"""
        row = self.df.iloc[idx]
        action = "WAIT"
        
        # STATE TRANSITIONS
        if self.state == State.IDLE:
            if self._is_squeezed(idx):
                self.state = State.SQUEEZED
                self.state_duration = 1
        
        elif self.state == State.SQUEEZED:
            if self._is_squeezed(idx):
                self.state_duration += 1
            else:
                if self._is_awakening(idx) and self.state_duration >= 12:
                    self.state = State.AWAKENING
                    self.state_duration = 1
                else:
                    self.state = State.IDLE
                    self.state_duration = 0
        
        elif self.state == State.AWAKENING:
            if self._is_committed(idx):
                self.state = State.COMMITTED
                self.state_duration = 1
                self.entry_price = row['close']
                self.entry_idx = idx
                action = "BUY"
            elif not self._is_awakening(idx):
                # Trend kıılırsa geri dön
                if self._is_squeezed(idx):
                    self.state = State.SQUEEZED
                else:
                    self.state = State.IDLE
                self.state_duration = 0
            else:
                self.state_duration += 1
        
        elif self.state == State.COMMITTED:
            if self._is_exhausted(idx):
                self.state = State.EXHAUSTED
                action = "SELL"
                # Trade kaydet
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
            else:
                self.state_duration += 1
                if self.state_duration > 8:
                    self.state = State.EXTENSION
        
        elif self.state == State.EXTENSION:
            if self._is_exhausted(idx):
                self.state = State.EXHAUSTED
                action = "SELL"
                # Trade kaydet
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
            else:
                self.state_duration += 1
        
        elif self.state == State.EXHAUSTED:
            # Pozisyon kapatıldı, bekleme moduna dön
            self.state = State.IDLE
            self.state_duration = 0
        
        return {
            'state': self.state.value,
            'action': action,
            'price': row['close']
        }
    
    def run_simulation(self, start_idx=100, end_idx=None):
        """Simülasyon çalıştır"""
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
    """Test: ALGO 15M ASM on known rally day (2024-12-02)"""
    symbol = 'ALGOUSDT'
    test_date = '2024-12-02'  # Known GOLD rally
    
    print(f"🎯 RALLİ KAPISI RK15 — TEST")
    print(f"Coin: {symbol}")
    print(f"Test Date: {test_date}")
    print("="*60)
    
    # Load 15M data
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    if not os.path.exists(path):
        print("❌ 15M data not found")
        return
    
    df = pd.read_parquet(path)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Filter for test date (and day before for context)
    start = pd.Timestamp(test_date) - timedelta(days=1)
    end = pd.Timestamp(test_date) + timedelta(days=1)
    mask = (df['datetime'] >= start) & (df['datetime'] < end)
    test_df = df[mask].reset_index(drop=True)
    
    print(f"Test Period: {test_df['datetime'].min()} to {test_df['datetime'].max()}")
    print(f"Candles: {len(test_df)}")
    
    # Run ASM
    asm = RalliASM15M(test_df)
    signals = asm.run_simulation(start_idx=50)
    
    print("\n📊 SIGNALS:")
    for sig in signals:
        print(f"  {sig['datetime']} | {sig['state']} | {sig['action']} @ {sig['price']:.4f}")
    
    print("\n📈 TRADES:")
    for trade in asm.trades:
        status = "✅" if trade['pnl_pct'] > 0 else "❌"
        print(f"  {status} Entry: {trade['entry_price']:.4f} -> Exit: {trade['exit_price']:.4f} | PnL: {trade['pnl_pct']:+.2f}%")
    
    # Summary
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
