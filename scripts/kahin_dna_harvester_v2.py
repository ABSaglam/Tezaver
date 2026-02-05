import pandas as pd
import numpy as np
import glob
import os
import time

# 🏛️ KUTSİLER VE KONFİGÜRASYON
CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
OUTPUT_CSV = "/Users/alisaglam/TezaverMac/HAM_DNA_V01_2025.csv"
START_YEAR = 2025
END_YEAR = 2025

def calculate_rsi(series, period=11):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def calculate_adx(df, period=14):
    df = df.copy()
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    
    df['up'] = df['high'] - df['high'].shift(1)
    df['down'] = df['low'].shift(1) - df['low']
    df['+dm'] = np.where((df['up'] > df['down']) & (df['up'] > 0), df['up'], 0)
    df['-dm'] = np.where((df['down'] > df['up']) & (df['down'] > 0), df['down'], 0)
    
    df['tr_s'] = df['tr'].rolling(window=period).mean()
    df['+dm_s'] = df['+dm'].rolling(window=period).mean()
    df['-dm_s'] = df['-dm'].rolling(window=period).mean()
    
    df['+di'] = 100 * (df['+dm_s'] / df['tr_s'])
    df['-di'] = 100 * (df['-dm_s'] / df['tr_s'])
    df['dx'] = 100 * (abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'] + 1e-9))
    return df['dx'].rolling(window=period).mean()

def get_dna_v2(row_15m, harmony):
    # RSI Fazı
    rsi = row_15m['rsi']
    if rsi <= 35: faz = "DIP"
    elif rsi <= 45: faz = "BIRIKIM"
    elif rsi <= 55: faz = "NOTR"
    elif rsi <= 65: faz = "MOM"
    elif rsi <= 75: faz = "TREND"
    else: faz = "ALIM"
    
    # Sıkışma (Aks)
    sq_pct = abs(row_15m['rsi_rib_20'] - row_15m['rsi_rib_55']) / (row_15m['rsi_ema'] or 1) * 100
    if sq_pct <= 0.3: aks = "TIGHT"
    elif sq_pct <= 0.8: aks = "MICRO"
    elif sq_pct <= 1.5: aks = "NORMAL"
    else: aks = "GAP"
    
    # Hacim Ritmi (Vrsi)
    v_hyb = row_15m['Vrsi']
    if v_hyb >= 10: ritim = "NOVA"
    elif v_hyb >= 7: ritim = "SURGE"
    elif v_hyb >= 4: ritim = "READY"
    else: ritim = "DRY"
    
    # Vuruş Karakteri (VBoy)
    v_eff = row_15m['VBoy']
    if v_eff >= 8: char = "PURE"
    elif v_eff >= 5: char = "SOLID"
    else: char = "THIN"
    
    # RSI Açı
    ang = row_15m['ang']
    if ang >= 60: a_p = "SHARP"
    elif ang >= 45: a_p = "UP"
    else: a_p = "FLAT"

    return f"{faz}|{aks}|{ritim}|{char}|{a_p}|{harmony}"

def process_coin(symbol):
    try:
        # Load all timeframes
        df_15m = pd.read_parquet(f"{CELLS_DIR}/{symbol}/data/history_15m.parquet")
        df_1h = pd.read_parquet(f"{CELLS_DIR}/{symbol}/data/history_1h.parquet")
        df_4h = pd.read_parquet(f"{CELLS_DIR}/{symbol}/data/history_4h.parquet")
        df_1d = pd.read_parquet(f"{CELLS_DIR}/{symbol}/data/history_1d.parquet")
        
        for df in [df_15m, df_1h, df_4h, df_1d]:
            df['ts'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('ts', inplace=True)
            df['rsi'] = calculate_rsi(df['close'], 11)
            df['rsi_ema'] = df['rsi'].ewm(span=11, adjust=False).mean()
            df['rsi_rib_20'] = df['rsi_ema'].ewm(span=20, adjust=False).mean()
            df['rsi_rib_55'] = df['rsi_ema'].ewm(span=55, adjust=False).mean()
            df['vol_ma100'] = df['volume'].rolling(window=100).mean()
            df['adx'] = calculate_adx(df, 14)
            df['atr_pct'] = ((df['high'] - df['low']).rolling(window=14).mean() / df['close']) * 100

        # Sync 15m with Upper Timeframes
        h1_vals = df_1h.reindex(df_15m.index, method='ffill')
        h4_vals = df_4h.reindex(df_15m.index, method='ffill')
        d1_vals = df_1d.reindex(df_15m.index, method='ffill')

        df_15m['h1_ok'] = h1_vals['close'] > h1_vals['rsi_rib_55']
        df_15m['h4_ok'] = h4_vals['close'] > h4_vals['rsi_rib_55']
        df_15m['d1_ok'] = d1_vals['close'] > d1_vals['rsi_rib_55']
        
        # Additional Metrics for 15m
        df_15m['Vrsi'] = (df_15m['volume'] / df_15m['vol_ma100'].replace(0, 1)) * 2 * (df_15m['rsi'] / 50.0)
        df_15m['VBoy'] = ((df_15m['close'] - df_15m['open']).abs() / (df_15m['high'] - df_15m['low']).replace(0, 1e-9)) * 10
        df_15m['ang'] = np.degrees(np.arctan((df_15m['rsi_ema'] - df_15m['rsi_ema'].shift(3)) / 3.0)) # Rough angle

        # Filter 2023-2025
        train_df = df_15m[(df_15m.index.year >= START_YEAR) & (df_15m.index.year <= END_YEAR)].copy()
        
        # Triggers
        # RC
        r_max = train_df[['rsi_rib_20', 'rsi_rib_55']].max(axis=1)
        r_min = train_df[['rsi_rib_20', 'rsi_rib_55']].min(axis=1)
        train_df['tr_rc'] = (train_df['rsi_ema'] > r_max) & (train_df['rsi_ema'].shift(1) <= r_max.shift(1)) & (r_min > 50)
        # 60
        train_df['tr_60'] = (train_df['rsi_ema'] > 60) & (train_df['rsi_ema'].shift(1) <= 60) & (train_df['rsi_rib_20'] > 50)
        # 70
        train_df['tr_70'] = (train_df['rsi'] > 70) & (train_df['rsi_ema'] > 70) & (train_df['rsi'] > train_df['rsi_ema']) & (train_df['rsi'].shift(1) <= 70)

        triggers = train_df[train_df['tr_rc'] | train_df['tr_60'] | train_df['tr_70']]
        harvest = []

        for ts, row in triggers.iterrows():
            # Result 21 bars later
            idx = train_df.index.get_loc(ts)
            future = train_df.iloc[idx+1:idx+22]
            if len(future) < 21: continue
            
            entry_p = future.iloc[0]['open']
            peak = future['high'].max()
            mdd = future['low'].min()
            exit_p = future.iloc[-1]['close']
            
            p_max = ((peak / entry_p) - 1) * 100
            p_mdd = ((mdd / entry_p) - 1) * 100
            p_exit = ((exit_p / entry_p) - 1) * 100
            
            harmony = f"{int(row['h1_ok'])}{int(row['h4_ok'])}{int(row['d1_ok'])}"
            dna = get_dna_v2(row, harmony)
            
            harvest.append({
                'symbol': symbol,
                'ts': ts,
                'dna': dna,
                'max': p_max,
                'mdd': p_mdd,
                'exit': p_exit,
                'type': 'RC' if row['tr_rc'] else ('60' if row['tr_60'] else '70')
            })
        return harvest
    except Exception as e:
        print(f"Error {symbol}: {e}")
        return []

all_harvest = []
coins = sorted([d for d in os.listdir(CELLS_DIR) if os.path.isdir(os.path.join(CELLS_DIR, d))])
print(f"Starting Harvest for {len(coins)} coins...")

for i, coin in enumerate(coins):
    print(f"[{i+1}/{len(coins)}] Harvesting {coin}...")
    all_harvest.extend(process_coin(coin))

df_final = pd.DataFrame(all_harvest)
df_final.to_csv(OUTPUT_CSV, index=False)
print(f"✅ HARVEST COMPLETE: {len(df_final)} dna samples saved to {OUTPUT_CSV}")
