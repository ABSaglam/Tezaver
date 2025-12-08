import sys
import os
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))
from tezaver.engine.analyzers.rally_analyzer import RallyAnalyzer

def debug_analyzer():
    # 1. Create Price Explosion Data
    # Flat then Explode
    prices = [100.0] * 50 + [100.0 * (1.10**i) for i in range(10)] 
    dates = pd.date_range(start="2024-01-01", periods=len(prices), freq="1h")
    
    df = pd.DataFrame({
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": [1000] * len(prices)
    }, index=dates)
    
    analyzer = RallyAnalyzer(rally_threshold=0.01, lookback_window=10)
    
    print("--- Debugging RallyAnalyzer ---")
    
    # Simulate sliding window
    for i in range(48, 55):
        window = df.iloc[:i]
        last_bar = window.iloc[-1]
        
        # Manual Calculation Print
        win_view = window.iloc[-10:]
        min_p = win_view['low'].min()
        gain = (last_bar['close'] - min_p) / min_p
        
        print(f"Bar {i} ({last_bar.name}): Close={last_bar['close']:.2f} Min={min_p:.2f} Gain={gain:.4f}")
        
        # Call Analyzer
        signals = analyzer.analyze("BTC", "1h", window)
        if signals:
            print(f"   >>> SIGNAL: {signals[0]['signal_type']} Score: {signals[0]['score']}")
            
if __name__ == "__main__":
    debug_analyzer()
