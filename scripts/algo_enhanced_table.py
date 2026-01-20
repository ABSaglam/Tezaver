
import sys
import os
import pandas as pd
import numpy as np
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from db_helper import get_rallies, TRAIN_CUTOFF

def get_faz(rsi, rsi_slope):
    if rsi < 35: return "erken"
    if rsi > 70: return "geç"
    if 35 <= rsi < 50 and rsi_slope > 0: return "eşik"
    return "olgun"

def get_birikim(atr_score, vol_change):
    if atr_score < 1.2:
        if vol_change > 0: return "taşmak_üzere"
        return "bastırılmış"
    return "rahat"

def get_uyum(w_trend, d_trend, h4_trend):
    directions = [1 if t > 0 else -1 if t < 0 else 0 for t in [w_trend, d_trend, h4_trend]]
    unique_dirs = len(set(directions))
    if unique_dirs == 1: return "itirazsız"
    if unique_dirs == 2: return "kısmi_uyum"
    return "uyumsuz"

def get_tempo(vol_cv):
    if vol_cv < 0.4: return "dengeli"
    if vol_cv > 0.8: return "kesik"
    return "aceleci"

def get_hafiza(w_rsi):
    if w_rsi < 35: return "anlamlı_dip"
    if w_rsi > 70: return "anlamlı_tepe"
    return "tanıdık"

def calc_indicators(df):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi_slope'] = df['rsi'].diff(3)
    
    ema21 = df['close'].ewm(span=21).mean()
    ema50 = df['close'].ewm(span=50).mean()
    df['h4_trend'] = (ema21 / ema50 - 1) * 100
    
    df['vol_change'] = df['volume'].diff(3)
    df['vol_cv'] = df['volume'].rolling(12).std() / df['volume'].rolling(12).mean()
    
    df['tr'] = np.maximum(df['high'] - df['low'], abs(df['close'].shift(1) - df['close']))
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_ratio'] = df['atr'] / df['close'] * 100
    df['atr_min'] = df['atr_ratio'].rolling(50).min()
    df['atr_score'] = df['atr_ratio'] / df['atr_min']
    
    return df

def main():
    symbol = 'ALGOUSDT'
    
    # Load 1D data for next day calculation
    d1_path = f"coin_cells/{symbol}/data/history_1d.parquet"
    df_1d = pd.read_parquet(d1_path)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['date'] = df_1d['datetime'].dt.date
    df_1d = df_1d.sort_values('date').reset_index(drop=True)
    
    # Create next day change map
    df_1d['next_close'] = df_1d['close'].shift(-1)
    df_1d['next_day_pct'] = (df_1d['next_close'] / df_1d['close'] - 1) * 100
    next_day_map = dict(zip(df_1d['date'], df_1d['next_day_pct']))
    
    # Load H4 data
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    df_h4 = pd.read_parquet(h4_path)
    df_h4 = df_h4.sort_values('timestamp').reset_index(drop=True)
    df_h4['datetime'] = pd.to_datetime(df_h4['timestamp'], unit='ms')
    df_h4 = df_h4[df_h4['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_h4 = calc_indicators(df_h4)
    
    df_d = df_h4.set_index('datetime').resample('1D').agg({'close': 'last'})
    ema21_d = df_d['close'].ewm(span=21).mean()
    ema50_d = df_d['close'].ewm(span=50).mean()
    df_d['d_trend'] = (ema21_d / ema50_d - 1) * 100
    df_d_re = df_d.reindex(df_h4['datetime'], method='ffill')
    df_h4['d_trend'] = df_d_re['d_trend'].values
    
    df_w = df_h4.set_index('datetime').resample('1W').agg({'close': 'last'})
    delta_w = df_w['close'].diff()
    gain_w = (delta_w.where(delta_w > 0, 0)).rolling(14).mean()
    loss_w = (-delta_w.where(delta_w < 0, 0)).rolling(14).mean()
    rs_w = gain_w / loss_w
    df_w['w_rsi'] = 100 - (100 / (1 + rs_w))
    ema21_w = df_w['close'].ewm(span=21).mean()
    ema50_w = df_w['close'].ewm(span=50).mean()
    df_w['w_trend'] = (ema21_w / ema50_w - 1) * 100
    df_w_re = df_w.reindex(df_h4['datetime'], method='ffill')
    df_h4['w_rsi'] = df_w_re['w_rsi'].values
    df_h4['w_trend'] = df_w_re['w_trend'].values
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    rally_dates = list(rally_results.keys())
    
    journey_offsets = [1, 3, 5, 7, 14, 21]
    journey_dates = set()
    journey_map = {}
    for rd in rally_dates:
        journey_dates.add(rd)
        journey_map[rd] = (f"T-0", rd, rally_results[rd][0])
        for offset in journey_offsets:
            prep_day = rd - timedelta(days=offset)
            journey_dates.add(prep_day)
            if prep_day not in journey_map:
                journey_map[prep_day] = (f"T-{offset}", rd, rally_results[rd][0])
    
    midnight = df_h4[df_h4['datetime'].dt.hour == 0].copy().reset_index(drop=True)
    midnight['date'] = midnight['datetime'].dt.date
    
    midnight['profile'] = midnight.apply(lambda row: 
        f"{get_faz(row['rsi'], row['rsi_slope'])} | " +
        f"{get_birikim(row['atr_score'], row['vol_change'])} | " +
        f"{get_uyum(row['w_trend'], row['d_trend'], row['h4_trend'])} | " +
        f"{get_tempo(row['vol_cv'])} | " +
        f"{get_hafiza(row['w_rsi'])}", axis=1
    )
    
    midnight['is_journey'] = midnight['date'].isin(journey_dates)
    midnight['is_rally_day'] = midnight['date'].isin(rally_dates)
    
    candidate_profiles = midnight[midnight['is_journey']]['profile'].unique()
    
    survivors = []
    for prof in candidate_profiles:
        mask = midnight['profile'] == prof
        occurrences = midnight[mask]
        non_journey = occurrences[~occurrences['is_journey']]
        if len(non_journey) == 0:
            survivors.append(prof)
    
    surviving_days = midnight[midnight['profile'].isin(survivors)].copy()
    surviving_days = surviving_days.sort_values('date')
    
    # Output as markdown table
    print("| # | Tarih | Profil | Durum | Ertesi Gün % |")
    print("|---|-------|--------|-------|-------------|")
    
    for i, (_, row) in enumerate(surviving_days.iterrows(), 1):
        d = row['date']
        prof = row['profile']
        next_pct = next_day_map.get(d, None)
        next_pct_str = f"{next_pct:+.1f}%" if next_pct is not None else "N/A"
        
        if row['is_rally_day']:
            tier = rally_results[d][0]
            status = f"🟢 RALLİ ({tier})"
            next_pct_str = "-" # Rally day, not relevant
        else:
            offset, target_date, tier = journey_map.get(d, ("?", "?", "?"))
            status = f"⚫ {offset} → {target_date} ({tier})"
            
        print(f"| {i} | {d} | {prof} | {status} | {next_pct_str} |")

if __name__ == "__main__":
    main()
