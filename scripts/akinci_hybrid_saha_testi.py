import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

# CONFIG
SYMBOL = "DASHUSDT"
APPROVED_DATES = [
    "2025-09-30", "2025-10-01", "2025-10-02", "2025-10-04", "2025-10-07",
    "2025-10-08", "2025-10-09", "2025-10-10", "2025-10-12", "2025-10-13",
    "2025-10-14", "2025-10-17", "2025-10-19", "2025-10-20", "2025-10-29",
    "2025-11-01", "2025-11-05", "2025-11-14", "2025-11-15", "2025-11-16",
    "2025-11-18", "2026-01-13"
]

def load_data():
    df = pd.read_parquet(f"coin_cells/{SYMBOL}/data/history_15m.parquet")
    df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('dt', inplace=True)
    df.sort_index(inplace=True)
    
    # Simple indicators
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
    df['rsi'] = 100 - (100 / (1 + gain / loss))
    
    df['body_pct'] = (df['close'] / df['open'] - 1) * 100
    df['vol_ma'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma']
    
    # Hybrid Metrics
    df['purity'] = abs(df['close'] - df['open']) / (df['high'] - df['low'] + 0.000001)
    df['rsi_roc'] = df['rsi'].diff(1)
    df['price_roc'] = df['close'].pct_change(1) * 100
    df['overdrive'] = df['rsi_roc'] / (df['price_roc'].replace(0, 0.001))
    df['stealth'] = (df['volume'] > df['volume'].shift(1)) & (df['volume'].shift(1) > df['volume'].shift(2))
    
    return df

def simulate_hybrid():
    df = load_data()
    all_trades = []
    
    for date_str in APPROVED_DATES:
        day_ts = pd.Timestamp(date_str)
        day_data = df[df.index.normalize() == day_ts]
        if day_data.empty: continue
        
        day_high = day_data['high'].max()
        day_low = day_data['low'].min()
        day_rally = (day_high / day_low - 1) * 100
        
        active_trade = None
        
        for i in range(len(day_data)):
            row = day_data.iloc[i]
            idx = day_data.index[i]
            
            if active_trade:
                # EXIT LOGIC (Nefes Kontrolü Simplified)
                active_trade['hold_bars'] += 1
                curr_pnl = (row['close'] / active_trade['entry_price'] - 1) * 100
                active_trade['max_pnl'] = max(active_trade['max_pnl'], curr_pnl)
                
                # Dynamic Exit Trailing (Simplified version of Nefes)
                # Drop from peak by 3% or Hit hard Stop Loss -3%
                if curr_pnl < -3.0 or (active_trade['max_pnl'] > 2.0 and curr_pnl < active_trade['max_pnl'] * 0.7):
                    active_trade['exit_time'] = idx
                    active_trade['exit_price'] = row['close']
                    active_trade['final_pnl'] = curr_pnl
                    all_trades.append(active_trade)
                    active_trade = None
                    break # One trade per approved day for simplicity
                
                # End of day exit
                if i == len(day_data) - 1:
                    active_trade['exit_time'] = idx
                    active_trade['exit_price'] = row['close']
                    active_trade['final_pnl'] = curr_pnl
                    all_trades.append(active_trade)
                    active_trade = None
            else:
                # ENTRY LOGIC
                # 1. Öncü Akıncı
                oncu_hit = (row['stealth'] == True) and (row['overdrive'] > 10)
                # 2. Ana Akıncı
                ana_hit = (row['vol_ratio'] >= 1.26) and (row['rsi'] >= 55) and (row['body_pct'] >= 0.50) and (row['purity'] > 0.90)
                
                if oncu_hit or ana_hit:
                    active_trade = {
                        'day': date_str,
                        'entry_time': idx,
                        'entry_price': row['close'],
                        'type': "ÖNCÜ" if oncu_hit else "ANA",
                        'hold_bars': 0,
                        'max_pnl': 0.0,
                        'day_rally': day_rally
                    }
                    
    # REPORT
    print("# 🦅 HİBRİT AKINCI (DASH) SİMÜLASYON SONUÇLARI\n")
    print("| GÜN | TİP | GİRİŞ | ÇIKIŞ | SÜRE (Bar/Dk) | RALLİ | YAKALANAN | KÂR |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    
    total_pnl = 0
    for t in all_trades:
        capture_rate = (t['final_pnl'] / t['day_rally']) * 100 if t['day_rally'] > 0 else 0
        dur_min = t['hold_bars'] * 15
        print(f"| {t['day']} | {t['type']} | {t['entry_time'].strftime('%H:%M')} | {t['exit_time'].strftime('%H:%M')} | {t['hold_bars']}b ({dur_min}dk) | %{t['day_rally']:.1f} | %{capture_rate:.1f} | **%{t['final_pnl']:.2f}** |")
        total_pnl += t['final_pnl']
        
    print(f"\n**TOPLAM NET KÂR (HİBRİT): %{total_pnl:.2f}**")
    print(f"**TOPLAM İŞLEM:** {len(all_trades)}")

if __name__ == "__main__":
    simulate_hybrid()
