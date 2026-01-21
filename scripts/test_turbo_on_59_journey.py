import sys
import os
import pandas as pd
import json
from datetime import timedelta
sys.path.append(os.getcwd())
from scripts.asm_v14_balanced import BalancedSniper_v14

def run_turbo_on_59_journey_days():
    # 1. Identify the 59 Journey Dates
    # Start with the 26 known rallies
    with open("data/algo_rally_days_15m.json", 'r') as f:
        rally_data = json.load(f)
    
    rally_dates = [pd.Timestamp(r['date']) for r in rally_data]
    journey_offsets = [1, 3, 5, 7, 14, 21]
    
    journey_dates = {}
    for rd in rally_dates:
        journey_dates[rd.date()] = "T-0"
        for offset in journey_offsets:
            prep_day = (rd - timedelta(days=offset)).date()
            if prep_day not in journey_dates:
                journey_dates[prep_day] = f"T-{offset}"
    
    print(f"🧙 Total Journey Days to test: {len(journey_dates)}")
    
    # 2. Prepare Data (H1 and 15M)
    df_h1 = pd.read_parquet("coin_cells/ALGOUSDT/data/history_1h.parquet")
    df_h1['timestamp'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
    df_h1.set_index('timestamp', inplace=True)
    df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
    df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
    df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
    
    df_15m = pd.read_parquet("coin_cells/ALGOUSDT/data/history_15m.parquet")
    df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
    df_15m['ema9'] = df_15m['close'].ewm(span=9, adjust=False).mean()
    df_15m['ema21'] = df_15m['close'].ewm(span=21, adjust=False).mean()
    df_15m['ema50'] = df_15m['close'].ewm(span=50, adjust=False).mean()
    df_15m['vol_ma'] = df_15m['volume'].rolling(20).mean()
    df_15m['vol_ratio'] = df_15m['volume'] / df_15m['vol_ma']
    
    # 3. Run ASM v12 on each day
    results = []
    sorted_dates = sorted(journey_dates.keys())
    
    for date in sorted_dates:
        tag = journey_dates[date]
        day_start = pd.Timestamp(date)
        day_end = day_start + pd.Timedelta(days=1)
        
        day_df = df_15m[(df_15m['timestamp'] >= day_start) & (df_15m['timestamp'] < day_end)]
        if day_df.empty: continue
        
        rally_data_mock = {'date': str(date), '15m_data': day_df.to_dict('records')}
        asm = BalancedSniper_v14(rally_data_mock, df_h1)
        res = asm.run()
        res['tag'] = tag
        results.append(res)
        
    # 4. Detailed Report
    print("\n🚀 TURBO SNIPER V12 - 59 JOURNEY DAYS REPORT")
    print("="*100)
    print(f"{'DATE':12} | {'TYPE':6} | {'IN':5} | {'PNL':8} | {'HELD':5} | {'REASON'}")
    print("-" * 100)
    
    trades = [r for r in results if r.get('entry_idx') is not None]
    for res in results:
        if res.get('entry_idx') is not None:
            icon = "✅" if res['pnl'] > 0 else "❌"
            print(f"{icon} {res['date']:12} | {res['tag']:6} | C{res['entry_idx']:2} | {res['pnl']:+7.2f}% | {res['held']:2} | {'Win'}")
        else:
            print(f"⚪ {res['date']:12} | {res['tag']:6} | Skip | {'---':8} | {'---':5} | {res.get('reason', 'No Trigger')}")

    # 5. Summary
    print("\n" + "="*100)
    if trades:
        total_pnl = sum(t['pnl'] for t in trades)
        t0_trades = [t for t in trades if t['tag'] == 'T-0']
        prep_trades = [t for t in trades if t['tag'] != 'T-0']
        
        print(f"TOTAL JOURNEY DAYS: {len(results)}")
        print(f"TRADES TAKEN:       {len(trades)}")
        print(f"TOTAL PNL:          {total_pnl:+.2f}%")
        print(f"WIN RATE:           {sum(1 for t in trades if t['pnl'] > 0) / len(trades) * 100:.1f}%")
        print(f"AVG HELD:           {sum(t['held'] for t in trades)/len(trades):.1f} candles")
        print("-" * 100)
        print(f"T-0 (Rally) PnL:    {sum(t['pnl'] for t in t0_trades):+.2f}% ({len(t0_trades)} trades)")
        print(f"Prep Day PnL:       {sum(t['pnl'] for t in prep_trades):+.2f}% ({len(prep_trades)} trades)")
    else:
        print("No trades taken.")

if __name__ == "__main__":
    run_turbo_on_59_journey_days()
