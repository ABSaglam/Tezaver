import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from tezaver.core.config import DEFAULT_COINS
from tezaver.core import coin_cell_paths

def diagnose_data():
    report = []
    for symbol in DEFAULT_COINS:
        cell_dir = coin_cell_paths.get_coin_data_dir(symbol)
        
        h15m = (cell_dir / "history_15m.parquet").exists()
        h1h = (cell_dir / "history_1h.parquet").exists()
        h4h = (cell_dir / "history_4h.parquet").exists()
        h1d = (cell_dir / "history_1d.parquet").exists()
        
        f15m = (cell_dir / "features_15m.parquet").exists()
        
        rally_file = Path(f"library/fast15_rallies/{symbol}/fast15_rallies.parquet")
        rallies = rally_file.exists()
        
        report.append({
            "symbol": symbol,
            "h15m": h15m,
            "h1h": h1h,
            "h4h": h4h,
            "h1d": h1d,
            "f15m": f15m,
            "rallies": rallies
        })
    
    df = pd.DataFrame(report)
    print("--- DATA DIAGNOSTICS ---")
    print(f"Total Coins in Config: {len(DEFAULT_COINS)}")
    print(f"Coins with ALL History: {len(df[df[['h15m', 'h1h', 'h4h', 'h1d']].all(axis=1)])}")
    print(f"Coins with Features: {len(df[df['f15m']])}")
    print(f"Coins with Rallies: {len(df[df['rallies']])}")
    
    missing_any = df[~df[['h15m', 'h1h', 'h4h', 'h1d', 'f15m', 'rallies']].all(axis=1)]
    print(f"Coins missing SOMETHING: {len(missing_any)}")
    
    if len(missing_any) > 0:
        print("\nSample of missing coins:")
        print(missing_any.head(10).to_string())

if __name__ == "__main__":
    diagnose_data()
