import pandas as pd
import json
import os

INPUT_CSV = "/Users/alisaglam/TezaverMac/HAM_DNA_HAVUZU_2023_2025.csv"
OUTPUT_JSON = "/Users/alisaglam/TezaverMac/data/faz100_dna_keys_V2.json"

def generate_manifest():
    print("🏛️ DNA v2 Mühürleme Operasyonu Başlatıldı...")
    
    if not os.path.exists(INPUT_CSV):
        print(f"❌ Hata: {INPUT_CSV} bulunamadı!")
        return

    df = pd.read_csv(INPUT_CSV)
    # Success: P-21 >= 3% and MDD >= -2%
    df['is_success'] = (df['max'] >= 3.0) & (df['mdd'] >= -2.0)
    
    # Coin-Specific Analysis
    symbols = df['symbol'].unique()
    manifest = {}
    
    total_a_plus_plus = 0
    total_a_plus = 0
    
    for sym in symbols:
        sym_df = df[df['symbol'] == sym]
        dna_stats = sym_df.groupby('dna').agg(
            TOTAL=('is_success', 'count'),
            SUCCESS=('is_success', 'sum')
        ).reset_index()
        
        dna_stats['WR'] = (dna_stats['SUCCESS'] / dna_stats['TOTAL']) * 100
        
        sym_manifest = {}
        for _, row in dna_stats.iterrows():
            dna = row['dna']
            wr = row['WR']
            total = row['TOTAL']
            
            klasman = "C"
            # Rütbe Nizamı (Sıkılaştırma)
            if wr == 100 and total >= 3: 
                klasman = "A++"
                total_a_plus_plus += 1
            elif wr >= 95 and total >= 4: 
                klasman = "A+"
                total_a_plus += 1
            elif wr >= 90 and total >= 5: 
                klasman = "A"
            elif wr >= 85 and total >= 8: 
                klasman = "B++"
            elif wr >= 80 and total >= 10: 
                klasman = "B+"
            
            if klasman != "C":
                sym_manifest[dna] = {
                    'KLAS': klasman,
                    'WR': round(wr, 1),
                    'TOTAL': int(total)
                }
        
        if sym_manifest:
            manifest[sym] = sym_manifest
            
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(manifest, f, indent=4)
    
    print(f"✅ Mühürleme Tamamlandı: {OUTPUT_JSON}")
    print(f"🏛️ A++ (Zero-Loss) Sayısı: {total_a_plus_plus}")
    print(f"🏛️ A+ (Elite) Sayısı: {total_a_plus}")
    print(f"🏛️ Toplam Rütbeli Koin Sayısı: {len(manifest)}")

if __name__ == "__main__":
    generate_manifest()
