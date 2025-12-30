
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from tezaver.core.annotations import SniperAnnotationRepository

def check():
    repo = SniperAnnotationRepository()
    symbol = "ADAUSDT"
    tf = "15m"
    target_id = "ADAUSDT_15m_RVZ_D_1740896100"
    
    print(f"Loading {symbol} {tf}...")
    anns = repo.load_all(symbol, tf)
    
    found = False
    for ann in anns:
        if ann.event_id == target_id:
            found = True
            print(f"FOUND {ann.event_id}")
            print(f"  rev_gain (obj): {ann.rev_gain}")
            print(f"  dict raw: {ann.to_dict()}")
            break
            
    if not found:
        print("Target ID NOT FOUND in loaded list.")
        # Debug: check file content manually?
        
if __name__ == "__main__":
    check()
