import sys
sys.path.insert(0, 'src')
import pandas as pd
import numpy as np
from tezaver.supernova.supernova_detector import SuperNovaDetector
from tezaver.core import config, coin_cell_paths
from pathlib import Path
from datetime import timedelta

def run_simulation():
    detector = SuperNovaDetector()
    all_res = []

    print("Hafıza taranıyor (100 Koin / 1 Yıl)...", file=sys.stderr)
    
    for symbol in config.DEFAULT_COINS:
        try:
            p15 = coin_cell_paths.get_history_file(symbol, '15m')
            if not p15.exists(): continue
            df1 = pd.read_parquet(p15)
            
            p1h = coin_cell_paths.get_history_file(symbol, '1h')
            p4h = coin_cell_paths.get_history_file(symbol, '4h')
            p1d = coin_cell_paths.get_history_file(symbol, '1d')
            
            df1h = detector.calculate_indicators(pd.read_parquet(p1h)) if p1h.exists() else None
            df4h = detector.calculate_indicators(pd.read_parquet(p4h)) if p4h.exists() else None
            df1d = pd.read_parquet(p1d) if p1d.exists() else None
            
            res = detector.analyze_backtest(df1, symbol=symbol, df_1h=df1h, df_4h=df4h, df_1d=df1d)
            # DNA v3 Pass only
            dna_only = [r for r in res if r['dna_v2'] == '✅' and r['killer_blow'] == '🔥']
            all_res.extend(dna_only)
        except: continue

    if not all_res:
        print("NO_SIGNALS")
        return

    df_signals = pd.DataFrame(all_res).sort_values('datetime')
    
    balance = 100.0
    active_trades = [] 
    max_slots = 3
    history = []

    for idx, signal in df_signals.iterrows():
        t = signal['datetime']
        
        # Close expired
        to_keep = []
        for tr in active_trades:
            if tr['end_time'] <= t:
                balance += tr['cap'] * (1 + tr['res_pct'])
            else:
                to_keep.append(tr)
        active_trades = to_keep
        
        # Entry Logic
        res_p = -0.01 
        if signal['max_loss'] <= -3.0:
            res_p = -0.03 # Stop Loss
        else:
            if signal['max_gain'] >= 30: res_p = 0.25 # Diamond
            elif signal['max_gain'] >= 20: res_p = 0.15 # Gold
            elif signal['max_gain'] >= 10: res_p = 0.08 # Silver
            elif signal['max_gain'] >= 5: res_p = 0.04 # Bronze
            else: res_p = -0.01 # Iron failure
            
        res_p -= 0.002 # Fees
        
        if len(active_trades) < max_slots:
            allocated = balance / (max_slots - len(active_trades))
            balance -= allocated
            active_trades.append({
                'end_time': t + timedelta(hours=12),
                'res_pct': res_p,
                'cap': allocated,
            })
        
        current_total = balance + sum(tr['cap'] for tr in active_trades)
        history.append({'t': t, 'bal': current_total})

    # Final close
    for tr in active_trades:
        balance += tr['cap'] * (1 + tr['res_pct'])
        
    print(f"--- PORTFOLIO ANALİZİ (DNA v3) ---")
    print(f"Başlangıç: $100")
    print(f"Final Bakiye: ${balance:.2f}")
    print(f"Toplam İşlem: {len(df_signals)}")
    print(f"Toplam Getiri: %{((balance-100)/100)*100:.1f}")
    
run_simulation()
