import pandas as pd
import json
import os

# CONFIG
INPUT_CSV = "/Users/alisaglam/TezaverMac/HAM_DNA_V01_2025.csv"
OUTPUT_JSON = "/Users/alisaglam/TezaverMac/data/V01_dna_keys_2025_A_plus_plus.json"

def generate_V01_manifest():
    print("🏛️ V01: Simya Operasyonu Başladı...")
    if not os.path.exists(INPUT_CSV):
        print(f"❌ Hata: {INPUT_CSV} bulunamadı!")
        return

    df = pd.read_csv(INPUT_CSV)
    print(f"📊 Toplam Örnek: {len(df)}")

    # ⚖️ V01 KRİTERLERİ (Elmas)
    # 1. Zero-Loss (MDD >= -2.0)
    # 2. Kar Primi (Max >= 10.0)
    
    # Her koin için ayrı analiz
    manifest = {}
    
    symbols = df['symbol'].unique()
    total_found = 0

    for symbol in symbols:
        sdf = df[df['symbol'] == symbol]
        # DNA bazlı grupla
        dna_groups = sdf.groupby('dna').agg({
            'max': ['count', 'mean', 'min'],
            'mdd': ['min', 'mean'],
            'exit': 'mean'
        })
        
        # Flatten columns
        dna_groups.columns = ['_'.join(col).strip() for col in dna_groups.columns.values]
        
        # Süzgeç: MDD_min >= -2.0 AND max_min >= 10.0 AND max_count >= 2
        elmas_dna = dna_groups[
            (dna_groups['mdd_min'] >= -2.0) & 
            (dna_groups['max_min'] >= 10.0) & 
            (dna_groups['max_count'] >= 2)
        ]
        
        if not elmas_dna.empty:
            manifest[symbol] = {}
            for dna, row in elmas_dna.iterrows():
                manifest[symbol][dna] = {
                    'KLAS': 'A++',
                    'Count': int(row['max_count']),
                    'AvgMax': round(float(row['max_mean']), 2),
                    'MinMax': round(float(row['max_min']), 2),
                    'AvgExit': round(float(row['exit_mean']), 2),
                    'MaxMDD': round(float(row['mdd_min']), 2)
                }
                total_found += 1

    # Save to JSON
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(manifest, f, indent=4)
    
    print(f"✅ V01 SİMYA TAMAMLANDI: {total_found} adet ELMAS (A++) DNA mühürlendi.")
    print(f"📁 Dosya: {OUTPUT_JSON}")

if __name__ == "__main__":
    generate_V01_manifest()
