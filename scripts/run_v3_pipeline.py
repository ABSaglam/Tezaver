import sys
import os
import json
import pandas as pd
import numpy as np
from tezaver.core.rally_store import RallyStore

def run_v3_pipeline(symbol):
    print(f"\n🚀 STARTING AYAŞ TÜNELİ v3 PIPELINE FOR: {symbol}")
    
    # 1. JOURNEY MEMORY
    print(f"🧠 Stage 1: Building Journey Memory...")
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    dgs = [r for r in all_rallies if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']]
    
    memory = []
    for r in dgs:
        r_date = pd.Timestamp(r['event_time']).normalize()
        journey = []
        for d in [1, 3, 5, 7, 14, 21]:
            journey.append((r_date - pd.Timedelta(days=d)).strftime('%Y-%m-%d'))
        
        memory.append({
            'rally_date': r_date.strftime('%Y-%m-%d'),
            'tier': r['tier'],
            'journey_days': journey
        })
    
    mem_path = f"data/memory_{symbol}.json"
    with open(mem_path, "w") as f:
        json.dump(memory, f, indent=2)
    print(f"✅ Memory saved: {len(memory)} rallies.")

    # 2. ATOMIC PROFILING (6D)
    print(f"🧩 Stage 2: Mapping Atomic Profiles (6D)...")
    try:
        df_w = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
        df_d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
        df_h4 = pd.read_parquet(f"coin_cells/{symbol}/data/history_4h.parquet")
        df_h1 = pd.read_parquet(f"coin_cells/{symbol}/data/history_1h.parquet")
    except Exception as e:
        print(f"❌ Data missing for {symbol}: {e}")
        return

    for df in [df_w, df_d, df_h4, df_h1]:
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        df.sort_index(inplace=True)
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))

    def v_faz(day):
        subset = df_w[df_w.index <= day]
        if subset.empty: return "baslangic"
        w = subset.iloc[-1]
        if w['rsi'] < 40: return "derin_dip"
        if w['rsi'] < 60: return "birikim_fazi"
        if w['rsi'] < 75: return "yukselis_fazi"
        return "asiri_alim"

    def v_birikim(day):
        h1 = df_h1[df_h1.index <= day].tail(24)
        if h1.empty: return "yok"
        comp = (h1[['ema9', 'ema21', 'ema50']].max(axis=1) / h1[['ema9', 'ema21', 'ema50']].min(axis=1) - 1) * 100
        min_c = comp.min()
        if min_c < 0.4: return "micro_squeeze"
        if min_c < 0.8: return "tight_squeeze"
        if min_c < 1.5: return "coiling"
        return "loose"

    def v_uyum(day):
        d_sub = df_d[df_d.index <= day]
        h4_sub = df_h4[df_h4.index <= day]
        h1_sub = df_h1[df_h1.index <= day]
        if d_sub.empty or h4_sub.empty or h1_sub.empty: return "yok"
        s = sum([d_sub.iloc[-1]['close'] > d_sub.iloc[-1]['ema21'], 
                 h4_sub.iloc[-1]['close'] > h4_sub.iloc[-1]['ema21'], 
                 h1_sub.iloc[-1]['close'] > h1_sub.iloc[-1]['ema21']])
        return f"harmony_L{s}"

    def v_ritim(day):
        d_tail = df_d[df_d.index <= day].tail(3)
        if d_tail.empty: return "yok"
        vol_pulse = d_tail['volume'].iloc[-1] / (d_tail['volume'].mean() + 1)
        if vol_pulse > 2.0: return "ignited"
        if vol_pulse > 1.0: return "active"
        return "sleeping"

    def v_hafiza(day):
        d_sub = df_d[df_d.index <= day]
        if d_sub.empty: return "yok"
        yr_high = d_sub.tail(365)['high'].max()
        retr = (d_sub.iloc[-1]['close'] / yr_high - 1) * 100
        if retr > -20: return "recovery_high"
        if retr > -50: return "mid_zone"
        return "deep_valley"

    def v_enerji(day):
        d_tail = df_d[df_d.index <= day].tail(10)
        if len(d_tail) < 5: return "neutral"
        v_trend = d_tail['volume'].tail(3).mean() > d_tail['volume'].head(7).mean()
        return "building_energy" if v_trend else "depleting_energy"

    profiles = {}
    target_days = df_d.index
    for day in target_days:
        profiles[day.strftime('%Y-%m-%d')] = {
            'faz': v_faz(day), 'birikim': v_birikim(day), 'uyum': v_uyum(day),
            'ritim': v_ritim(day), 'hafiza': v_hafiza(day), 'enerji': v_enerji(day)
        }
    
    prof_path = f"data/profiles_{symbol}.json"
    with open(prof_path, "w") as f:
        json.dump(profiles, f, indent=2)
    print(f"✅ Profiles mapped.")

    # 3. EVOLUTION (0 FP Target)
    print(f"🧬 Stage 3: Running Evolution Loop...")
    rally_days = {pd.Timestamp(r['rally_date']): r['tier'] for r in memory}
    
    # Discovery: Initial families from rally precursors
    initial_families = set()
    for m in memory:
        for j_day in m['journey_days']:
            if j_day in profiles:
                p = profiles[j_day]
                initial_families.add(f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafiza']}|{p['enerji']}")

    blacklist = set()
    iteration = 0
    final_signals = []
    
    while True:
        iteration += 1
        active_families = initial_families - blacklist
        signals = []
        misses = []
        
        for d_str, p in profiles.items():
            key = f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafiza']}|{p['enerji']}"
            if key in active_families:
                date = pd.Timestamp(d_str)
                found = False
                for off in [0, 1]:
                    if date + pd.Timedelta(days=off) in rally_days:
                        found = True; break
                
                signals.append(d_str)
                if not found:
                    misses.append(key)
        
        if not misses or iteration > 100:
            final_signals = signals
            break
        for m in misses: blacklist.add(m)

    # 4. REPORT
    results = {
        'symbol': symbol,
        'signals': len(final_signals),
        'fp': 0,
        'allowed_families': list(active_families),
        'hits': {
            'diamond': sum(1 for s in final_signals if rally_days.get(pd.Timestamp(s)) == 'DIAMOND' or rally_days.get(pd.Timestamp(s)+pd.Timedelta(days=1)) == 'DIAMOND'),
            'gold': sum(1 for s in final_signals if rally_days.get(pd.Timestamp(s)) == 'GOLD' or rally_days.get(pd.Timestamp(s)+pd.Timedelta(days=1)) == 'GOLD'),
            'silver': sum(1 for s in final_signals if rally_days.get(pd.Timestamp(s)) == 'SILVER' or rally_days.get(pd.Timestamp(s)+pd.Timedelta(days=1)) == 'SILVER'),
        }
    }
    
    res_path = f"data/final_v3_{symbol}.json"
    with open(res_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n🏁 V3 PIPELINE COMPLETE FOR {symbol}")
    print(f"Total Signals: {results['signals']} | FP: 0")
    print(f"Distribution: D:{results['hits']['diamond']} G:{results['hits']['gold']} S:{results['hits']['silver']}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_v3_pipeline.py <SYMBOL>")
    else:
        run_v3_pipeline(sys.argv[1])
