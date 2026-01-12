import pandas as pd
import numpy as np
from datetime import datetime
from tezaver.core import config, coin_cell_paths

symbol = "API3USDT"
target_date = "2025-08-19"

def diagnose_coin(symbol, target_date):
    path_1d = coin_cell_paths.get_history_file(symbol, '1d')
    path_4h = coin_cell_paths.get_history_file(symbol, '4h')
    
    if not path_1d.exists() or not path_4h.exists():
        print(f"Data missing for {symbol}")
        return

    df_1d = pd.read_parquet(path_1d)
    df_1d['datetime'] = df_1d['datetime'].dt.tz_localize(None)
    
    df_4h = pd.read_parquet(path_4h)
    df_4h['datetime'] = df_4h['datetime'].dt.tz_localize(None)
    
    # ATR Calculation
    df_1d['tr'] = np.maximum(df_1d['high'] - df_1d['low'], 
                            np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), 
                                       abs(df_1d['low'] - df_1d['close'].shift(1))))
    df_1d['atr_pct'] = (df_1d['tr'].rolling(14).mean() / df_1d['close']) * 100
    
    # RSI Calculation (Daily logic)
    delta = df_4h['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df_4h['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 0.001))))
    df_4h['day'] = df_4h['datetime'].dt.floor('D')
    daily_rsi = df_4h.groupby('day')['rsi'].last()
    
    # Get values for target date
    target_dt = pd.to_datetime(target_date)
    idx = df_1d[df_1d['datetime'] == target_dt].index[0]
    
    tr_trail = df_1d.iloc[idx-13 : idx+1][['datetime', 'tr']]
    avg_tr = df_1d.iloc[idx]['tr_rolling_mean'] = df_1d['tr'].rolling(14).mean().iloc[idx]
    
    print(f"--- {symbol} Forensic Diagnosis for {target_date} ---")
    print("\nSon 14 Günlük True Range (TR) Dağılımı:")
    print(tr_trail.to_string(index=False))
    
    atr_pct = (avg_tr / df_1d.loc[idx, 'close']) * 100
    rsi = daily_rsi.get(target_dt, None)
    
    print(f"\nHesaplama:")
    print(f"14 Günlük TR Ortalaması: {avg_tr:.4f}")
    print(f"Günün Kapanış Fiyatı: {df_1d.loc[idx, 'close']:.4f}")
    print(f"ATR % (Ort_TR / Close): {atr_pct:.2f}%")
        
    # Check criteria
    TUNEL = {
        'TREND': {'atr_min': 15.0, 'rsi_min': 55.0, 'rsi_max': 70.0},
        'NINJA': {'atr_min': 12.0, 'rsi_min': 60.0, 'rsi_max': 75.0}
    }
    
    is_trend = atr >= TUNEL['TREND']['atr_min'] and TUNEL['TREND']['rsi_min'] <= rsi <= TUNEL['TREND']['rsi_max']
    is_ninja = atr >= TUNEL['NINJA']['atr_min'] and TUNEL['NINJA']['rsi_min'] <= rsi <= TUNEL['NINJA']['rsi_max']
    
    print(f"Meets TREND: {is_trend}")
    print(f"Meets NINJA: {is_ninja}")
    
    # Detail why
    if not is_trend:
        reasons = []
        if atr < TUNEL['TREND']['atr_min']: reasons.append(f"ATR too low ({atr:.2f} < {TUNEL['TREND']['atr_min']})")
        if rsi < TUNEL['TREND']['rsi_min']: reasons.append(f"RSI too low ({rsi:.2f} < {TUNEL['TREND']['rsi_min']})")
        if rsi > TUNEL['TREND']['rsi_max']: reasons.append(f"RSI too high ({rsi:.2f} > {TUNEL['TREND']['rsi_max']})")
        print(f"TREND rejection: {', '.join(reasons)}")

    if not is_ninja:
        reasons = []
        if atr < TUNEL['NINJA']['atr_min']: reasons.append(f"ATR too low ({atr:.2f} < {TUNEL['NINJA']['atr_min']})")
        if rsi < TUNEL['NINJA']['rsi_min']: reasons.append(f"RSI too low ({rsi:.2f} < {TUNEL['NINJA']['rsi_min']})")
        if rsi > TUNEL['NINJA']['rsi_max']: reasons.append(f"RSI too high ({rsi:.2f} > {TUNEL['NINJA']['rsi_max']})")
        print(f"NINJA rejection: {', '.join(reasons)}")

diagnose_coin(symbol, target_date)
