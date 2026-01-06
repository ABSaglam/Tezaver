"""
SuperNova Pre-Condition Analyzer
================================

Finds SuperNova events with strict criteria and analyzes the "weather" before them.

Criteria:
- First 3 candles must be GREEN
- Total gain >= 10%
- Volume spike >= 7x average

Then analyzes pre-event conditions (5-10 bars before).
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# Setup path
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tezaver.core.config import DEFAULT_COINS
from tezaver.data.history_service import load_existing_history
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class SuperNovaEvent:
    """A SuperNova event with pre-conditions."""
    symbol: str
    event_time: pd.Timestamp
    event_idx: int
    # Event metrics
    gain_pct: float  # Total gain in first 3 bars
    volume_ratio: float  # Volume spike ratio
    # Pre-conditions (5 bars before event)
    pre_rsi: float
    pre_rsi_ema: float
    pre_macd_hist: float
    pre_macd_signal: str  # 'positive', 'negative', 'crossing'
    pre_trend: str  # RSI relationship
    # 10 bar pre-conditions
    pre_10_rsi_min: float
    pre_10_rsi_max: float
    pre_10_rsi_range: float


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add RSI, MACD, and other indicators to dataframe."""
    df = df.copy()
    
    # RSI (14 period)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # RSI EMA (11 period)
    df['rsi_ema'] = df['rsi'].ewm(span=11, adjust=False).mean()
    
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # Volume moving average (20 period)
    df['volume_ma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']
    
    return df


def find_supernova_events(df: pd.DataFrame, symbol: str) -> List[SuperNovaEvent]:
    """
    Find SuperNova events with criteria:
    - First 3 candles GREEN
    - Total gain >= 10%
    - Volume ratio >= 7x
    """
    events = []
    
    if len(df) < 50:
        return events
    
    df = calculate_indicators(df)
    
    for i in range(30, len(df) - 3):  # Need room before and after
        # Check volume spike (current bar)
        if df['volume_ratio'].iloc[i] < 7.0:
            continue
        
        # Check first 3 candles are green
        candle1_green = df['close'].iloc[i] > df['open'].iloc[i]
        candle2_green = df['close'].iloc[i+1] > df['open'].iloc[i+1] if i+1 < len(df) else False
        candle3_green = df['close'].iloc[i+2] > df['open'].iloc[i+2] if i+2 < len(df) else False
        
        if not (candle1_green and candle2_green and candle3_green):
            continue
        
        # Calculate 3-bar gain
        entry_price = df['open'].iloc[i]
        exit_price = df['close'].iloc[i+2] if i+2 < len(df) else df['close'].iloc[i]
        gain_pct = (exit_price - entry_price) / entry_price
        
        if gain_pct < 0.10:  # Must be at least 10%
            continue
        
        # Get pre-conditions (5 bars before)
        pre_idx = i - 5
        if pre_idx < 0:
            continue
            
        pre_rsi = df['rsi'].iloc[pre_idx]
        pre_rsi_ema = df['rsi_ema'].iloc[pre_idx]
        pre_macd_hist = df['macd_hist'].iloc[pre_idx]
        
        # MACD signal classification
        if pre_macd_hist > 0.001:
            pre_macd_signal = 'positive'
        elif pre_macd_hist < -0.001:
            pre_macd_signal = 'negative'
        else:
            pre_macd_signal = 'neutral'
        
        # RSI trend
        if pre_rsi > pre_rsi_ema + 2:
            pre_trend = 'rsi_above_ema'
        elif pre_rsi < pre_rsi_ema - 2:
            pre_trend = 'rsi_below_ema'
        else:
            pre_trend = 'rsi_near_ema'
        
        # 10 bar pre-conditions
        pre_10_slice = df['rsi'].iloc[max(0, i-10):i]
        pre_10_rsi_min = pre_10_slice.min() if len(pre_10_slice) > 0 else 0
        pre_10_rsi_max = pre_10_slice.max() if len(pre_10_slice) > 0 else 0
        pre_10_rsi_range = pre_10_rsi_max - pre_10_rsi_min
        
        event = SuperNovaEvent(
            symbol=symbol,
            event_time=df['datetime'].iloc[i] if 'datetime' in df.columns else pd.NaT,
            event_idx=i,
            gain_pct=gain_pct,
            volume_ratio=df['volume_ratio'].iloc[i],
            pre_rsi=pre_rsi,
            pre_rsi_ema=pre_rsi_ema,
            pre_macd_hist=pre_macd_hist,
            pre_macd_signal=pre_macd_signal,
            pre_trend=pre_trend,
            pre_10_rsi_min=pre_10_rsi_min,
            pre_10_rsi_max=pre_10_rsi_max,
            pre_10_rsi_range=pre_10_rsi_range
        )
        events.append(event)
    
    return events


def analyze_preconditions(events: List[SuperNovaEvent]) -> Dict:
    """Analyze the pre-conditions of all events."""
    if not events:
        return {}
    
    df = pd.DataFrame([
        {
            'symbol': e.symbol,
            'gain_pct': e.gain_pct,
            'volume_ratio': e.volume_ratio,
            'pre_rsi': e.pre_rsi,
            'pre_rsi_ema': e.pre_rsi_ema,
            'pre_macd_hist': e.pre_macd_hist,
            'pre_macd_signal': e.pre_macd_signal,
            'pre_trend': e.pre_trend,
            'pre_10_rsi_range': e.pre_10_rsi_range
        }
        for e in events
    ])
    
    analysis = {
        'total_events': len(events),
        'avg_gain': df['gain_pct'].mean() * 100,
        'avg_volume_ratio': df['volume_ratio'].mean(),
        
        # RSI Analysis
        'avg_pre_rsi': df['pre_rsi'].mean(),
        'rsi_50_70_count': len(df[(df['pre_rsi'] >= 50) & (df['pre_rsi'] <= 70)]),
        'rsi_50_70_pct': len(df[(df['pre_rsi'] >= 50) & (df['pre_rsi'] <= 70)]) / len(df) * 100,
        
        # MACD Analysis
        'macd_positive_count': len(df[df['pre_macd_signal'] == 'positive']),
        'macd_positive_pct': len(df[df['pre_macd_signal'] == 'positive']) / len(df) * 100,
        
        # RSI-EMA relationship
        'rsi_near_ema_count': len(df[df['pre_trend'] == 'rsi_near_ema']),
        'rsi_near_ema_pct': len(df[df['pre_trend'] == 'rsi_near_ema']) / len(df) * 100,
        
        # Compression analysis
        'avg_rsi_range': df['pre_10_rsi_range'].mean(),
        'compressed_count': len(df[df['pre_10_rsi_range'] < 15]),  # RSI range < 15 = compressed
        'compressed_pct': len(df[df['pre_10_rsi_range'] < 15]) / len(df) * 100,
    }
    
    return analysis


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SuperNova Pre-Condition Analyzer")
    parser.add_argument("--coins", type=int, default=100, help="Number of coins to scan")
    parser.add_argument("--tf", type=str, default="15m", help="Timeframe")
    args = parser.parse_args()
    
    coins = DEFAULT_COINS[:args.coins]
    
    print("=" * 60)
    print("  SUPERNOVA PRE-CONDITION ANALYZER")
    print("  Criteria: 3 Green Candles, >10% Gain, 7x+ Volume")
    print("=" * 60)
    print(f"\nScanning {len(coins)} coins on {args.tf}...")
    
    all_events = []
    
    for i, symbol in enumerate(coins):
        if i % 20 == 0:
            print(f"Progress: {i}/{len(coins)}...")
        
        df = load_existing_history(symbol, args.tf)
        if df is None or df.empty:
            continue
        
        if 'datetime' not in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        
        events = find_supernova_events(df, symbol)
        all_events.extend(events)
    
    print(f"\n{'='*60}")
    print(f"  RESULTS: Found {len(all_events)} SuperNova Events")
    print(f"{'='*60}")
    
    if not all_events:
        print("No events found with given criteria.")
        return
    
    # Analyze pre-conditions
    analysis = analyze_preconditions(all_events)
    
    print(f"\n📊 GENEL İSTATİSTİKLER:")
    print(f"   Toplam Olay: {analysis['total_events']}")
    print(f"   Ortalama Kazanç: %{analysis['avg_gain']:.1f}")
    print(f"   Ortalama Hacim Oranı: {analysis['avg_volume_ratio']:.1f}x")
    
    print(f"\n🌡️ RSI HAVA DURUMU (5 bar önce):")
    print(f"   Ortalama RSI: {analysis['avg_pre_rsi']:.1f}")
    print(f"   RSI 50-70 Aralığında: {analysis['rsi_50_70_count']} (%{analysis['rsi_50_70_pct']:.1f})")
    
    print(f"\n📈 MACD DURUMU (5 bar önce):")
    print(f"   Pozitif Alanda: {analysis['macd_positive_count']} (%{analysis['macd_positive_pct']:.1f})")
    
    print(f"\n🎯 RSI-EMA İLİŞKİSİ (5 bar önce):")
    print(f"   RSI ≈ EMA (Yakın): {analysis['rsi_near_ema_count']} (%{analysis['rsi_near_ema_pct']:.1f})")
    
    print(f"\n🗜️ SIKIŞMA ANALİZİ (10 bar önce):")
    print(f"   Ortalama RSI Aralığı: {analysis['avg_rsi_range']:.1f}")
    print(f"   Sıkışık (<15 RSI range): {analysis['compressed_count']} (%{analysis['compressed_pct']:.1f})")
    
    print(f"\n{'='*60}")
    
    # Save detailed results
    output_path = project_root / "data" / "simulation_results"
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    events_df = pd.DataFrame([
        {
            'symbol': e.symbol,
            'event_time': e.event_time,
            'gain_pct': e.gain_pct,
            'volume_ratio': e.volume_ratio,
            'pre_rsi': e.pre_rsi,
            'pre_rsi_ema': e.pre_rsi_ema,
            'pre_macd_hist': e.pre_macd_hist,
            'pre_macd_signal': e.pre_macd_signal,
            'pre_trend': e.pre_trend,
            'pre_10_rsi_range': e.pre_10_rsi_range
        }
        for e in all_events
    ])
    
    events_path = output_path / f"supernova_preconditions_{timestamp}.csv"
    events_df.to_csv(events_path, index=False)
    print(f"\n📁 Detaylı sonuçlar: {events_path}")


if __name__ == "__main__":
    main()
