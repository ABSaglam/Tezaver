"""
Comprehensive DSG Anomaly Detector
===================================
Detects and categorizes unpredictable rally patterns across all anomaly types.
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

def detect_flash_crash(symbol, start_time, lookback_bars=10):
    """Detect flash crash before rally (RELAXED criteria)."""
    try:
        path = coin_cell_paths.get_history_file(symbol, '15m')
        if not path.exists():
            return False, None
        
        df = pd.read_parquet(path)
        df = df.sort_values('timestamp')
        
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        df['ts_diff'] = (df['timestamp'] - start_ts).abs()
        start_idx = df['ts_diff'].idxmin()
        
        if start_idx < lookback_bars:
            return False, None
        
        window = df.iloc[max(0, start_idx - lookback_bars):start_idx]
        
        for idx, row in window.iterrows():
            # Single bar crash (15%+)
            if idx > 0:
                prev_close = df.loc[idx - 1, 'close']
                current_low = row['low']
                drop = ((prev_close - current_low) / prev_close) * 100
                
                if drop > 15:
                    return True, f"FLASH_CRASH_{drop:.1f}%"
            
            # Multi-bar crash (25%+ in 3 bars)
            if idx >= 2:
                three_bars_ago_close = df.loc[idx - 2, 'close']
                current_low = row['low']
                multi_drop = ((three_bars_ago_close - current_low) / three_bars_ago_close) * 100
                
                if multi_drop > 25:
                    return True, f"MULTI_BAR_CRASH_{multi_drop:.1f}%"
        
        return False, None
        
    except:
        return False, None

def detect_single_tower(symbol, start_time, rally_data):
    """Detect single tower / balina alımı pattern."""
    try:
        path = coin_cell_paths.get_history_file(symbol, '15m')
        if not path.exists():
            return False, None
        
        df = pd.read_parquet(path)
        df = df.sort_values('timestamp')
        
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        df['ts_diff'] = (df['timestamp'] - start_ts).abs()
        start_idx = df['ts_diff'].idxmin()
        
        if start_idx < 10:
            return False, None
        
        # Get rally info
        rally_low = rally_data.get('low', 0)
        rally_high = rally_data.get('high', 0)
        rally_gain = rally_data.get('gain', 0)
        
        if rally_gain < 15:  # Too small to be interesting
            return False, None
        
        # Check first 3 bars of rally
        rally_window = df.iloc[start_idx:start_idx+3]
        
        if len(rally_window) < 1:
            return False, None
        
        # First bar metrics
        first_bar = rally_window.iloc[0]
        first_bar_gain = ((first_bar['high'] - first_bar['low']) / first_bar['low']) * 100
        
        # Check if first bar captures 70%+ of total gain
        total_rally_range = rally_high - rally_low
        first_bar_range = first_bar['high'] - first_bar['low']
        
        if total_rally_range > 0:
            first_bar_contribution = (first_bar_range / total_rally_range) * 100
            
            if first_bar_contribution > 70 and first_bar_gain > 15:
                # Check pre-rally calmness
                pre_window = df.iloc[max(0, start_idx-10):start_idx]
                if not pre_window.empty:
                    pre_volatility = ((pre_window['high'] - pre_window['low']) / pre_window['low'] * 100).mean()
                    
                    if pre_volatility < 5:  # Very calm before
                        return True, f"SINGLE_TOWER_{first_bar_gain:.1f}%"
        
        return False, None
        
    except:
        return False, None

def detect_liquidity_manipulation(symbol, start_time, rally_data):
    """Detect low liquidity manipulation."""
    try:
        path = coin_cell_paths.get_history_file(symbol, '15m')
        if not path.exists():
            return False, None
        
        df = pd.read_parquet(path)
        df = df.sort_values('timestamp')
        
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        df['ts_diff'] = (df['timestamp'] - start_ts).abs()
        start_idx = df['ts_diff'].idxmin()
        
        if start_idx < 20:
            return False, None
        
        # Calculate normal volume
        pre_window = df.iloc[max(0, start_idx-20):start_idx]
        normal_volume = pre_window['volume'].mean()
        
        # Rally start volume
        rally_bar = df.iloc[start_idx]
        rally_volume = rally_bar['volume']
        
        if normal_volume == 0 or pd.isna(normal_volume):
            return False, None
        
        volume_spike = rally_volume / normal_volume
        rally_gain = rally_data.get('gain', 0)
        
        # Low liquidity manipulation: normal volume very low + huge spike
        if normal_volume < 50000 and volume_spike > 50 and rally_gain > 20:
            return True, f"LOW_LIQ_{volume_spike:.0f}x_VOL"
        
        return False, None
        
    except:
        return False, None

def detect_bot_error(symbol, start_time, rally_data):
    """Detect bot error / flash order (spike + immediate reversal)."""
    try:
        path = coin_cell_paths.get_history_file(symbol, '15m')
        if not path.exists():
            return False, None
        
        df = pd.read_parquet(path)
        df = df.sort_values('timestamp')
        
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        df['ts_diff'] = (df['timestamp'] - start_ts).abs()
        start_idx = df['ts_diff'].idxmin()
        
        # Check if rally reversed quickly
        rally_bars = rally_data.get('bars', 0)
        rally_gain = rally_data.get('gain', 0)
        
        if rally_bars < 5 and rally_gain > 30:
            # Check if it fell back sharply
            if start_idx + rally_bars + 3 < len(df):
                peak_bar = df.iloc[start_idx + rally_bars]
                aftermath = df.iloc[start_idx + rally_bars:start_idx + rally_bars + 3]
                
                if not aftermath.empty:
                    reversal = ((peak_bar['high'] - aftermath['close'].min()) / peak_bar['high']) * 100
                    
                    if reversal > 50:  # Lost 50%+ of gain immediately
                        return True, f"BOT_ERROR_{reversal:.0f}%_REVERSAL"
        
        return False, None
        
    except:
        return False, None

def run_comprehensive_detection():
    print("=" * 80)
    print(f"🔍 COMPREHENSIVE ANOMALY DETECTION")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Load all DSG rallies
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM rallies WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER')"
    df_rallies = pd.read_sql_query(query, conn)
    conn.close()
    
    total = len(df_rallies)
    print(f"\nTotal DSG Rallies: {total}\n")
    
    results = []
    
    for i, row in df_rallies.iterrows():
        if (i + 1) % 2000 == 0:
            print(f"Progress: {i+1}/{total} analyzed...")
        
        raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
        symbol = raw_data['symbol']
        start_time = raw_data['start_time']
        tier = row['tier']
        
        rally_info = {
            'low': raw_data.get('low', 0),
            'high': raw_data.get('high', 0),
            'gain': raw_data.get('gain', 0),
            'bars': raw_data.get('bars', 0)
        }
        
        # Run all detectors
        anomalies = []
        
        is_flash, flash_detail = detect_flash_crash(symbol, start_time)
        if is_flash:
            anomalies.append(flash_detail)
        
        is_tower, tower_detail = detect_single_tower(symbol, start_time, rally_info)
        if is_tower:
            anomalies.append(tower_detail)
        
        is_liq, liq_detail = detect_liquidity_manipulation(symbol, start_time, rally_info)
        if is_liq:
            anomalies.append(liq_detail)
        
        is_bot, bot_detail = detect_bot_error(symbol, start_time, rally_info)
        if is_bot:
            anomalies.append(bot_detail)
        
        # Categorize
        if anomalies:
            category = "ANOMALY"
            anomaly_types = ", ".join(anomalies)
        else:
            category = "CLEAN"
            anomaly_types = "NONE"
        
        results.append({
            'tier': tier,
            'category': category,
            'anomaly_types': anomaly_types
        })
    
    df = pd.DataFrame(results)
    
    # Statistics
    print("\n" + "=" * 80)
    print("📊 ANOMALY DETECTION RESULTS")
    print("=" * 80)
    
    for tier in ['DIAMOND', 'GOLD', 'SILVER']:
        df_tier = df[df['tier'] == tier]
        if df_tier.empty:
            continue
        
        clean_count = len(df_tier[df_tier['category'] == 'CLEAN'])
        anomaly_count = len(df_tier[df_tier['category'] == 'ANOMALY'])
        total_tier = len(df_tier)
        
        clean_pct = (clean_count / total_tier) * 100
        anomaly_pct = (anomaly_count / total_tier) * 100
        
        print(f"\n{'─' * 80}")
        print(f"💎 {tier}")
        print(f"{'─' * 80}")
        print(f"Total: {total_tier}")
        print(f"CLEAN: {clean_count} ({clean_pct:.1f}%)")
        print(f"ANOMALY: {anomaly_count} ({anomaly_pct:.1f}%)")
        
        # Breakdown of anomaly types
        anomalies = df_tier[df_tier['category'] == 'ANOMALY']
        if not anomalies.empty:
            print(f"\n🔹 ANOMALY BREAKDOWN:")
            
            # Count each anomaly type
            flash_count = anomalies['anomaly_types'].str.contains('FLASH_CRASH|MULTI_BAR_CRASH').sum()
            tower_count = anomalies['anomaly_types'].str.contains('SINGLE_TOWER').sum()
            liq_count = anomalies['anomaly_types'].str.contains('LOW_LIQ').sum()
            bot_count = anomalies['anomaly_types'].str.contains('BOT_ERROR').sum()
            
            if flash_count > 0:
                print(f"   Flash Crash: {flash_count} ({flash_count/total_tier*100:.1f}%)")
            if tower_count > 0:
                print(f"   Single Tower: {tower_count} ({tower_count/total_tier*100:.1f}%)")
            if liq_count > 0:
                print(f"   Low Liquidity: {liq_count} ({liq_count/total_tier*100:.1f}%)")
            if bot_count > 0:
                print(f"   Bot Error: {bot_count} ({bot_count/total_tier*100:.1f}%)")
    
    # Overall summary
    print(f"\n{'═' * 80}")
    print(f"🌍 OVERALL SUMMARY")
    print(f"{'═' * 80}")
    
    total_clean = len(df[df['category'] == 'CLEAN'])
    total_anomaly = len(df[df['category'] == 'ANOMALY'])
    
    print(f"Total DSG Rallies: {len(df)}")
    print(f"CLEAN (Predictable): {total_clean} ({total_clean/len(df)*100:.1f}%)")
    print(f"ANOMALY (Unpredictable): {total_anomaly} ({total_anomaly/len(df)*100:.1f}%)")
    
    print("\n" + "=" * 80)
    print("✅ Anomaly Detection Complete")
    print("=" * 80)

if __name__ == "__main__":
    run_comprehensive_detection()
