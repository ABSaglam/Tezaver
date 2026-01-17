
import pandas as pd
from datetime import datetime
from tezaver.core import coin_cell_paths, config
from tezaver.mining.ayas_tuneli import tunelden_gec

def find_active_coins_nov():
    start_nov = datetime(2025, 11, 1)
    end_nov = datetime(2025, 11, 30, 23, 59)
    
    active_coins = []
    
    for symbol in config.DEFAULT_COINS[:100]: # Check first 100
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, '1d')
            path_4h = coin_cell_paths.get_history_file(symbol, '4h')
            if not path_1d.exists() or not path_4h.exists(): continue
            
            df_1d = pd.read_parquet(path_1d)
            df_1d['datetime'] = df_1d['datetime'].dt.tz_localize(None)
            df_4h = pd.read_parquet(path_4h)
            df_4h['datetime'] = df_4h['datetime'].dt.tz_localize(None)
            
            q4_data = df_1d[(df_1d['datetime'] >= start_nov) & (df_1d['datetime'] <= end_nov)]
            
            count = 0
            for i, row in q4_data.iterrows():
                sig_time = row['datetime']
                if tunelden_gec(symbol, df_1d[df_1d['datetime'] <= sig_time], df_4h[df_4h['datetime'] <= sig_time])['passed']:
                    count += 1
            
            if count > 0:
                active_coins.append((symbol, count))
                
        except: continue
    
    active_coins.sort(key=lambda x: x[1], reverse=True)
    print("ACTIVE COINS IN NOV 2025:")
    for sym, c in active_coins:
        print(f"{sym}: {c} signals")

if __name__ == "__main__":
    find_active_coins_nov()
