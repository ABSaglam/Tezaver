import sys
import os
sys.path.append(os.getcwd())
import pandas as pd
import numpy as np
import json

def generate_lockstate_profiles_v4():
    symbol = "ALGOUSDT"
    print(f"🧩 HIGH-RESOLUTION Lock-State Profiles (v4) for {symbol}")
    
    # Load Data
    df_w = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
    df_d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
    df_h4 = pd.read_parquet(f"coin_cells/{symbol}/data/history_4h.parquet")
    df_h1 = pd.read_parquet(f"coin_cells/{symbol}/data/history_1h.parquet")
    
    for df in [df_w, df_d, df_h4, df_h1]:
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        df.sort_index(inplace=True)
        
        # EMA
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # RSI Slope (3 periods)
        df['rsi'] = 100 - (100 / (1 + (df['close'].diff().where(df['close'].diff() > 0, 0).rolling(14).mean() / 
                                    (-df['close'].diff().where(df['close'].diff() < 0, 0)).rolling(14).mean().replace(0, 0.001))))
        df['rsi_slope'] = df['rsi'].diff(3)
        
        # Vol Trend
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['vol_trend'] = df['volume'].rolling(5).mean() / df['vol_ma']

    # 1. Faz (Phase)
    def get_phase(date):
        try:
            w = df_w[df_w.index <= date].iloc[-1]
            d = df_d[df_d.index <= date].iloc[-1]
            
            # Use Weekly Baseline
            if d['close'] < w['ema50']: return "erken"
            if w['rsi'] > 75: return "geç"
            if d['ema9'] > d['ema21'] > d['ema50']: return "olgun"
            return "eşik"
        except: return "belirsiz"

    # 2. Birikim (Accumulation)
    def get_accumulation(date):
        try:
            h1_all = df_h1[df_h1.index <= date].tail(48)
            def get_comp(row):
                emas = [row['ema9'], row['ema21'], row['ema50']]
                return (max(emas) / min(emas) - 1) * 100
            
            comps = h1_all.apply(get_comp, axis=1)
            curr_comp = comps.iloc[-1]
            min_comp = comps.min()
            
            # Trend of Squeeze
            if min_comp < 3.0 and comps.iloc[-1] < comps.iloc[-12]: return "taşmak üzere"
            if curr_comp < 6.0: return "bastırılmış"
            return "rahat"
        except: return "belirsiz"

    # 3. Uyum (Harmony)
    def get_harmony(date):
        try:
            d = df_d[df_d.index <= date].iloc[-1]
            h4 = df_h4[df_h4.index <= date].iloc[-1]
            
            # Directional Momentum Harmony
            d_momentum = d['rsi_slope'] > 0
            h4_momentum = h4['rsi_slope'] > 0
            d_price = d['close'] > d['ema9']
            
            score = sum([d_momentum, h4_momentum, d_price])
            if score == 3: return "itirazsız"
            if score >= 1: return "kısmi uyum"
            return "uyumsuz"
        except: return "belirsiz"

    # 4. Ritim (Tempo)
    def get_tempo(date):
        try:
            d_tail = df_d[df_d.index <= date].tail(5)
            # Volume consistency
            vol_std = d_tail['volume'].std() / d_tail['volume'].mean()
            price_acc = (d_tail['close'].iloc[-1] / d_tail['close'].iloc[0] - 1) * 100
            
            if abs(price_acc) > 15: return "aceleci"
            if vol_std < 0.4: return "dengeli"
            return "kesik"
        except: return "belirsiz"

    # 5. Hafıza (Context)
    def get_context(date):
        try:
            d_row = df_d[df_d.index <= date].iloc[-1]
            # Context of multi-month highs
            high_90d = df_d[df_d.index <= date].tail(90)['high'].max()
            if d_row['close'] > high_90d * 0.95: return "anlamlı"
            if d_row['close'] > high_90d * 0.70: return "tanıdık"
            return "anlamsız"
        except: return "belirsiz"

    target_days = df_d[df_d.index.year.isin([2023, 2024, 2025])].index
    profiles = {}
    
    print("Reprocessing...")
    for day in target_days:
        day_str = day.strftime('%Y-%m-%d')
        profiles[day_str] = {
            'faz': get_phase(day),
            'birikim': get_accumulation(day),
            'uyum': get_harmony(day),
            'ritim': get_tempo(day),
            'hafıza': get_context(day)
        }
    
    with open("data/algo_lockstate_profiles.json", "w") as f:
        json.dump(profiles, f, indent=2)
    print(f"✅ High-Res Profiles Saved.")

if __name__ == "__main__":
    generate_lockstate_profiles_v4()
