import sys
import os
sys.path.append(os.getcwd())
import pandas as pd
import numpy as np
import json
from scripts.asm_v14_balanced import BalancedSniper_v14

def scan_agld_ayas_days():
    symbol = "AGLDUSDT"
    path_1d = f"coin_cells/{symbol}/data/history_1d.parquet"
    path_4h = f"coin_cells/{symbol}/data/history_4h.parquet"
    path_1h = f"coin_cells/{symbol}/data/history_1h.parquet"
    path_15m = f"coin_cells/{symbol}/data/history_15m.parquet"
    
    df_1d = pd.read_parquet(path_1d)
    df_4h = pd.read_parquet(path_4h)
    df_1h = pd.read_parquet(path_1h)
    df_15m = pd.read_parquet(path_15m)
    
    # Pre-process 1D (ATR)
    df_1d['dt'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d.set_index('dt', inplace=True)
    df_1d['tr'] = np.maximum(df_1d['high'] - df_1d['low'], 
                            np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), 
                                       abs(df_1d['low'] - df_1d['close'].shift(1))))
    df_1d['atr_pct'] = (df_1d['tr'].rolling(14).mean() / df_1d['close']) * 100
    
    # Pre-process 4H (RSI)
    df_4h['dt'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h.set_index('dt', inplace=True)
    delta = df_4h['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df_4h['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 0.001))))
    
    # Pre-process 1H (H1_Data for ASM)
    df_1h['dt'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
    df_1h.set_index('dt', inplace=True)
    df_1h['ema9'] = df_1h['close'].ewm(span=9, adjust=False).mean()
    df_1h['ema21'] = df_1h['close'].ewm(span=21, adjust=False).mean()
    df_1h['ema50'] = df_1h['close'].ewm(span=50, adjust=False).mean()
    
    # Pre-process 15M (ASM Data)
    df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
    df_15m['ema9'] = df_15m['close'].ewm(span=9, adjust=False).mean()
    df_15m['ema21'] = df_15m['close'].ewm(span=21, adjust=False).mean()
    df_15m['ema50'] = df_15m['close'].ewm(span=50, adjust=False).mean()
    df_15m['vol_ma'] = df_15m['volume'].rolling(20).mean()
    df_15m['vol_ratio'] = df_15m['volume'] / df_15m['vol_ma']
    
    # Identify PASS days in 2023
    pass_days = []
    df_1d_2023 = df_1d[df_1d.index.year == 2023]
    
    for day_ts in df_1d_2023.index:
        atr = df_1d.loc[day_ts, 'atr_pct']
        try:
            rsi_4h = df_4h[df_4h.index <= day_ts].iloc[-1]['rsi']
        except:
            continue
            
        is_trend = atr >= 15.0 and 55 <= rsi_4h <= 70
        is_ninja = atr >= 12.0 and 60 <= rsi_4h <= 75
        
        if is_trend or is_ninja:
            pass_days.append(day_ts)
            
    print(f"🚇 Found {len(pass_days)} days passing 'Ayaş Tüneli' for {symbol} in 2023.")
    
    results = []
    for day in pass_days:
        day_start = day
        day_end = day + pd.Timedelta(days=1)
        
        day_df = df_15m[(df_15m['dt'] >= day_start) & (df_15m['dt'] < day_end)]
        if len(day_df) < 50: continue
        
        day_df_mock = day_df.copy()
        day_df_mock['timestamp'] = day_df_mock['dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        rally_data = {'date': str(day.date()), '15m_data': day_df_mock.to_dict('records')}
        asm = BalancedSniper_v14(rally_data, df_1h)
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
        else:
            print(f"⚪ {res['date']:12} | Skip | {'No signal (Vetoed)'}")

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
    scan_agld_ayas_days()
