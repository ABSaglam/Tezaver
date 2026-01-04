
import sys
import pandas as pd
from pathlib import Path
from tezaver.core import coin_cell_paths
from tezaver.supernova.supernova_detector import SuperNovaDetector

# Add src to path
sys.path.insert(0, 'src')

def run_test():
    coins = ['RENDERUSDT', 'ARBUSDT', 'SEIUSDT', 'AXSUSDT', 'MANAUSDT']
    detector = SuperNovaDetector()
    
    print("=" * 80)
    print("🚀 SUPERNOVA DEDEKTÖR TESTİ (Son 1 bar)")
    print("=" * 80)
    
    for coin in coins:
        try:
            # Load 15m data
            path = coin_cell_paths.get_history_file(coin, '15m')
            df = pd.read_parquet(path)
            
            print(f"\nScanning {coin} (Last 100 bars)...")
            
            # Use the new API with lookback
            signals = detector.detect(coin, df, lookback=100)
            
            if signals:
                for sig in signals:
                    print(f"  🔥 {sig.mode} SIGNAL @ {sig.timestamp}")
                    print(f"     Price: {sig.price:.4f} | Vol Ratio: {sig.volume_ratio:.1f}x | RSI: {sig.rsi:.1f}")
            else:
                print("  No recent signals.")
                
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    run_test()
