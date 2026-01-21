import json
import pandas as pd
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core.rally_store import RallyStore

def compare_dgs(symbol):
    key_path = f"data/golden_keys/{symbol}_key.json"
    if not os.path.exists(key_path):
        print(json.dumps({"error": "No key found"}))
        return

    with open(key_path, "r") as f:
        key_data = json.load(f)
        
    allowed_families = set(key_data.get('golden_dna_list', []))
    
    # Load Data
    root = "coin_cells"
    df_w = pd.read_parquet(f"{root}/{symbol}/data/history_1w.parquet")
    df_d = pd.read_parquet(f"{root}/{symbol}/data/history_1d.parquet")
    df_h4 = pd.read_parquet(f"{root}/{symbol}/data/history_4h.parquet")
    df_h1 = pd.read_parquet(f"{root}/{symbol}/data/history_1h.parquet")

    for df in [df_w, df_d, df_h4, df_h1]:
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        df.sort_index(inplace=True)
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()

    def get_profile(day):
        sub_w = df_w[df_w.index <= day]
        if sub_w.empty: return "neutral"
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        
        faz = "neutral"
        if rsi_val < 40: faz = "derin_dip"
        elif rsi_val < 60: faz = "birikim_fazi"
        elif rsi_val < 75: faz = "yukselis_fazi"
        else: faz = "asiri_alim"
        
        sub_h1 = df_h1[df_h1.index <= day].tail(24)
        if sub_h1.empty: return "neutral"
        comp = (sub_h1[['ema9','ema21','ema50']].max(axis=1) / sub_h1[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "loose"
        if min_c < 0.4: acc = "micro_squeeze"
        elif min_c < 0.8: acc = "tight_squeeze"
        elif min_c < 1.5: acc = "coiling"
        
        sub_d = df_d[df_d.index <= day]
        sub_h4 = df_h4[df_h4.index <= day]
        if sub_d.empty or sub_h4.empty: return "neutral"
        s = sum([sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21'], 
                 sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21'], 
                 sub_h1.iloc[-1]['close']>sub_h1.iloc[-1]['ema21']])
        harm = f"harmony_L{s}"
        
        sub_d_tail = sub_d.tail(10)
        vol_pulse = sub_d_tail['volume'].iloc[-1] / (sub_d_tail['volume'].mean()+1)
        ritim = "active" if vol_pulse > 1.0 else "sleeping"
        if vol_pulse > 2.0: ritim = "ignited"
        
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        
        yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
        retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
        ctx = "mid_zone"
        if retr > -20: ctx = "recovery_high"
        elif retr < -50: ctx = "deep_valley"
        
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"

    # Total DGS + Gains
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    
    dgs_total = {'DIAMOND': 0, 'GOLD': 0, 'SILVER': 0}
    gains_total = {'DIAMOND': [], 'GOLD': [], 'SILVER': []}
    rally_map = {}
    
    for r in all_rallies:
        tier = r.get('tier')
        if tier in dgs_total:
            dgs_total[tier] += 1
            raw = r.get('raw_data', {})
            gain = raw.get('gain', 0) or raw.get('pnl', 0)
            gains_total[tier].append(gain)
            
            d = pd.Timestamp(r['event_time']).normalize()
            rally_map[d] = {'tier': tier, 'gain': gain}

    # v4 DGS + Gains
    dgs_v4 = {'DIAMOND': 0, 'GOLD': 0, 'SILVER': 0}
    gains_v4 = {'DIAMOND': [], 'GOLD': [], 'SILVER': []}
    
    for date in df_d.index:
        dna = get_profile(date)
        if dna in allowed_families:
            target_date = date + pd.Timedelta(days=1)
            if target_date in rally_map:
                info = rally_map[target_date]
                tier = info['tier']
                dgs_v4[tier] += 1
                gains_v4[tier].append(info['gain'])

    # Averages
    def avg(lst): return round(sum(lst)/len(lst), 2) if lst else 0

    avgs_total = {k: avg(v) for k, v in gains_total.items()}
    avgs_v4 = {k: avg(v) for k, v in gains_v4.items()}

    # Percentages
    total_count = sum(dgs_total.values())
    v4_count = sum(dgs_v4.values())
    
    pct_total = (v4_count / total_count * 100) if total_count > 0 else 0
    pct_d = (dgs_v4['DIAMOND'] / dgs_total['DIAMOND'] * 100) if dgs_total['DIAMOND'] > 0 else 0
    pct_g = (dgs_v4['GOLD'] / dgs_total['GOLD'] * 100) if dgs_total['GOLD'] > 0 else 0
    pct_s = (dgs_v4['SILVER'] / dgs_total['SILVER'] * 100) if dgs_total['SILVER'] > 0 else 0

    print(json.dumps({
        'total_counts': dgs_total,
        'total_avgs': avgs_total,
        'v4_counts': dgs_v4,
        'v4_avgs': avgs_v4,
        'pct': {
            'TOTAL': round(pct_total, 2),
            'DIAMOND': round(pct_d, 2),
            'GOLD': round(pct_g, 2),
            'SILVER': round(pct_s, 2)
        }
    }))

if __name__ == "__main__":
    compare_dgs(sys.argv[1])
