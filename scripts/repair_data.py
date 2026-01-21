import os
import pandas as pd
import sys

def audit_and_repair():
    print("🔍 DATA INTEGRITY AUDIT STARTING...")
    
    root = "coin_cells"
    if not os.path.exists(root):
        print(f"❌ '{root}' directory not found.")
        return

    coins = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    coins.sort()
    
    report = {
        'total': len(coins),
        'missing_1w': [],
        'repaired_1w': [],
        'fatal': []
    }
    
    for coin in coins:
        data_dir = os.path.join(root, coin, "data")
        f_1w = os.path.join(data_dir, "history_1w.parquet")
        f_1d = os.path.join(data_dir, "history_1d.parquet")
        
        # Check 1W
        if not os.path.exists(f_1w):
            print(f"⚠️ {coin}: Missing 1W Data.")
            report['missing_1w'].append(coin)
            
            # ATTEMPT REPAIR
            if os.path.exists(f_1d):
                print(f"   🛠️ Repairing {coin} 1W using 1D data...")
                try:
                    df_d = pd.read_parquet(f_1d)
                    df_d['dt'] = pd.to_datetime(df_d['timestamp'], unit='ms')
                    df_d.set_index('dt', inplace=True)
                    
                    # Resample logic for Weekly (ending Sunday usually, or strictly 7D)
                    # Binance weekly candles start Monday 00:00 UTC. 
                    # We will use 'W-MON' to align approx with typical crypto weeks or just 'W'.
                    # 'W' defaults to Sunday. 'W-MON' starts monday.
                    
                    logic = {
                        'open': 'first',
                        'high': 'max',
                        'low': 'min',
                        'close': 'last',
                        'volume': 'sum',
                        'quote_asset_volume': 'sum',
                        'number_of_trades': 'sum',
                        'taker_buy_base_asset_volume': 'sum',
                        'taker_buy_quote_asset_volume': 'sum',
                        'timestamp': 'first' # We will fix this
                    }
                    
                    # Resample to Weekly (Mon start)
                    df_w = df_d.resample('W-MON').agg(logic).dropna()
                    
                    # Fix timestamp (ms) - resample often sets it to index or messes it up
                    # We want the timestamp of the start of the week usually or just preserve index
                    df_w['timestamp'] = df_w.index.astype(int) // 10**6 
                    
                    # Save
                    df_w.reset_index(inplace=True) # brings dt back as col
                    # Reorder cols if needed (not strictly required for parquet reading usually as long as names match)
                    
                    df_w.to_parquet(f_1w)
                    print(f"   ✅ {coin}: 1W Data Repaired ({len(df_w)} weeks generated)")
                    report['repaired_1w'].append(coin)
                    
                except Exception as e:
                    print(f"   ❌ Repair Failed: {e}")
                    report['fatal'].append(f"{coin} (Repair Error)")
            else:
                print(f"   ❌ {coin}: Cannot repair (Missing 1D data too!)")
                report['fatal'].append(f"{coin} (No 1D)")
        
    print("\n📊 AUDIT & REPAIR SUMMARY")
    print(f"Total Coins: {report['total']}")
    print(f"Missing 1W Initially: {len(report['missing_1w'])}")
    print(f"Repaired Successfully: {len(report['repaired_1w'])}")
    print(f"Fatal Issues (Still Missing): {len(report['fatal'])}")
    
    if len(report['fatal']) > 0:
        print("Fatal List:", report['fatal'])

if __name__ == "__main__":
    audit_and_repair()
