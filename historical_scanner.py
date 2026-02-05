import json
import pandas as pd
from module4_synthesis import DiamondSynthesisEngine
from tqdm import tqdm
import os
from pathlib import Path

class HistoricalDiamondScanner:
    def __init__(self, symbols=None):
        self.engine = DiamondSynthesisEngine()
        if symbols:
            self.symbols = symbols
        else:
            self.symbols = [d for d in os.listdir("coin_cells") if os.path.isdir(os.path.join("coin_cells", d))]

    def scan_latest(self, limit=20):
        all_diamonds = []
        test_symbols = self.symbols[:limit]
        print(f"Scanning latest window for {len(test_symbols)} symbols...")
        for symbol in tqdm(test_symbols):
            try:
                result = self.engine.run_discovery(symbol)
                if result: all_diamonds.append(result)
            except: continue
        return all_diamonds

if __name__ == "__main__":
    scanner = HistoricalDiamondScanner()
    diamonds = scanner.scan_latest()
    print(f"\nDiscovery complete. Diamonds: {len(diamonds)}")
    with Path("diamond_discovery_report.json").open("w") as f:
        json.dump(diamonds, f, indent=4)
