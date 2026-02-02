import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings('ignore')

FILEPATH = "/Users/alisaglam/TezaverMac/coin_cells/AUCTIONUSDT/data/history_15m.parquet"

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

try:
    df = pd.read_parquet(FILEPATH)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime').sort_index()
    
    # --- CALCULATIONS (ATR, VBOY, V100) ---
    def calculate_atr(df, period=14):
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(window=period).mean()

    print(f"\n🚀 AUCTIONUSDT COMPREHENSIVE SCAN (PHYSICS + VOLUME + ATR)...")
    
    # 15M Indicators
    df['rsi'] = calculate_rsi(df['close'], 11)
    df['rsi_ema'] = df['rsi'].ewm(span=11, adjust=False).mean()
    ribbon_periods = [20, 25, 30, 35, 40, 45, 50, 55]
    for p in ribbon_periods:
        df[f'ribbon_ema{p}'] = df['rsi_ema'].ewm(span=p, adjust=False).mean()
    df['rib_max'] = df[[f'ribbon_ema{p}' for p in ribbon_periods]].max(axis=1)
    
    df['vol_ma'] = df['volume'].rolling(21).mean()
    df['atr'] = calculate_atr(df, 14)
    df['atr_pct'] = (df['atr'] / df['close']) * 100
    
    # Volume Metrics
    df['vol_max_100'] = df['volume'].rolling(window=100).max()
    
    # MTF (1H)
    df_1h = df.resample('1h').agg({'open':'first','high':'max','low':'min','close':'last', 'volume':'sum'}).dropna()
    df_1h['rsi'] = calculate_rsi(df_1h['close'], 11)
    df_1h['rsi_ema'] = df_1h['rsi'].ewm(span=11, adjust=False).mean()

    found_events = []
    prev_r_ema = 0

    for idx, row in df.iterrows():
        r_ema = row['rsi_ema']
        r_max = row['rib_max']
        
        # 1. MACRO CHECK (1H Context)
        # "Nefesi kesilmiş" değil, "Toparlanıyor" -> < 50 but Rising
        ctx_1h_idx = idx.floor('1h')
        val_1h = 100
        prev_1h = 100
        
        if ctx_1h_idx in df_1h.index:
            val_1h = df_1h.loc[ctx_1h_idx]['rsi_ema']
            # Get previous 1H value for slope check
            loc_idx = df_1h.index.get_loc(ctx_1h_idx)
            if loc_idx > 0:
                prev_1h = df_1h.iloc[loc_idx-1]['rsi_ema']
        
        # Macro Filter: 1H < 45 (Still low) AND Rising (Recovering)
        is_macro_ok = (val_1h < 45) and (val_1h >= prev_1h)

        # 2. T1 FLARE (Breakout)
        is_flare = (r_ema > r_max) and (prev_r_ema <= r_max)
        
        # 3. VOLUME TRIGGER (The Final Trigger)
        # Volume > 2.0x MA within last 3 bars
        # Simple lookback
        vol_window = df.loc[:idx].tail(3)
        vol_ok = False
        if len(vol_window) == 3:
             # Check if any bar in window had Vol > 2.0x
             for _, v_row in vol_window.iterrows():
                 if v_row['vol_ma'] > 0 and (v_row['volume'] / v_row['vol_ma']) > 2.0:
                     vol_ok = True
                     break
        
        if is_flare and is_macro_ok and vol_ok:
            # METRICS
            vboy = row['volume'] / row['vol_ma'] if row['vol_ma'] > 0 else 0
            v100 = (row['volume'] / row['vol_max_100'] * 100) if row['vol_max_100'] > 0 else 0
            # PATTERN CRITERIA: Macro must be 'Tight/Low'
            # Let's keep the broad net first to find the difference
            if val_1h < 55: # Slightly wider to see edge cases
                # Capture post-event potential
                future_window = df.loc[idx:].iloc[1:96] # Next 24h
                if not future_window.empty:
                    max_gain = ((future_window['high'].max() - row['close']) / row['close']) * 100
                else:
                    max_gain = 0
                
                # Calculate Spread
                rib_cols = [f'ribbon_ema{p}' for p in ribbon_periods]
                spread = row['rib_max'] - row[rib_cols].min()
                
                found_events.append({
                    'time': idx,
                    'price': row['close'],
                    'rsi_ema': r_ema,
                    '1h_e': val_1h,
                    'atr': row['atr_pct'],
                    'spread': spread,
                    'vboy': vboy,
                    'v100': v100,
                    'gain': max_gain
                })
        
        prev_r_ema = r_ema

    # --- ONE-OFF CHECK FOR 06:15 ---
    target_time = pd.Timestamp("2026-02-02 06:15:00").tz_localize("UTC")
    if target_time in df.index:
        row = df.loc[target_time]
        vol = row['volume']
        ma = row['vol_ma']
        ratio = vol / ma if ma > 0 else 0
        prev_vol = df.shift(1).loc[target_time]['volume']
        prev_ratio = vol / prev_vol if prev_vol > 0 else 0
        
        print(f"\n🔍 DETAY ANALİZ (06:15):")
        print(f"Hacim: {int(vol)}")
        print(f"Ortalama (21): {int(ma)}")
        print(f"VBOY (Ortalamaya Göre): {ratio:.2f} Kat")
        print(f"Önceki Bara Göre: {prev_ratio:.2f} Kat")
    else:
        print("Veri bulunamadı.")

    # --- DISCRIMINANT ANALYSIS ---
    wins = [e for e in found_events if e['gain'] >= 5.0]
    fakes = [e for e in found_events if e['gain'] < 5.0]
    
    print("\n" + "="*80)
    print(f"FAKE VS WIN ANALİZİ (HEDEF: %5 ALTI ELENECEK)")
    print("="*80)
    
    def get_avg(lst, key):
        if not lst: return 0
        return sum([x[key] for x in lst]) / len(lst)
        
    print(f"{'METRİK':<15} | {'WIN (Ort)':<10} | {'FAKE (Ort)':<10} | {'FARK'} | {'WIN (Min/Max)'}")
    print("-" * 80)
    metrics = ['vboy', 'v100', 'spread', 'atr', '1h_e']
    
    for m in metrics:
        avg_w = get_avg(wins, m)
        avg_f = get_avg(fakes, m)
        diff = avg_w - avg_f
        
        min_w = min([x[m] for x in wins]) if wins else 0
        max_w = max([x[m] for x in wins]) if wins else 0
        
        print(f"{m.upper():<15} | {avg_w:<10.2f} | {avg_f:<10.2f} | {diff:+.2f} | {min_w:.2f} / {max_w:.2f}")
        
    print("-" * 80)
    print(f"WIN Sayısı: {len(wins)}")
    print(f"FAKE Sayısı: {len(fakes)}")
    print(f"Toplam: {len(found_events)}")

    # --- OPTIMIZER (GRID SEARCH) ---
    print("\n" + "="*80)
    print(f"EN İYİ FİLTRE ARANIYOR (Win > %5, Fake < %5)...")
    print("="*80)
    
    best_score = -9999
    best_cfg = None
    best_stats = None
    
    atr_thresholds = [0.3, 0.5, 0.7, 0.9]
    rsi_thresholds = [38, 40, 42, 45, 48]
    spread_thresholds = [0.5, 1.0, 1.5, 2.0, 2.5]
    
    # We want to keep wins and kill fakes
    total_wins = len(wins)
    total_fakes = len(fakes)
    
    for atr_min in atr_thresholds:
        for rsi_max in rsi_thresholds:
            for spread_min in spread_thresholds:
                
                kept_wins = [w for w in wins if w['atr'] >= atr_min and w['1h_e'] <= rsi_max and w['spread'] >= spread_min]
                kept_fakes = [f for f in fakes if f['atr'] >= atr_min and f['1h_e'] <= rsi_max and f['spread'] >= spread_min]
                
                n_wins = len(kept_wins)
                n_fakes = len(kept_fakes)
                
                # Scoring: We value keeping wins highly, but punishing fakes is key
                # Win Rate = n_wins / (n_wins + n_fakes)
                if (n_wins + n_fakes) > 0:
                    wr = (n_wins / (n_wins + n_fakes)) * 100
                else:
                    wr = 0
                
                # Custom Score: High WR + High Win Retention
                # Penalty for losing too many wins
                win_retention = (n_wins / total_wins) * 100 if total_wins > 0 else 0
                
                # We want WR > 60% and Retention > 50%
                score = wr + (win_retention * 0.5)
                
                if score > best_score and n_wins > 10: # Min 10 samples
                    best_score = score
                    best_cfg = (atr_min, rsi_max, spread_min)
                    best_stats = (n_wins, n_fakes, wr, win_retention)

    print(f"BULUNAN EN İYİ FORMÜL:")
    print(f"ATR > {best_cfg[0]}  VE  1H_E < {best_cfg[1]}  VE  SPREAD > {best_cfg[2]}")
    print(f"--------------------------------------------------")
    print(f"KALAN WIN  : {best_stats[0]} / {total_wins} (Kayıp: %{100-best_stats[3]:.1f})")
    print(f"KALAN FAKE : {best_stats[1]} / {total_fakes} (Temizlenen: %{(1 - best_stats[1]/total_fakes)*100:.1f})")
    print(f"YENİ BAŞARI: %{best_stats[2]:.1f} (Eski: %{total_wins/(total_wins+total_fakes)*100:.1f})")
    print(f"--------------------------------------------------")

except Exception as e:
    print(f"Error: {e}")
