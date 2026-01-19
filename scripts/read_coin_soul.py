"""
Coin Soul Reader - Multi-Timeframe Rhythm Analysis
==================================================
Reads the soul, rhythm, and harmony of Diamond formations.
Not just metrics - the CHARACTER of the movement.
"""

import sys
import os
import pandas as pd
import numpy as np
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def read_rhythm(df, window_size=7):
    """Analyze the rhythm and pattern of price movement."""
    rhythm = {
        'tempo': [],  # Acceleration/deceleration
        'harmony': [],  # Consistency
        'intensity': [],  # Strength
        'pattern': []  # Character
    }
    
    for i in range(window_size, len(df)):
        window = df.iloc[i-window_size:i]
        
        # Tempo: Is momentum accelerating?
        price_changes = window['close'].pct_change()
        tempo = 'ACCELERATING' if price_changes.iloc[-1] > price_changes.mean() else 'DECELERATING'
        
        # Harmony: Are indicators aligned?
        rsi_up = window['rsi'].iloc[-1] > window['rsi'].iloc[0]
        price_up = window['close'].iloc[-1] > window['close'].iloc[0]
        vol_up = window['volume'].iloc[-1] > window['volume'].mean()
        harmony = 'ALIGNED' if (rsi_up == price_up == vol_up) else 'DIVERGENT'
        
        # Intensity: How strong is the movement?
        volatility = window['close'].std() / window['close'].mean()
        intensity = 'HIGH' if volatility > 0.05 else ('MEDIUM' if volatility > 0.02 else 'LOW')
        
        # Pattern: What's the character?
        consecutive_ups = (price_changes > 0).sum()
        if consecutive_ups >= window_size * 0.8:
            pattern = 'STEADY_CLIMB'
        elif consecutive_ups <= window_size * 0.2:
            pattern = 'STEADY_FALL'
        elif window['close'].iloc[-1] > window['close'].iloc[0]:
            pattern = 'VOLATILE_RISE'
        else:
            pattern = 'VOLATILE_FALL'
        
        rhythm['tempo'].append(tempo)
        rhythm['harmony'].append(harmony)
        rhythm['intensity'].append(intensity)
        rhythm['pattern'].append(pattern)
    
    return rhythm

def read_coin_soul(symbol, diamond_event_time, diamond_start_time):
    """Deep soul reading of a single Diamond formation."""
    print(f"\n{'='*80}")
    print(f"🔮 READING THE SOUL OF {symbol}")
    print(f"Diamond Event: {diamond_event_time[:10]}")
    print(f"{'='*80}")
    
    # Load all three timeframes
    paths = {
        '1w': coin_cell_paths.get_history_file(symbol, '1w'),
        '1d': coin_cell_paths.get_history_file(symbol, '1d'),
        '4h': coin_cell_paths.get_history_file(symbol, '4h')
    }
    
    data = {}
    for tf, path in paths.items():
        if path.exists():
            df = pd.read_parquet(path).sort_values('timestamp')
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['rsi'] = calculate_rsi(df['close'])
            data[tf] = df
    
    if '1d' not in data:
        print("❌ No daily data available")
        return None
    
    diamond_time = pd.to_datetime(diamond_start_time)
    
    # === WEEKLY SOUL ===
    print(f"\n📅 WEEKLY TIMEFRAME - The Foundation")
    print("-" * 80)
    
    if '1w' in data:
        df_w = data['1w']
        # Find the week of Diamond
        week_row = df_w[df_w['datetime'] <= diamond_time].iloc[-1] if len(df_w[df_w['datetime'] <= diamond_time]) > 0 else None
        
        if week_row is not None:
            week_idx = df_w[df_w['datetime'] == week_row['datetime']].index[0]
            if week_idx >= 4:
                last_4_weeks = df_w.iloc[week_idx-3:week_idx+1]
                
                weekly_soul = {
                    'trend': 'BULL' if last_4_weeks['close'].iloc[-1] > last_4_weeks['close'].iloc[0] else 'BEAR',
                    'rsi_zone': 'HOT' if week_row['rsi'] > 65 else ('WARM' if week_row['rsi'] > 50 else 'COLD'),
                    'momentum': last_4_weeks['close'].pct_change().mean() * 100,
                    'character': 'EXPLOSIVE' if last_4_weeks['close'].std() / last_4_weeks['close'].mean() > 0.15 else 'STEADY'
                }
                
                print(f"Foundation Trend: {weekly_soul['trend']}")
                print(f"Temperature: {weekly_soul['rsi_zone']} (RSI: {week_row['rsi']:.1f})")
                print(f"Weekly Momentum: {weekly_soul['momentum']:+.1f}%")
                print(f"Character: {weekly_soul['character']}")
    
    # === DAILY SOUL (7 days before Diamond) ===
    print(f"\n📊 DAILY TIMEFRAME - The Rhythm")
    print("-" * 80)
    
    df_d = data['1d']
    sig_date = diamond_time - timedelta(days=1)
    sig_rows = df_d[df_d['datetime'].dt.date == sig_date.date()]
    
    if not sig_rows.empty:
        sig_idx = sig_rows.index[0]
        
        if sig_idx >= 7:
            week_before = df_d.iloc[sig_idx-6:sig_idx+1]
            
            # Analyze the 7-day dance
            daily_dance = {
                'opening_rsi': week_before['rsi'].iloc[0],
                'closing_rsi': week_before['rsi'].iloc[-1],
                'rsi_journey': week_before['rsi'].tolist(),
                'price_journey': ((week_before['close'] / week_before['close'].iloc[0] - 1) * 100).tolist(),
                'vol_pattern': week_before['volume'].tolist()
            }
            
            # Describe the dance
            rsi_movement = daily_dance['closing_rsi'] - daily_dance['opening_rsi']
            price_movement = daily_dance['price_journey'][-1]
            
            print(f"7-Day Journey:")
            print(f"  RSI: {daily_dance['opening_rsi']:.1f} → {daily_dance['closing_rsi']:.1f} ({rsi_movement:+.1f})")
            print(f"  Price: {price_movement:+.1f}%")
            print(f"\nDaily Bars (last 7 days):")
            for i, (date, rsi, price_chg) in enumerate(zip(
                week_before['datetime'].dt.strftime('%m-%d'),
                daily_dance['rsi_journey'],
                daily_dance['price_journey']
            )):
                bar = '█' * int(rsi / 10)
                print(f"  {date}: {bar} RSI:{rsi:5.1f} Price:{price_chg:+6.1f}%")
            
            # Rhythm analysis
            rhythm_desc = []
            if rsi_movement > 15:
                rhythm_desc.append("SURGING momentum")
            elif rsi_movement < -15:
                rhythm_desc.append("FADING momentum")
            else:
                rhythm_desc.append("STEADY momentum")
            
            if price_movement > 20:
                rhythm_desc.append("EXPLOSIVE price action")
            elif price_movement < -20:
                rhythm_desc.append("COLLAPSING price action")
            else:
                rhythm_desc.append("CONTROLLED price action")
            
            print(f"\n🎵 Rhythm: {' + '.join(rhythm_desc)}")
    
    # === 4H SOUL (last 48h before Diamond) ===
    print(f"\n⏰ 4H TIMEFRAME - The Heartbeat")
    print("-" * 80)
    
    if '4h' in data:
        df_4h = data['4h']
        pre_diamond = df_4h[df_4h['datetime'] < diamond_time]
        
        if len(pre_diamond) >= 12:  # Last 48h (12 bars)
            last_48h = pre_diamond.iloc[-12:]
            
            # Heartbeat analysis
            heartbeat = {
                'pulses': [],
                'intensity': []
            }
            
            print(f"Last 48 Hours (12 bars):")
            for i, row in last_48h.iterrows():
                pulse_strength = row['close'].pct_change() if i > last_48h.index[0] else 0
                heartbeat['pulses'].append(pulse_strength)
                
                # Visual pulse
                if abs(pulse_strength) > 0.05:
                    pulse_icon = '💥' if pulse_strength > 0 else '📉'
                elif abs(pulse_strength) > 0.02:
                    pulse_icon = '📈' if pulse_strength > 0 else '📊'
                else:
                    pulse_icon = '➖'
                
                print(f"  {row['datetime'].strftime('%m-%d %H:%M')}: {pulse_icon} {pulse_strength*100:+5.1f}% | RSI:{row['rsi']:5.1f}")
            
            # Describe heartbeat
            avg_pulse = np.mean([abs(p) for p in heartbeat['pulses']])
            if avg_pulse > 0.05:
                beat_desc = "RACING (high volatility)"
            elif avg_pulse > 0.02:
                beat_desc = "STRONG (active)"
            else:
                beat_desc = "CALM (stable)"
            
            print(f"\n❤️ Heartbeat: {beat_desc}")
    
    print(f"\n{'='*80}")
    print(f"✨ SOUL SUMMARY")
    print(f"{'='*80}")
    print(f"This Diamond emerged from a coin that was...")
    print(f"Weekly: Building foundation")
    print(f"Daily: Dancing through momentum")
    print(f"4H: Pulsing with life")
    print(f"\n🔮 The spirit of {symbol} spoke through movement, and Diamond formed.")

if __name__ == "__main__":
    # Read PEPEUSDT's Diamond souls
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT event_time, raw_data FROM rallies 
        WHERE symbol = 'PEPEUSDT' AND tier = 'DIAMOND'
        AND event_time >= '2026-01-01'
        ORDER BY event_time
        LIMIT 2
    """)
    diamonds = cursor.fetchall()
    conn.close()
    
    for event_time, raw_data in diamonds:
        raw = json.loads(raw_data)
        read_coin_soul('PEPEUSDT', event_time, raw['start_time'])
