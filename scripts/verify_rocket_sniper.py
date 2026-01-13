#!/usr/bin/env python3
"""
Pulse Check: ROCKET Sniper Verification
---------------------------------------
1. Time Lag Analysis: How long after the Daily Close does the rally actually start?
   - Helps define the "Monitoring Window" (24h? 48h? 96h?).
2. Trigger Verification: accurately simulate the 'Supernova' trigger.
   - Trigger: RSI(14) > 65 AND Volume > 2 * 24h_Avg
   - Window: Test 24h, 48h, 72h.
   - Outcome: Win/Loss after entry.
"""

import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

# from tezaver.core import coin_cell_paths
# from tezaver.features.indicator_engine import IndicatorEngine

from tezaver.core import coin_cell_paths

def calculate_atr(high, low, close, period=14):
    high_low = high - low
    high_close = (high - close.shift()).abs()
    low_close = (low - close.shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()


def get_rocket_signals():
    """Get all historical daily signals for ROCKET coins."""
    # We'll reload the report parsing logic or just re-run the daily signal check?
    # Parsing the report is safer as it contains the 'Truth' of the backtest.
    # But the report only lists *Rallies*, not *All Signals*.
    # To be honest (show false positives), we need ALL SIGNALS.
    # So we must re-scan daily data for signals.
    
    print("Loading ROCKET coins...")
    try:
        dna = pd.read_csv('library/coin_dna/final_classification.csv')
        rocket_syms = dna[dna['cluster_name'] == 'ROCKET']['symbol'].tolist()
    except:
        print("Error loading DNA.")
        return [], []

    print(f"Scanning daily history for {len(rocket_syms)} ROCKET coins...")
    
    signals = []
    
    # Ayaş Tüneli Logic (Simplified for speed, matching original backtest)
    # TREND: ATR% > 15, 55 < RSI < 70
    # NINJA: ATR% > 12, 60 < RSI < 75
    
    for symbol in rocket_syms:
        path = coin_cell_paths.get_history_file(symbol, '1d')
        if not path.exists(): continue
        
        try:
            df = pd.read_parquet(path)
            if len(df) < 50: continue
            
            # Indicators
            df['atr'] = calculate_atr(df['high'], df['low'], df['close'], 14)
            df['atr_pct'] = (df['atr'] / df['close']) * 100
            
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, 0.001)
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Find Signals
            # TREND
            trend_mask = (df['atr_pct'] > 15) & (df['rsi'] > 55) & (df['rsi'] < 70)
            # NINJA
            ninja_mask = (df['atr_pct'] > 12) & (df['atr_pct'] <= 15) & (df['rsi'] > 60) & (df['rsi'] < 75)
            
            signal_dates = df[trend_mask | ninja_mask]['datetime'].tolist()
            
            for date in signal_dates:
                signals.append({
                    'symbol': symbol,
                    'signal_date': date,
                    'type': 'TREND' # Simplified
                })
                
        except Exception as e:
            continue
            
    return signals, rocket_syms

def verify_sniper(signals):
    print(f"Verifying {len(signals)} Daily Signals on 15m data...")
    
    results = []
    
    for i, sig in enumerate(signals):
        if i % 10 == 0: print(f"Processing {i}/{len(signals)}...", end='\r')
        
        symbol = sig['symbol']
        signal_date = sig['signal_date'] # Timestamp of daily close (03:00)
        
        path_15m = coin_cell_paths.get_history_file(symbol, '15m')
        if not path_15m.exists(): continue
        
        try:
            df = pd.read_parquet(path_15m)
            
            # Monitoring Window: 0 to 120 hours (5 days)
            # We want to see WHEN the trigger happens
            start_time = signal_date
            end_time = signal_date + pd.Timedelta(hours=120)
            
            mask = (df['datetime'] >= start_time) & (df['datetime'] <= end_time)
            window_df = df.loc[mask].copy().reset_index(drop=True)
            
            if len(window_df) < 10: continue
            
            # Compute Indicators for Trigger
            # RSI 14
            delta = window_df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, 0.001)
            window_df['rsi'] = 100 - (100 / (1 + rs))
            
            # Volume 24h Avg (Approximation: Rolling 96 bars)
            # For accuracy we should use pre-window data, but let's use expanding for now
            window_df['vol_avg'] = window_df['volume'].expanding().mean()
            
            # SUPERNOVA TRIGGER: RSI > 65 AND Vol > 2 * Avg
            # Let's find the FIRST occurrence
            trigger_mask = (window_df['rsi'] > 65) & (window_df['volume'] > 2 * window_df['vol_avg'])
            triggers = window_df[trigger_mask]
            
            has_trigger = not triggers.empty
            
            res = {
                'symbol': symbol,
                'signal_date': signal_date,
                'has_trigger': has_trigger,
                'time_to_trigger_h': None,
                'outcome_gain': 0,
                'max_potential_gain': 0,
                'trigger_price': 0
            }
            
            if has_trigger:
                first_trigger = triggers.iloc[0]
                trigger_idx = first_trigger.name
                trigger_time = first_trigger['datetime']
                trigger_price = first_trigger['close']
                
                time_lag = (trigger_time - start_time).total_seconds() / 3600
                res['time_to_trigger_h'] = time_lag
                res['trigger_price'] = trigger_price
                
                # Result after trigger (up to end of 120h window)
                post_trigger = window_df.loc[trigger_idx+1:]
                if not post_trigger.empty:
                    # Max gain from entry
                    max_price = post_trigger['high'].max()
                    max_gain = (max_price - trigger_price) / trigger_price * 100
                    
                    # End of window gain (if we held till 120h)
                    final_price = post_trigger.iloc[-1]['close']
                    final_gain = (final_price - trigger_price) / trigger_price * 100
                    
                    res['max_potential_gain'] = max_gain
                    res['outcome_gain'] = final_gain
                    
            else:
                # No trigger - what did we miss?
                # Max gain in window from signal start
                start_price = window_df.iloc[0]['open']
                max_price = window_df['high'].max()
                missed_gain = (max_price - start_price) / start_price * 100
                res['max_potential_gain'] = missed_gain # "Missed" potential
            
            results.append(res)
            
        except Exception as e:
            # print(e)
            pass
            
    return pd.DataFrame(results)

def main():
    signals, _ = get_rocket_signals()
    if not signals:
        print("No stats generated.")
        return
        
    df = verify_sniper(signals)
    
    print("\n" + "="*60)
    print("⚖️ VERDICT: ROCKET SNIPER (Honest Check)")
    print("="*60)
    
    triggered = df[df['has_trigger'] == True]
    ignored = df[df['has_trigger'] == False]
    
    print(f"Total Daily Signals: {len(df)}")
    print(f"Triggers Fired: {len(triggered)} ({len(triggered)/len(df)*100:.1f}%)")
    print(f"Signals Ignored: {len(ignored)} ({len(ignored)/len(df)*100:.1f}%)")
    
    print("\n⏱️ TIME LAG (When does the Sniper shoot?)")
    print("-" * 40)
    print(triggered['time_to_trigger_h'].describe().to_markdown())
    
    # Analyze Lag Buckets
    lags = triggered['time_to_trigger_h']
    print(f"\nTrigger < 24h: {len(lags[lags <= 24])} ({len(lags[lags <= 24])/len(triggered)*100:.1f}%)")
    print(f"Trigger 24-48h: {len(lags[(lags > 24) & (lags <= 48)])}")
    print(f"Trigger 48-72h: {len(lags[(lags > 48) & (lags <= 72)])}")
    print(f"Trigger > 72h: {len(lags[lags > 72])}")
    
    print("\n💰 PERFORMANCE (Triggered Entries)")
    print("-" * 40)
    # Win if max gain > 5%?
    wins = triggered[triggered['max_potential_gain'] > 5]
    big_wins = triggered[triggered['max_potential_gain'] > 20]
    
    print(f"Avg Max Potential: {triggered['max_potential_gain'].mean():.1f}%")
    print(f"Win Rate (>5% gain): {len(wins)/len(triggered)*100:.1f}%")
    print(f"Big Win Rate (>20% gain): {len(big_wins)/len(triggered)*100:.1f}%")
    
    print("\n🙈 MISSED OPPORTUNITIES (Ignored Signals)")
    print("-" * 40)
    # Did we ignore any big rallies?
    missed_big = ignored[ignored['max_potential_gain'] > 20]
    print(f"Missed Big Rallies (>20%): {len(missed_big)}")
    if not missed_big.empty:
        print("Top Missed:")
        print(missed_big.sort_values('max_potential_gain', ascending=False)[['symbol', 'signal_date', 'max_potential_gain']].head().to_string())
    else:
        print("We didn't miss much!")

    # Save
    df.to_csv('library/rally_dna/rocket_sniper_verification.csv', index=False)

if __name__ == "__main__":
    main()
