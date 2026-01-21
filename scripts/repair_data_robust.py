import os
import pandas as pd
import sys

def audit_and_repair_robust():
    print("🔍 ROBUST AUDIT & REPAIR STARTING...")
    
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
            # Try repair
            if os.path.exists(f_1d):
                try:
                    df_d = pd.read_parquet(f_1d)
                    
                    # Robust Logic: Only use existing columns
                    base_logic = {
                        'open': 'first',
                        'high': 'max',
                        'low': 'min',
                        'close': 'last',
                        'volume': 'sum',
                        'timestamp': 'first'
                    }
                    
                    # Add optional columns if they exist
                    extras = ['quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']
                    logic = {k: v for k, v in base_logic.items() if k in df_d.columns}
                    for e in extras:
                        if e in df_d.columns:
                            logic[e] = 'sum'
                            
                    # Timestamp handling
                    if 'timestamp' in df_d.columns:
                        df_d['dt'] = pd.to_datetime(df_d['timestamp'], unit='ms')
                    elif 'datetime' in df_d.columns:
                        df_d['dt'] = pd.to_datetime(df_d['datetime'])
                    else:
                        raise ValueError("No timestamp column found")
                        
                    df_d.set_index('dt', inplace=True)
                    
                    # Resample
                    df_w = df_d.resample('W-MON').agg(logic).dropna()
                    
                    if df_w.empty:
                        raise ValueError("Resampling resulted in empty dataframe")
                        
                    # Fix timestamp (ms) - ensure int
                    df_w['timestamp'] = df_w.index.astype('int64') // 10**6 
                    
                    # Reset index
                    df_w.reset_index(inplace=True)
                    
                    df_w.to_parquet(f_1w)
                    print(f"   ✅ {coin}: Repaired ({len(df_w)} weeks)")
                    report['repaired_1w'].append(coin)
                    
                except Exception as e:
                    print(f"   ❌ {coin} Repair Failed: {e}")
                    report['fatal'].append(f"{coin} (Error: {e})")
            else:
                report['missing_1w'].append(coin)
                report['fatal'].append(f"{coin} (No 1D)")
        
    print("\n📊 SUMMARY")
    print(f"Repaired: {len(report['repaired_1w'])}")
    print(f"Still Missing: {len(report['missing_1w'])}")
    # print(f"Fatal details: {report['fatal'][:5]}...") # Too long

if __name__ == "__main__":
    audit_and_repair_robust()
