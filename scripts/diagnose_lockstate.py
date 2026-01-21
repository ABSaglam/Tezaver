import json
import pandas as pd

def diagnose_lockstate():
    with open("data/algo_journey_memory.json", "r") as f:
        memory = json.load(f)
    with open("data/algo_lockstate_profiles.json", "r") as f:
        profiles = json.load(f)

    # Contradiction Filters (User's Phase 4 Rules)
    def check_contradiction(p):
        reasons = []
        if p['faz'] in ['geç']: reasons.append("faz_geç")
        if p['birikim'] == 'rahat': reasons.append("birikim_rahat")
        if p['uyum'] == 'uyumsuz': reasons.append("uyum_uyumsuz")
        if p['ritim'] in ['aceleci', 'kesik']: reasons.append("ritim_bozuk")
        if p['hafıza'] == 'anlamsız': reasons.append("hafıza_bos")
        return reasons

    stats = []
    for r in memory:
        # Check T-1 (The Day Before Rally)
        t_1_day = (pd.Timestamp(r['rally_date']) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        if t_1_day in profiles:
            p = profiles[t_1_day]
            reasons = check_contradiction(p)
            stats.append({
                'date': r['rally_date'],
                'type': r['type'],
                'p_faz': p['faz'],
                'p_birikim': p['birikim'],
                'p_uyum': p['uyum'],
                'p_ritim': p['ritim'],
                'p_hafıza': p['hafıza'],
                'reasons': ", ".join(reasons) if reasons else "CLEAN"
            })
            
    df = pd.DataFrame(stats)
    print("📊 T-1 PROFILES FOR 169 RALLIES:")
    print("-" * 50)
    print(df['reasons'].value_counts())
    
    print("\n🔍 MOST COMMON CONTRADICTIONS:")
    all_reasons = []
    for r in df['reasons']:
        if r != "CLEAN": all_reasons.extend(r.split(", "))
    print(pd.Series(all_reasons).value_counts())

if __name__ == "__main__":
    diagnose_lockstate()
