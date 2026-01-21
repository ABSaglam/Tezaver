import sys
import os
sys.path.append(os.getcwd())
import pandas as pd
import json
from scripts.asm_v12_turbo import TurboSniper_v12

def scan_ayas_days():
    # 1. Load 1H Data
    df_h1 = pd.read_parquet("coin_cells/ALGOUSDT/data/history_1h.parquet")
    df_h1['timestamp'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
    df_h1.set_index('timestamp', inplace=True)
    df_h1.sort_index(inplace=True)
    
    # Calculate Indicators
    df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
    df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
    df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
    
    def get_comp(row):
        emas = [row['ema9'], row['ema21'], row['ema50']]
        return (max(emas) / min(emas) - 1) * 100
        
    df_h1['comp'] = df_h1.apply(get_comp, axis=1)
    
    # 2. Find "Ayaş Tüneli" Days (Squeeze < 2.5%)
    # We look for the first time it enters squeeze each day to avoid duplicates
    ayas_triggers = df_h1[df_h1['comp'] < 2.5]
    ayas_days = ayas_triggers.index.normalize().unique()
    
    print(f"🔍 Found {len(ayas_days)} days that passed 'Ayaş Tüneli' (1H Squeeze < 2.5%).")
    
    # 3. Load 15M Data
    df_15m = pd.read_parquet("coin_cells/ALGOUSDT/data/history_15m.parquet")
    df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
    
    # Indicators for 15M
    df_15m['ema9'] = df_15m['close'].ewm(span=9, adjust=False).mean()
    df_15m['ema21'] = df_15m['close'].ewm(span=21, adjust=False).mean()
    df_15m['ema50'] = df_15m['close'].ewm(span=50, adjust=False).mean()
    
    # Simple Volume MA for vol_ratio
    df_15m['vol_ma'] = df_15m['volume'].rolling(20).mean()
    df_15m['vol_ratio'] = df_15m['volume'] / df_15m['vol_ma']
    
    # RSI
    delta = df_15m['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df_15m['rsi'] = 100 - (100 / (1 + rs))

    results = []
    
    for day in ayas_days:
        # Extract 15m candles for that day (100 candles starting from midnight or trigger?)
        # Let's take the day itself
        day_start = day
        day_end = day + pd.Timedelta(days=1)
        
        day_candles_df = df_15m[(df_15m['timestamp'] >= day_start) & (df_15m['timestamp'] < day_end)]
        if len(day_candles_df) < 50: continue
        
        # Convert to list of dicts for ASM
        candles_list = day_candles_df.to_dict('records')
        rally_data = {'date': str(day.date()), '15m_data': candles_list}
        
        asm = TurboSniper_v12(rally_data, df_h1)
        res = asm.run()
        results.append(res)

    # Report
    print("\n" + "="*100)
    print(f"{'DATE':12} | {'IN':5} | {'PNL':8} | {'HELD':5} | {'RESULT'}")
    print("-" * 100)
    
    trades = [r for r in results if r.get('entry_idx') is not None]
    for res in results:
        if res.get('entry_idx') is not None:
            icon = "✅" if res['pnl'] > 0 else "❌"
            print(f"{icon} {res['date']:12} | C{res['entry_idx']:2} | {res['pnl']:+7.2f}% | {res['held']:2} | {'Win' if res['pnl'] > 0 else 'Loss'}")
        # else:
        #    print(f"⚪ {res['date']:12} | Skip | {res['reason']}")

    print("\n" + "="*100)
    if trades:
        total_pnl = sum(t['pnl'] for t in trades)
        win_rate = sum(1 for t in trades if t['pnl'] > 0) / len(trades) * 100
        print(f"TOTAL DAYS SCANNED: {len(results)}")
        print(f"TRADES TAKEN:       {len(trades)} (Coverage: {len(trades)/len(results)*100:.1f}%)")
        print(f"TOTAL PNL:          {total_pnl:+.2f}%")
        print(f"WIN RATE:           {win_rate:.1f}%")
        print(f"AVG HELD:           {sum(t['held'] for t in trades)/len(trades):.1f} candles")
    else:
        print("No trades taken.")

if __name__ == "__main__":
    scan_ayas_days()
