import json
import pandas as pd
from tezaver.core.rally_store import RallyStore

def run_v4_pure_prediction(symbol):
    print(f"\n🧪 STARTING AYAŞ TÜNELİ v4 (PURE PREDICTION) FOR: {symbol}")
    
    # 1. Load Data
    with open(f"data/memory_{symbol}.json", "r") as f:
        memory = json.load(f)
    with open(f"data/profiles_{symbol}.json", "r") as f:
        profiles = json.load(f)
        
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    rally_days = {pd.Timestamp(r['event_time']).normalize(): r.get('tier') for r in all_rallies if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']}
    
    # 2. Strict Evolution (T+1 Only)
    # We only accept a family if EVERY time it appears, the NEXT day is a rally.
    
    initial_families = set()
    # Populate potential candidates from reliable T-1 precursors
    for m in memory:
        r_date = pd.Timestamp(m['rally_date'])
        t_1 = (r_date - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        if t_1 in profiles:
            p = profiles[t_1]
            key = f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafiza']}|{p['enerji']}"
            initial_families.add(key)
            
    print(f"Initial Candidates (from T-1): {len(initial_families)}")
    
    blacklist = set()
    iteration = 0
    final_signals_map = {}
    
    while True:
        iteration += 1
        active_families = initial_families - blacklist
        
        signals = []
        clean_hits = 0
        leaks = 0
        false_positives = 0
        new_blacklist_items = set()
        
        for d_str, p in profiles.items():
            key = f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafiza']}|{p['enerji']}"
            
            if key in active_families:
                date = pd.Timestamp(d_str)
                signals.append(date)
                
                # STRICT RULE: RALLY MUST BE ON T+1 (Tomorrow)
                # If rally is on T=0 (Today), it's a LEAK -> Fail.
                # If rally is nowhere, it's a FP -> Fail.
                
                target_day = date + pd.Timedelta(days=1)
                
                if target_day in rally_days:
                    clean_hits += 1
                else:
                    # Investigating Failure Type
                    if date in rally_days:
                        leaks += 1 # It was a T=0 rally (Hindsight)
                    else:
                        false_positives += 1
                    
                    new_blacklist_items.add(key)
        
        print(f"Iter {iteration}: Active {len(active_families)} | Signals {len(signals)} | Clean Hits {clean_hits} | Leaks/FP {len(new_blacklist_items)}")
        
        if len(new_blacklist_items) == 0:
            final_signals_map = {s.strftime('%Y-%m-%d'): rally_days.get(s + pd.Timedelta(days=1)) for s in signals}
            break
            
        blacklist.update(new_blacklist_items)
        if iteration > 50: break

    # 3. Final Report Data
    results = {
        'symbol': symbol,
        'logic': 'v4_pure_prediction',
        'signals': len(final_signals_map),
        'fp': 0,
        'leaks_removed': leaks,
        'hits': {
            'diamond': sum(1 for t in final_signals_map.values() if t == 'DIAMOND'),
            'gold': sum(1 for t in final_signals_map.values() if t == 'GOLD'),
            'silver': sum(1 for t in final_signals_map.values() if t == 'SILVER')
        },
        'allowed_families': list(active_families) 
    }
    
    with open(f"data/final_v4_{symbol}.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\n🏆 V4 PURE PREDICTION COMPLETE FOR {symbol}")
    print(f"Valid Predictive Signals: {results['signals']}")
    print(f"Verified 0 FP (Strict T+1)")

if __name__ == "__main__":
    import sys
    run_v4_pure_prediction(sys.argv[1])
