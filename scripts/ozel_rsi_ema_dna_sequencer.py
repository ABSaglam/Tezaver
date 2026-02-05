#!/usr/bin/env python3
"""
DNA SEQUENCER V6: INDEPENDENT TRIGGERS & ARCHETYPE OPTIMIZATION
---------------------------------------------------------------
This script acts as a 'Trading Strategy Engine' for each coin.
It iterates through all historical data (pre-2026) to find the best configuration
of TRIGGERS and FILTERS for each RALLY ARCHETYPE.

Input: Coin History (15m, 1h, 4h, 1d)
Output: dna_manifest_v6.json (Map of Symbol -> List[Strategies])
"""

import pandas as pd
import numpy as np
import os
import json
import warnings
import itertools
from datetime import timedelta

# Suppress warnings
warnings.filterwarnings("ignore")

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
OUTPUT_MANIFEST = "dna_manifest_v6.json"
EXCLUDE_YEAR = 2026

# ==========================================
# 🧬 THE GENE POOL (SEARCH SPACE)
# ==========================================
GENES = {
    'trigger_level': [
        {'type': 'CROSS_UP', 'val': 50, 'name': 'RSI>50'},
        {'type': 'CROSS_UP', 'val': 55, 'name': 'RSI>55'},
        {'type': 'CROSS_UP', 'val': 60, 'name': 'RSI>60'},
        {'type': 'CROSS_UP', 'val': 65, 'name': 'RSI>65'},
        {'type': 'CROSS_UP', 'val': 70, 'name': 'RSI>70'},
        {'type': 'CROSS_UP', 'val': 30, 'name': 'RSI>30 (Dip)'}, # Oversold bounce
    ],
    'trend_filter': [
        'OFF', 
        '4H_EMA',  # Close > 4H EMA21
        '1H_EMA',  # Close > 1H EMA21
        'RIBBON'   # RSI-EMA Ribbon Aligned (20 > 55)
    ],
    'vol_filter': [
        'OFF',
        'VIDX_1.5', # v_idx > 1.5
        'VIDX_2.0', # v_idx > 2.0
        'VIDX_3.0', # v_idx > 3.0
    ],
    'adx_filter': [
        'OFF',
        'ADX_20', # ADX > 20
        'ADX_30'  # ADX > 30 (Strong Trend)
    ],
    'time_filter': [
        'OFF',
        'NO_WEEKEND', # Mon-Fri only
    ]
}

# ==========================================
# 📐 ARCHETYPE DEFINITIONS (TARGETS)
# ==========================================
def classify_win(row):
    """
    Classifies a winning trade into an archetype based on its price action.
    This is a simplified version of the full classifier logic.
    """
    gain = row.get('max_gain', 0)
    bars_to_peak = row.get('bars_to_peak', 10)
    pullbacks = row.get('pullbacks', 0)
    vol_expansion = row.get('vol_expansion', 1.0)
    rsi_peak = row.get('rsi_peak', 50)
    
    # 1. SUPERNOVA: Fast, Explosive
    speed_ratio = (gain / bars_to_peak) if bars_to_peak > 0 else 0
    if speed_ratio > 1.5 and pullbacks <= 1:
        return 'SUPERNOVA'

    # 2. GUILLOTINE: V-Shape Reversal (usually implies low RSI start)
    # We check trigger RSI in the main loop, here we verify the bounce
    if speed_ratio > 2.0 and bars_to_peak < 10:
        return 'GUILLOTINE' # or Spike

    # 3. GRIND: Slow, steady
    if bars_to_peak > 20 and pullbacks >= 2:
        return 'GRIND'

    # 4. BREAKOUT: Volatility Expansion
    if vol_expansion > 3.0:
        return 'BREAKOUT'

    # Default
    return 'GENERIC'

# ==========================================
# 🛠️ CORE FUNCTIONS
# ==========================================

def load_data(symbol):
    try:
        path_15m = f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet"
        path_1h = f"{COIN_CELLS_DIR}/{symbol}/data/history_1h.parquet"
        path_4h = f"{COIN_CELLS_DIR}/{symbol}/data/history_4h.parquet"
        path_1d = f"{COIN_CELLS_DIR}/{symbol}/data/history_1d.parquet"

        if not os.path.exists(path_15m): return None

        df_15m = pd.read_parquet(path_15m)
        df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
        df_15m.set_index('dt', inplace=True)
        df_15m = df_15m[~df_15m.index.duplicated(keep='last')].sort_index()
        
        # Filter 2026
        df_15m = df_15m[df_15m.index.year < EXCLUDE_YEAR]
        if df_15m.empty: return None

        # Determine Trend Context (resample/merge simulation)
        # For speed: we'll calculate everything on 15m but use approximation for 4H/1D metrics to avoid heavy merges
        # BETTER: Just compute what is needed.

        # 1. Indicators
        df_15m['ema21'] = df_15m['close'].ewm(span=21, adjust=False).mean()
        
        # RSI
        delta = df_15m['close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/11, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/11, adjust=False).mean().replace(0, 0.001)
        df_15m['rsi'] = 100 - (100 / (1 + (gain / loss)))
        df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()

        # Ribbon (Simplified Check: 20 vs 55 on RSI-EMA)
        df_15m['rsi_rib_20'] = df_15m['rsi_ema'].ewm(span=20, adjust=False).mean()
        df_15m['rsi_rib_55'] = df_15m['rsi_ema'].ewm(span=55, adjust=False).mean()
        df_15m['ribbon_aligned'] = df_15m['rsi_rib_20'] > df_15m['rsi_rib_55']

        # Volume Metrics
        df_15m['vol_ma20'] = df_15m['volume'].rolling(20).mean()
        df_15m['v_idx'] = df_15m['volume'] / (df_15m['vol_ma20'].replace(0, 0.001))

        # 4H EMA Trend Approximation (Resampling 15m EMA is tricky, better to load 4H if possible, or approx with 15m*16)
        # Approx: EMA 336 on 15m roughly tracks EMA 21 on 4H (21 * 16 = 336)
        df_15m['ema_4h_approx'] = df_15m['close'].ewm(span=336, adjust=False).mean()
        df_15m['ema_1h_approx'] = df_15m['close'].ewm(span=84, adjust=False).mean() # 21 * 4

        # ADX Approximation (1D) -> 1D ADX maps to ~96 bars on 15m.
        # We will skip exact ADX for speed and use Volatility (ATR) instead for "Strength"
        # Or calculate simplified ADX on 15m with longer period
        
        # Day of Week
        df_15m['weekday'] = df_15m.index.dayofweek # 0=Mon, 6=Sun

        return df_15m
    except:
        return None

def find_best_strategies(symbol, df_15m):
    strategies = []
    
    # Pre-calculate triggers for all levels to speed up
    trigger_masks = {}
    for trig in GENES['trigger_level']:
        t_val = trig['val']
        # Cross UP logic
        cond = df_15m['rsi_ema'] > t_val
        mask = (cond) & (~cond.shift(1).fillna(False))
        trigger_masks[trig['name']] = mask

    # Get all potential signal indices (union of all triggers)
    all_indices = set()
    for name, mask in trigger_masks.items():
        all_indices.update(np.where(mask)[0])
    sorted_indices = sorted(list(all_indices))
    
    if not sorted_indices: return []

    # 1. EVALUATE RAW SIGNALS (Harvest Context)
    # ------------------------------------------
    raw_signals = []
    
    for idx in sorted_indices:
        if idx >= len(df_15m) - 50: continue # Skip if no future

        row = df_15m.iloc[idx]
        context = {
            'idx': idx,
            '4h_trend': row['close'] > row['ema_4h_approx'],
            '1h_trend': row['close'] > row['ema_1h_approx'],
            'ribbon': bool(row['ribbon_aligned']),
            'v_idx': row['v_idx'],
            'is_weekend': row['weekday'] >= 5,
        }

        # Determine result (Future 49 bars)
        entry_price = row['close']
        future_window = df_15m.iloc[idx+1 : idx+50]
        max_price = future_window['high'].max()
        max_gain = ((max_price - entry_price) / entry_price) * 100
        
        # Classify Archetype (Roughly)
        # Bars to peak
        peak_idx = future_window['high'].idxmax()
        bars_to_peak = (peak_idx - df_15m.index[idx]).seconds // 900 # approx bars
        
        context['max_gain'] = max_gain
        context['archetype'] = 'GENERIC'
        
        # Simple classifier
        if max_gain > 5:
            if max_gain > 20 and bars_to_peak < 12: context['archetype'] = 'SUPERNOVA'
            elif max_gain > 15 and bars_to_peak > 30: context['archetype'] = 'GRIND'
            elif row['v_idx'] > 3.0: context['archetype'] = 'BREAKOUT'
            elif row['rsi_ema'] < 35: context['archetype'] = 'GUILLOTINE'
            elif row['rsi_ema'] > 70: context['archetype'] = 'SURFER'
        
        # Determine which triggers fired here
        fired_triggers = []
        for t_name, mask in trigger_masks.items():
            if mask[idx]: fired_triggers.append(t_name)
        
        context['triggers'] = fired_triggers
        raw_signals.append(context)

    # 2. RUN GENETIC OPTIMIZATION
    # ---------------------------
    # We want to find the best ruleset for EACH archetype.
    
    target_archetypes = ['SUPERNOVA', 'GRIND', 'BREAKOUT', 'GUILLOTINE', 'GENERIC'] #, 'SURFER']
    
    manifest_entries = []

    for target_arch in target_archetypes:
        best_rules = None
        best_score = 0
        
        # Define relevant Trigger Candidates based on Archetype Logic
        # (Heuristic pruning to save time)
        candidate_triggers = GENES['trigger_level']
        if target_arch == 'GUILLOTINE':
            candidate_triggers = [t for t in GENES['trigger_level'] if t['val'] <= 35]
        elif target_arch == 'SUPERNOVA':
            candidate_triggers = [t for t in GENES['trigger_level'] if t['val'] >= 60]
        
        # Iterate Combinations
        for trig in candidate_triggers:
            for trend in GENES['trend_filter']:
                for vol in GENES['vol_filter']:
                    for time_f in GENES['time_filter']:
                        
                        # Apply Filters per Signal
                        valid_signals = []
                        wins = 0
                        
                        for s in raw_signals:
                            if trig['name'] not in s['triggers']: continue
                            
                            # Trend Filter
                            if trend == '4H_EMA' and not s['4h_trend']: continue
                            if trend == '1H_EMA' and not s['1h_trend']: continue
                            if trend == 'RIBBON' and not s['ribbon']: continue
                            
                            # Vol Filter
                            if vol == 'VIDX_1.5' and s['v_idx'] < 1.5: continue
                            if vol == 'VIDX_2.0' and s['v_idx'] < 2.0: continue
                            if vol == 'VIDX_3.0' and s['v_idx'] < 3.0: continue
                            
                            # Time Filter
                            if time_f == 'NO_WEEKEND' and s['is_weekend']: continue
                            
                            valid_signals.append(s)
                            if s['max_gain'] >= 5.0: wins += 1 # Bronze+ Win
                        
                        total = len(valid_signals)
                        if total < 15: continue # Too few samples
                        
                        win_rate = (wins / total) * 100
                        if win_rate < 25.0: continue # Min acceptable performance
                        
                        # Calculate Archetype Specific Score
                        # How many of the wins were actually the target archetype?
                        arch_wins = sum(1 for s in valid_signals if s['max_gain'] >= 5.0 and s['archetype'] == target_arch)
                        arch_rate = (arch_wins / total) * 100
                        
                        # Optimization Score: 
                        # We want high overall win rate, but specifically high yield of the target archetype.
                        score = win_rate * np.log1p(total) + (arch_rate * 2)
                        
                        if score > best_score:
                            best_score = score
                            best_rules = {
                                'name': f"{target_arch}_HUNTER",
                                'target': target_arch,
                                'trigger': trig['name'],
                                'trend': trend,
                                'vol': vol,
                                'time': time_f,
                                'win_rate': round(win_rate, 2),
                                'total_signals': total
                            }
        
        if best_rules:
            manifest_entries.append(best_rules)
    
    # Filter redundant strategies (keep top 3 distinct ones)
    # Sort by Win Rate
    manifest_entries.sort(key=lambda x: x['win_rate'], reverse=True)
    return manifest_entries[:3] # Keep top 3 best strategies per coin

def run_sequencer():
    print(f"🧬 DNA SEQUENCER V6 BAŞLATILIYOR...")
    print(f"Hedef: {OUTPUT_MANIFEST}")
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    # symbols = symbols[:50] # Limit for testing if needed
    
    manifest = {}
    
    processed = 0
    for symbol in symbols:
        df = load_data(symbol)
        if df is None: continue
        
        strategies = find_best_strategies(symbol, df)
        if strategies:
            manifest[symbol] = strategies
            # print(f"✅ {symbol}: Found {len(strategies)} strategies. Top: {strategies[0]['name']} ({strategies[0]['win_rate']}%)")
        
        processed += 1
        print(f"Sequencing DNA: {processed}/{len(symbols)} coins analyzed...", end='\r')
    
    print("\n\n✨ SEQUENCING COMPLETED.")
    print(f"Total Coins with optimized DNA: {len(manifest)}")
    
    with open(OUTPUT_MANIFEST, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"Manifest saved to {OUTPUT_MANIFEST}")
    
    # Show example
    if manifest:
        example_sym = list(manifest.keys())[0]
        print(f"\nExample ({example_sym}):")
        print(json.dumps(manifest[example_sym], indent=2))

if __name__ == "__main__":
    run_sequencer()
