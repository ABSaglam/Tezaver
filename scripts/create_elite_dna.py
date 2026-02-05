import json

INPUT_FILE = "dna_manifest_v6.json"
OUTPUT_FILE = "dna_manifest_v6_elite.json"

MIN_WIN_RATE = 55.0
MIN_SIGNALS = 10

def filter_dna():
    print(f"🧬 DNA Refining Process Started...")
    print(f"Criteria: Win Rate >= {MIN_WIN_RATE}% AND Signals >= {MIN_SIGNALS}")

    try:
        with open(INPUT_FILE, 'r') as f:
            manifest = json.load(f)
    except FileNotFoundError:
        print(f"❌ Input file not found: {INPUT_FILE}")
        return

    elite_manifest = {}
    total_strats = 0
    kept_strats = 0

    for symbol, strategies in manifest.items():
        elite_strats = []
        for s in strategies:
            total_strats += 1
            if s['win_rate'] >= MIN_WIN_RATE and s['total_signals'] >= MIN_SIGNALS:
                elite_strats.append(s)
        
        if elite_strats:
            elite_manifest[symbol] = elite_strats
            kept_strats += len(elite_strats)

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(elite_manifest, f, indent=2)

    print(f"✅ Scanning Complete.")
    print(f"Original Strategies: {total_strats}")
    print(f"Elite Strategies:    {kept_strats}")
    print(f"Eliminated:          {total_strats - kept_strats}")
    print(f"Elite DNA saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    filter_dna()
