from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

from tezaver.sniper.sniper_annotations import SniperAnnotationRepository

def main():
    repo = SniperAnnotationRepository(base_dir=Path("data/sniper"))
    
    # 1. Start from coin_cells to find active symbols (or just glob the data dir)
    # Using data dir glob is safer to catch everything
    data_dir = Path("data/sniper")
    if not data_dir.exists():
        print("No data/sniper directory found.")
        return

    print("--- ONY APPROVED LIST ---")
    count = 0
    # Structure: data/sniper/{SYMBOL}/{TF}/sniper_annotations_v1.json
    for sym_dir in data_dir.iterdir():
        if not sym_dir.is_dir(): continue
        symbol = sym_dir.name
        
        for tf_dir in sym_dir.iterdir():
            if not tf_dir.is_dir(): continue
            timeframe = tf_dir.name
            
            anns = repo.load_all(symbol, timeframe)
            approved = [a for a in anns if a.status == "APPROVED"]
            
            for a in approved:
                print(f"[{symbol} {timeframe}] {a.event_id} | Label: {a.label} | Note: {a.note}")
                count += 1
                
    if count == 0:
        print("No approved annotations found.")
    else:
        print(f"\nTotal: {count} approved items.")

if __name__ == "__main__":
    main()
