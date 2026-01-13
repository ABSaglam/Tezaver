#!/usr/bin/env python3
"""
Rally DNA Extractor - Analyze rally patterns from Ayaş Tüneli signals.
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths
from tezaver.core.rally_store import RallyStore

def compute_rsi(close, period=14):
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.0001)
    return 100 - (100 / (1 + rs))

def analyze_rally_shape(prices_15m, start_idx, peak_idx):
    """Analyze the shape of a rally."""
    if peak_idx <= start_idx or peak_idx >= len(prices_15m):
        return None
    
    segment = prices_15m.iloc[start_idx:peak_idx+1]
    if len(segment) < 3:
        return None
    
    # Duration in 15m bars
    duration_bars = len(segment)
    
    # Speed: gain per bar
    total_gain = (segment.iloc[-1] - segment.iloc[0]) / segment.iloc[0] * 100
    speed = total_gain / duration_bars if duration_bars > 0 else 0
    
    # Shape detection
    mid_idx = len(segment) // 2
    first_half_gain = (segment.iloc[mid_idx] - segment.iloc[0]) / segment.iloc[0] * 100
    second_half_gain = (segment.iloc[-1] - segment.iloc[mid_idx]) / segment.iloc[mid_idx] * 100
    
    if first_half_gain > second_half_gain * 1.5:
        shape = "FRONT-LOADED"  # Fast start, slow finish
    elif second_half_gain > first_half_gain * 1.5:
        shape = "BACK-LOADED"   # Slow start, fast finish
    else:
        shape = "LINEAR"        # Steady climb
    
    # Check for V-bounce (significant dip before rally)
    min_before_rally = segment.min()
    if segment.iloc[0] > min_before_rally * 1.05:
        shape = "V-BOUNCE"
    
    return {
        'duration_bars': duration_bars,
        'duration_hours': duration_bars * 0.25,
        'total_gain_pct': total_gain,
        'speed_per_bar': speed,
        'shape': shape
    }

def classify_rally(metrics):
    """Classify rally into types based on metrics."""
    if metrics is None:
        return "UNKNOWN"
    
    duration = metrics['duration_bars']
    speed = metrics['speed_per_bar']
    shape = metrics['shape']
    
    if shape == "V-BOUNCE":
        return "V-BOUNCE"
    elif duration <= 8 and speed > 1.5:
        return "INSTANT"
    elif duration > 48:
        return "GRIND"
    else:
        return "STANDARD"

def main():
    print("=" * 70)
    print("🧬 RALLİ DNA ANALİZİ")
    print("=" * 70)
    
    # Load Ayaş Tüneli backtest results
    report_path = Path("analysis/ayas_tuneli_2y_120h_rapor.md")
    if not report_path.exists():
        print("❌ Ayaş Tüneli raporu bulunamadı")
        return
    
    # Parse rallies from report
    import re
    with open(report_path, 'r') as f:
        content = f.read()
    
    # Extract Diamond rallies for analysis
    diamond_pattern = r'(\w+)\(D\+(\d+)%\)'
    matches = re.findall(diamond_pattern, content)
    
    print(f"📊 Diamond ralliler bulundu: {len(matches)}")
    
    rally_data = []
    
    for symbol, gain in matches[:100]:  # Sample first 100
        symbol_full = f"{symbol}USDT"
        
        try:
            path_15m = coin_cell_paths.get_history_file(symbol_full, '15m')
            if not path_15m.exists():
                continue
            
            df = pd.read_parquet(path_15m)
            if len(df) < 100:
                continue
            
            # Find rally peaks (simplified - look for high gains)
            df['returns'] = df['close'].pct_change(16) * 100  # 4-hour returns
            high_return_idx = df[df['returns'] > 20].index.tolist()
            
            for peak_idx in high_return_idx[:3]:  # First 3 peaks
                start_idx = max(0, peak_idx - 48)
                metrics = analyze_rally_shape(df['close'], start_idx, peak_idx)
                
                if metrics:
                    metrics['symbol'] = symbol
                    metrics['gain_pct'] = int(gain)
                    metrics['rally_type'] = classify_rally(metrics)
                    rally_data.append(metrics)
                    
        except Exception as e:
            continue
    
    if not rally_data:
        print("❌ Ralli verileri çıkarılamadı")
        return
    
    df_rallies = pd.DataFrame(rally_data)
    
    # Summary
    print("\n" + "=" * 70)
    print("📈 RALLİ TİP DAĞILIMI")
    print("=" * 70)
    
    type_counts = df_rallies['rally_type'].value_counts()
    for rtype, count in type_counts.items():
        pct = count / len(df_rallies) * 100
        print(f"  {rtype}: {count} ({pct:.1f}%)")
    
    print("\n📊 RALLİ KARAKTERİSTİKLERİ (Tip bazlı)")
    print("-" * 50)
    
    for rtype in df_rallies['rally_type'].unique():
        subset = df_rallies[df_rallies['rally_type'] == rtype]
        print(f"\n{rtype}:")
        print(f"  Ortalama süre: {subset['duration_hours'].mean():.1f} saat")
        print(f"  Ortalama hız: {subset['speed_per_bar'].mean():.2f}%/bar")
        print(f"  Örnek koinler: {', '.join(subset['symbol'].head(5).tolist())}")
    
    # Save
    output_path = Path("library/rally_dna/rally_profiles.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_rallies.to_parquet(output_path, index=False)
    print(f"\n📁 Kaydedildi: {output_path}")

if __name__ == "__main__":
    main()
