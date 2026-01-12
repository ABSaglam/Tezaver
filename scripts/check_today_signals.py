import pandas as pd
import numpy as np
from datetime import datetime
from tezaver.core import config, coin_cell_paths

def get_latest_signals():
    signals = []
    
    TUNEL = {
        'TREND': {'atr_min': 15.0, 'rsi_min': 55, 'rsi_max': 70},
        'NINJA': {'atr_min': 12.0, 'rsi_min': 60, 'rsi_max': 75}
    }
    
    # Tüm koinler için en son ortak tarihi bulalım
    all_dates = []
    symbol_checks = []
    
    print("--- Ayaş Tüneli Son Sinyal Taraması ---")
    
    for symbol in config.DEFAULT_COINS[:50]: # Hızlı örnekleme
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if path_1d.exists():
            df = pd.read_parquet(path_1d)
            if not df.empty:
                all_dates.append(df['datetime'].max())
    
    if not all_dates:
        print("Veri bulunamadı.")
        return

    latest_date = max(all_dates)
    print(f"Sistemdeki en güncel veri tarihi: {latest_date.strftime('%Y-%m-%d')}")
    print(f"Bu tarih için sinyaller listeleniyor...\n")

    for symbol in config.DEFAULT_COINS:
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, '1d')
            path_4h = coin_cell_paths.get_history_file(symbol, '4h')
            if not path_1d.exists() or not path_4h.exists(): continue
            
            df_1d = pd.read_parquet(path_1d)
            df_4h = pd.read_parquet(path_4h)
            
            # ATR (Daily)
            df_1d['tr'] = np.maximum(df_1d['high'] - df_1d['low'], 
                                    np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), 
                                               abs(df_1d['low'] - df_1d['close'].shift(1))))
            df_1d['atr_pct'] = (df_1d['tr'].rolling(14).mean() / df_1d['close']) * 100
            
            # RSI (Daily Grouping)
            delta = df_4h['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df_4h['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 0.001))))
            df_4h['day'] = df_4h['datetime'].dt.floor('D')
            daily_rsi = df_4h.groupby('day')['rsi'].last()
            
            row_1d = df_1d[df_1d['datetime'] == latest_date]
            if row_1d.empty: continue
            
            atr = row_1d.iloc[0]['atr_pct']
            rsi = daily_rsi.get(latest_date, None)
            
            if rsi is None: continue
            
            t = TUNEL['TREND']
            n = TUNEL['NINJA']
            is_trend = atr >= t['atr_min'] and t['rsi_min'] <= rsi <= t['rsi_max']
            is_ninja = atr >= n['atr_min'] and n['rsi_min'] <= rsi <= n['rsi_max']
            
            if is_trend or is_ninja:
                signals.append({
                    'symbol': symbol.replace('USDT', ''),
                    'type': 'TREND' if is_trend else 'NINJA',
                    'atr': round(atr, 2),
                    'rsi': round(rsi, 2)
                })
        except:
            continue
            
    if not signals:
        print(f"{latest_date.strftime('%Y-%m-%d')} tarihinde tünelden geçen koin bulunamadı.")
    else:
        df_sig = pd.DataFrame(signals)
        print(df_sig.to_markdown(index=False))

if __name__ == "__main__":
    get_latest_signals()
