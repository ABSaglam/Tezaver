import requests
import json

def probes_binance():
    url = "https://api.binance.com/api/v3/exchangeInfo"
    resp = requests.get(url)
    data = resp.json()
    symbols = data.get('symbols', [])
    
    # Check BTCUSDT specificially to see format
    for s in symbols:
        if s['symbol'] == 'BTCUSDT':
            print("--- BTCUSDT SAMPLE ---")
            print(json.dumps(s, indent=2))
            break
            
if __name__ == "__main__":
    probes_binance()
