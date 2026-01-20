
import sys
import os
import pandas as pd
import numpy as np
import scipy.stats as stats

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths
from db_helper import get_rallies, TRAIN_CUTOFF

def calculate_harmony_metrics(df):
    # 1. RHYTHM (Volume Consistency)
    # Is the volume flow smooth (Legato) or erratic (Staccato)?
    # Low CV (Coef of Variation) = Smooth Rhythm
    df['vol_rolling_mean'] = df['volume'].rolling(12).mean() # 2 days of 4H
    df['vol_rolling_std'] = df['volume'].rolling(12).std()
    df['rhythm_cv'] = df['vol_rolling_std'] / df['vol_rolling_mean'] # Lower is better (More rhythmic)
    
    # 2. TEXTURE (Candle Confidence)
    # Body vs Shadow. We want "Confident" candles (High Body/Range ratio).
    body = abs(df['close'] - df['open'])
    rng = df['high'] - df['low']
    df['texture_confidence'] = (body / rng).rolling(6).mean() # Last 24h confidence
    
    # 3. TENSION (Bollinger/ATR Squeeze)
    # The "Silence before the storm".
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    df['atr_ratio'] = df['atr'] / df['close'] * 100
    # Rolling Min/Max of ATR to define "Relative Tightness"
    df['atr_min_200'] = df['atr_ratio'].rolling(200).min()
    df['tension_score'] = df['atr_ratio'] / df['atr_min_200'] # Closer to 1.0 means Maximum Tension (Squeeze)
    
    # 4. FLOW (RSI Slope)
    # Is momentum building up smoothly?
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['flow_slope'] = df['rsi'].diff(3) # Short term momentum acceleration
    
    return df

def main():
    symbol = 'ALPACAUSDT'
    print(f"🎻 SYMPHONIC RECOGNITION: {symbol}")
    print("="*70)

    # Load Data
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    if not os.path.exists(h4_path):
        print("❌ 4H Data not found")
        return
        
    df = pd.read_parquet(h4_path)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # Calculate Harmony
    df = calculate_harmony_metrics(df)
    
    # Target Mapping (Midnight Check)
    df['hour'] = df['datetime'].dt.hour
    midnight = df[df['hour'] == 0].copy().reset_index(drop=True)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    rally_dates = set(rally_results.keys())
    midnight['is_rally'] = midnight['datetime'].dt.date.isin(rally_dates)
    
    print(f"Analyzing {len(midnight)} Daily Cycles for Melodic Signatures...")
    
    # RECOGNITION LOOP
    # We are not brute forcing random thresholds.
    # We are looking for a SPECIFIC MELODY:
    # "Rhythmic (Low CV) + Confident (High Texture) + Tense (Low Tension Score)"
    
    # Let's define the "Melody" thresholds dynamically
    
    # Melody A: "The Calm Before Storm" (Quiet Confidence)
    # Rhythm < 0.5 (Steady volume)
    # Texture > 0.5 (Body dominant)
    # Tension < 1.2 (Near max squeeze)
    
    # Melody B: "The Crescendo" (Building Up)
    # Flow Slope > 0 (RSI Rising)
    # Rhythm < 0.8 (Not chaotic yet)
    # Texture > 0.4
    
    melodies = [
        ("Calm Before Storm", {'rhythm_max': 0.5, 'texture_min': 0.5, 'tension_max': 1.5}),
        ("Silent Confidence", {'rhythm_max': 0.4, 'texture_min': 0.6, 'tension_max': 2.0}),
        ("Tense Wait",        {'rhythm_max': 0.6, 'texture_min': 0.4, 'tension_max': 1.1}), # Extreme squeeze
    ]
    
    found_melody = False
    
    for name, m in melodies:
        mask = (
            (midnight['rhythm_cv'] <= m['rhythm_max']) &
            (midnight['texture_confidence'] >= m['texture_min']) &
            (midnight['tension_score'] <= m['tension_max'])
        )
        
        hits = midnight[mask & midnight['is_rally']].shape[0]
        fails = midnight[mask & ~midnight['is_rally']].shape[0]
        total = hits + fails
        
        if total > 0:
            prec = hits/total*100
            print(f"🎵 Pattern '{name}': {hits}/{total} ({prec:.1f}%)")
            if prec == 100 and hits > 0:
                print(f"   💎 PERFECT HARMONY FOUND!")
                found_melody = True
                
    # If predefined melodies fail, let's "Listen" (Scan) for the best one
    if not found_melody:
        print("\n👂 Listening for unique ALPACA signatures...")
        best_p = 0
        best_sig = ""
        
        # Scan Texture & Rhythm Space
        for tex in [0.4, 0.5, 0.6]:
            for rhy in [0.4, 0.5, 0.6]:
                 mask = (
                     (midnight['texture_confidence'] >= tex) &
                     (midnight['rhythm_cv'] <= rhy)
                 )
                 hits = midnight[mask & midnight['is_rally']].shape[0]
                 fails = midnight[mask & ~midnight['is_rally']].shape[0]
                 total = hits+fails
                 if total > 0:
                     p = hits/total*100
                     if p > best_p and hits > 0:
                         best_p = p
                         best_sig = f"Confidence>={tex}, Rhythm<={rhy}"
        
        print(f"Best Improvisation: {best_sig} -> {best_p:.1f}%")

if __name__ == "__main__":
    main()
