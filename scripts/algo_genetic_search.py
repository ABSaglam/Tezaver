
import sys
import os
import pandas as pd
import numpy as np
import random

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ALGOUSDT'
    print(f"🧪 GENETIC SEARCH: {symbol}")
    print("="*70)

    # 1. Load Data
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD'], train_only=True)
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    
    if not os.path.exists(h4_path):
        print("❌ 4H Data not found!")
        return
        
    df = pd.read_parquet(h4_path)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)

    # 2. Rich Feature Set
    df['rsi'] = 100 - (100 / (1 + (df['close'].diff().where(df['close'].diff() > 0, 0).rolling(14).mean() / (-df['close'].diff().where(df['close'].diff() < 0, 0).rolling(14).mean()))))
    df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    df['ema_21'] = df['close'].ewm(span=21).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    df['trend'] = (df['ema_21'] / df['ema_50'] - 1) * 100
    df['hour'] = df['datetime'].dt.hour
    df['day_of_week'] = df['datetime'].dt.dayofweek # 0=Mon, 6=Sun
    df['body_size'] = abs(df['close'] - df['open']) / df['open'] * 100
    
    # Target Mapping
    rally_dates = set(rally_results.keys())
    # Target: Candle is within 24h before a rally
    # We map 'next_day' date
    df['target'] = (df['datetime'] + pd.Timedelta(hours=24)).dt.date.isin(rally_dates)
    
    # 3. GENETIC MONTE CARLO
    # Generate random rules
    
    BEST_PRECISION = 0
    BEST_RULE = ""
    BEST_HITS = 0
    
    ITERATIONS = 5000
    print(f"🧬 Spawning {ITERATIONS} mutants...")
    
    for i in range(ITERATIONS):
        # Randomly select parameters
        r_min = random.choice([30, 40, 50, 55, 60, 65, 70])
        r_max = random.choice([75, 80, 85, 90, 100])
        if r_min >= r_max: r_min = r_max - 5
        
        v_max = random.choice([1.5, 2.0, 3.0, 5.0, 10.0])
        t_min = random.choice([-5, 0, 5, 10])
        
        # Optional: Time filters
        use_hour = random.random() > 0.7
        target_hour = random.choice([0, 4, 8, 12, 16, 20])
        
        # Construct Mask
        mask = (
            (df['rsi'] >= r_min) &
            (df['rsi'] <= r_max) &
            (df['vol_ratio'] <= v_max) &
            (df['trend'] >= t_min)
        )
        
        if use_hour:
            mask = mask & (df['hour'] == target_hour)
            rule_str = f"RSI:{r_min}-{r_max} & Vol<={v_max} & Trend>={t_min} & Hour={target_hour}"
        else:
            rule_str = f"RSI:{r_min}-{r_max} & Vol<={v_max} & Trend>={t_min}"
            
        hits = df[mask & df['target']]
        fails = df[mask & ~df['target']]
        
        h = len(hits)
        f = len(fails)
        t = h + f
        
        if t >= 2: # Minimum 2 signals
            prec = h/t * 100
            
            if prec > BEST_PRECISION:
                BEST_PRECISION = prec
                BEST_RULE = rule_str
                BEST_HITS = h
                
                # Check absolute perfection
                if prec == 100:
                    print(f"💎 EUREKA! {rule_str} -> {h}/{t} (100%)")
                    # Save into a list? No, just keep the best.
                    
            # Also log anything decent
            if prec >= 80 and h >= 3:
                print(f"🥈 Strong Mutant: {rule_str} -> {h}/{t} ({prec:.1f}%)")

    print("\n" + "="*70)
    print(f"👑 KING MUTANT: {BEST_RULE}")
    print(f"   Precision: {BEST_PRECISION:.1f}% ({BEST_HITS} Hits)")
    
    if BEST_PRECISION == 100:
        print("✅ GÖREV TAMAMLANDI. %100 Filtre Bulundu.")
    else:
        print("❌ 5000 Mutasyon yetmedi. %100 bulunamadı.")

if __name__ == "__main__":
    main()
