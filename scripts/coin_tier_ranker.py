"""
📊 Coin Tier Ranking Scanner
Find coins ranked 70-150 by Tier count
"""
import os
import pandas as pd
import numpy as np

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"

def load_clean(path):
    try:
        df = pd.read_parquet(path)
        if 'timestamp' in df.columns:
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df = df[~df.index.duplicated(keep='last')]
            return df.sort_index()
    except:
        return pd.DataFrame()

def count_tiers(symbol):
    """Count tier events for a symbol"""
    base_path = os.path.join(COIN_CELLS_DIR, symbol, "data")
    df_15m_path = os.path.join(base_path, "history_15m.parquet")
    
    if not os.path.exists(df_15m_path):
        return 0
    
    df_15m = load_clean(df_15m_path)
    if df_15m.empty or len(df_15m) < 1000:
        return 0
    
    # Filter to 2023-2025
    start_date = pd.Timestamp("2023-01-01")
    end_date = pd.Timestamp("2025-12-31")
    df_15m = df_15m[(df_15m.index >= start_date) & (df_15m.index <= end_date)]
    
    if len(df_15m) < 1000:
        return 0
    
    # Calculate RSI-EMA and Ribbon
    try:
        alpha_rsi = 1/11
        delta = df_15m['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta.where(delta < 0, 0))
        avg_gain = gain.ewm(alpha=alpha_rsi, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha_rsi, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df_15m['rsi'] = 100 - (100 / (1 + rs))
        df_15m['rsi_ema'] = df_15m['rsi'].ewm(span=11, adjust=False).mean()
        
        ribbon_spans = [20, 25, 30, 35, 40, 45, 50, 55]
        for span in ribbon_spans:
            df_15m[f'ribbon_{span}'] = df_15m['rsi_ema'].ewm(span=span, adjust=False).mean()
        
        ribbon_cols = [f'ribbon_{s}' for s in ribbon_spans]
        df_15m['ribbon_max'] = df_15m[ribbon_cols].max(axis=1)
        
        cond_now = df_15m['rsi_ema'] >= df_15m['ribbon_max']
        cond_prev = df_15m['rsi_ema'].shift(1) < df_15m['ribbon_max'].shift(1)
        df_15m['trigger'] = cond_now & cond_prev
        
        trigger_indices = df_15m[df_15m['trigger']].index.tolist()
        
        tier_count = 0
        for trig_time in trigger_indices:
            trig_idx = df_15m.index.get_loc(trig_time)
            if trig_idx + 21 >= len(df_15m):
                continue
            entry_price = df_15m['close'].iloc[trig_idx]
            future_bars = df_15m.iloc[trig_idx+1 : trig_idx+22]
            if future_bars.empty:
                continue
            peak_price = future_bars['high'].max()
            peak_pct = ((peak_price / entry_price) - 1) * 100
            if peak_pct >= 5:
                tier_count += 1
        
        return tier_count
    except:
        return 0

def main():
    print("📊 Tüm Coinler Tier Sayısına Göre Sıralanıyor...")
    
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    symbols = [s for s in symbols if s.endswith('USDT')]
    
    results = []
    for i, symbol in enumerate(sorted(symbols)):
        tier_count = count_tiers(symbol)
        results.append({'symbol': symbol, 'tier_count': tier_count})
        if i % 20 == 0:
            print(f"   {i+1}/{len(symbols)}: {symbol} = {tier_count} tier")
    
    df = pd.DataFrame(results)
    df = df.sort_values(by='tier_count', ascending=False).reset_index(drop=True)
    df['rank'] = df.index + 1
    
    print(f"\n📊 EN ÇOK TİER ÜRETEN TOP 20:")
    for _, r in df.head(20).iterrows():
        print(f"   {r['rank']:>3}. {r['symbol']:<20} = {r['tier_count']} tier")
    
    print(f"\n🎯 RANK 70-150 ARASI:")
    mid_range = df[(df['rank'] >= 70) & (df['rank'] <= 150)]
    for _, r in mid_range.iterrows():
        print(f"   {r['rank']:>3}. {r['symbol']:<20} = {r['tier_count']} tier")
    
    # Pick one from middle
    if not mid_range.empty:
        selected = mid_range.iloc[len(mid_range)//2]
        print(f"\n✅ SEÇİLEN COİN (Orta Nokta): {selected['symbol']} (Rank {selected['rank']}, {selected['tier_count']} tier)")

if __name__ == "__main__":
    main()
