
import pandas as pd
import numpy as np

def demonstrate_bias():
    print("🔬 DEMONSTRATING RALLY MINER LOGIC ERROR (Intensity Bias)")
    
    # Create fake data: A steady 30% rise over 48 bars, with a 5% spike in the middle.
    n = 100
    prices = [100.0]
    for i in range(n-1):
        prices.append(prices[-1] * 1.005) # Steady rise
    
    # Add a sharp 5% spike at bar 40-42
    prices[40] = 120.0
    prices[41] = 126.0
    prices[42] = 126.1
    
    data = {
        'high': [p * 1.001 for p in prices],
        'low': [p * 0.999 for p in prices],
        'close': prices,
        'datetime': pd.date_range("2025-01-01", periods=n, freq="15min")
    }
    df = pd.DataFrame(data)
    
    # Mocking the mine_rallies logic
    def mock_mine(df):
        candidates = []
        n = len(df)
        prices_high = df['high'].values
        prices_low = df['low'].values
        
        for i in range(0, n - 10, 1): # Precision 1 for demo
            window_end = min(i + 96, n)
            win_highs = prices_high[i:window_end]
            max_h_idx = np.argmax(win_highs)
            max_h = win_highs[max_h_idx]
            max_h_global = i + max_h_idx
            
            win_lows_before = prices_low[i:max_h_global + 1]
            if len(win_lows_before) < 2: continue
            min_l_idx = np.argmin(win_lows_before)
            min_l = win_lows_before[min_l_idx]
            min_l_global = i + min_l_idx
            
            duration = max_h_global - min_l_global + 1
            gain = (max_h / min_l) - 1
            if gain >= 0.05:
                candidates.append({
                    'start_idx': min_l_global,
                    'end_idx': max_h_global,
                    'gain': gain * 100,
                    'bars': duration,
                    'intensity': (gain * 100) / duration
                })
        
        # ERROR POINT 1: Intensity Priority
        candidates.sort(key=lambda x: x['intensity'], reverse=True)
        
        final = []
        used = set()
        for c in candidates:
            r = set(range(c['start_idx'], c['end_idx'] + 1))
            if not (r & used):
                final.append(c)
                used.update(r)
        return final

    results = mock_mine(df)
    
    print(f"\nRally Miner'ın bulduğu sonuçlar:")
    for r in results:
        print(f"  Ralli: %+6.1f%% Kazanç | %3d Bar Süre | Intensity: %5.2f" % (r['gain'], r['bars'], r['intensity']))

    print("\n⚠️ HATA TESPİTİ:")
    print("Gerçekte burada %60+ kazandıran dev bir ralli var (tüm pencere).")
    print("Ancak Miner, içindeki hızlı 'spike'ı seçtiği için dev ralliyi 'overlap' diyerek çöpe attı.")
    print("Bu da sistemin yüksek kârlı ana trendleri 'gürültü' sanıp görmezden gelmesine sebep oluyor.")

if __name__ == "__main__":
    demonstrate_bias()
