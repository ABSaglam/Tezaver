import json
import pandas as pd

def run_evolution():
    # Load 1D Ground Truth
    symbol = "ALGOUSDT"
    df_d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
    df_d['dt'] = pd.to_datetime(df_d['timestamp'], unit='ms')
    df_d.set_index('dt', inplace=True)
    
    # Load Reality (Rallies)
    from tezaver.core.rally_store import RallyStore
    store = RallyStore()
    all_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
    rally_days = {pd.Timestamp(r['event_time']).normalize(): r.get('tier', 'SILVER') for r in all_rallies if r.get('tier') in ['DIAMOND', 'GOLD', 'SILVER']}

    # Load All Daily Profiles
    with open("data/algo_lockstate_profiles.json", "r") as f:
        profiles = json.load(f)

    # Initial Allowed Families (from Stage 3)
    with open("data/algo_lockstate_families.json", "r") as f:
        allowed_families = set(json.load(f).keys())

    # Pre-defined Contradiction Filters (User's Phase 4 Rules)
    def has_contradiction(p):
        if p['faz'] in ['geç']: return True
        if p['birikim'] == 'rahat': return True
        if p['uyum'] == 'uyumsuz': return True
        if p['ritim'] in ['aceleci', 'kesik']: return True
        if p['hafıza'] == 'anlamsız': return True
        return False

    iteration = 0
    blacklist = set()

    while True:
        iteration += 1
        signals = []
        hits = []
        misses = []
        
        # Current Active Key Rules: Allowed Families + NO Contradiction + NOT in Blacklist
        active_families = allowed_families - blacklist
        
        for date_str, p in profiles.items():
            date = pd.Timestamp(date_str)
            family_key = f"{p['faz']}|{p['birikim']}|{p['uyum']}|{p['ritim']}|{p['hafıza']}"
            
            # THE KEY CHECK
            if family_key in active_families and not has_contradiction(p):
                signals.append((date_str, family_key))
                
                # Check if rally actually happened in next 48h
                found = False
                for d_offset in [0, 1]:
                    check_day = date + pd.Timedelta(days=d_offset)
                    if check_day in rally_days:
                        found = True
                        hits.append((date_str, rally_days[check_day]))
                        break
                
                if not found:
                    misses.append((date_str, family_key))

        print(f"Iteration {iteration}: Signals: {len(signals)} | Hits: {len(hits)} | Misses: {len(misses)}")
        
        if len(misses) == 0:
            print("🏁 ZERO FALSE POSITIVE ACHIEVED.")
            break
            
        # EVOLUTION: Blacklist all profiles that missed
        for _, fam in misses:
            blacklist.add(fam)
            
        if iteration > 100: # Safety break
            print("Safety break reached.")
            break

    # Save Final Lock-State
    final_state = {
        'iteration_id': iteration,
        'logic': 'Deterministic Lock-State (Ayaş v2)',
        'allowed_families': list(active_families),
        'results': {
            'total_active_days': len(signals),
            'diamond': sum(1 for _, t in hits if t == 'DIAMOND'),
            'gold': sum(1 for _, t in hits if t == 'GOLD'),
            'silver': sum(1 for _, t in hits if t == 'SILVER'),
            'false_positives': len(misses)
        }
    }
    
    with open("data/algo_lockstate_final.json", "w") as f:
        json.dump(final_state, f, indent=2)
        
    print(f"\n✅ Final Lock-State report generated in data/algo_lockstate_final.json")

if __name__ == "__main__":
    run_evolution()
