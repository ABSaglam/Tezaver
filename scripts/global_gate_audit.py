import json
import os
import glob
from collections import Counter

def run_audit():
    print("🩺 GLOBAL GATE AUDIT: X-RAY PHASE STARTING...")
    
    key_files = glob.glob("data/golden_keys/*_key.json")
    print(f"🔍 Found {len(key_files)} Golden Keys.")

    dna_frequency = Counter()
    dna_to_symbols = {}
    
    component_analysis = {
        'faz': Counter(),
        'acc': Counter(),
        'harm': Counter(),
        'ritim': Counter(),
        'ctx': Counter(),
        'enerji': Counter()
    }

    processed_count = 0
    for file_path in key_files:
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                symbol = data.get('symbol')
                dna_list = data.get('golden_dna_list', [])
                
                for dna in dna_list:
                    if dna == "neutral": continue
                    
                    dna_frequency[dna] += 1
                    if dna not in dna_to_symbols:
                        dna_to_symbols[dna] = []
                    dna_to_symbols[dna].append(symbol)
                    
                    # Component Breakdown
                    parts = dna.split('|')
                    if len(parts) == 6:
                        component_analysis['faz'][parts[0]] += 1
                        component_analysis['acc'][parts[1]] += 1
                        component_analysis['harm'][parts[2]] += 1
                        component_analysis['ritim'][parts[3]] += 1
                        component_analysis['ctx'][parts[4]] += 1
                        component_analysis['enerji'][parts[5]] += 1
            
            processed_count += 1
        except Exception as e:
            print(f"⚠️ Error processing {file_path}: {e}")

    print(f"✅ Processed {processed_count} keys.")

    # 1. TOP UNIVERSAL DNA strings
    top_dna = dna_frequency.most_common(20)
    
    # 2. Results Preparation
    results = {
        "summary": {
            "total_keys_processed": processed_count,
            "unique_dna_count": len(dna_frequency)
        },
        "top_universal_dna": [
            {"dna": d, "count": c, "symbols": dna_to_symbols[d][:5]} # Show first 5 symbols
            for d, c in top_dna
        ],
        "component_breakdown": {
            k: dict(v.most_common()) for k, v in component_analysis.items()
        }
    }

    output_path = "data/global_audit_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"🏁 Audit complete. Results saved to {output_path}")

    # Generate Markdown Report
    report_path = "GLOBAL_GATE_AUDIT_REPORT.md"
    with open(report_path, "w") as f:
        f.write("# 🩺 GLOBAL GATE AUDIT: MARKET ANATOMY REPORT\n\n")
        f.write(f"**Analiz Tarihi:** 2026-01-21\n")
        f.write(f"**Kapsam:** {processed_count} Koin Altın Anahtarı\n\n")
        
        f.write("## 🏛️ 1. EVRENSEL DNA'LAR (EN SIK RASTLANAN)\n")
        f.write("Aşağıdaki DNA (Kapı) kombinasyonları, market genelinde en çok koinde ralli kilitleyen yapılardır.\n\n")
        f.write("| DNA (Profil) | Koin Sayısı | Örnek Koinler |\n")
        f.write("| :--- | :---: | :--- |\n")
        for item in results['top_universal_dna']:
            koinler = ", ".join(item['symbols'])
            f.write(f"| `{item['dna']}` | {item['count']} | {koinler} |\n")
        
        f.write("\n## 🧼 2. BİLEŞEN ANALİZİ (Component Breakdown)\n")
        f.write("Ralli kapılarının içindeki tekil özelliklerin tüm marketteki ağırlıkları.\n\n")
        
        for comp, counts in results['component_breakdown'].items():
            f.write(f"### 📍 {comp.upper()}\n")
            f.write("| Değer | Frekans |\n")
            f.write("| :--- | :---: |\n")
            for val, count in counts.items():
                f.write(f"| {val} | {count} |\n")
            f.write("\n")
            
    print(f"📄 Markdown report generated: {report_path}")

if __name__ == "__main__":
    run_audit()
