import sys
import os
import json
import requests

# This script fetches the live authoritative list of Binance Spot USDT pairs
# and saves it to 'data/spot_whitelist_437.json'.

def fetch_whitelist():
    print("🌍 FETCHING AUTHORITATIVE BINANCE GLOBAL SPOT LIST...")
    
    try:
        url = "https://api.binance.com/api/v3/exchangeInfo"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        symbols = data.get('symbols', [])
        spot_usdt = []
        
        print(f"   -> Raw Symbols Found: {len(symbols)}")
        
        for s in symbols:
            # Criteria for 'The Noble 437':
            # 1. Status: TRADING
            # 2. Quote Asset: USDT
            # 3. isSpotTradingAllowed MUST be True
            
            if s['status'] != 'TRADING': continue
            if s['quoteAsset'] != 'USDT': continue
            
            # API Update: Check 'isSpotTradingAllowed' boolean directly
            if not s.get('isSpotTradingAllowed', False):
                 continue
            
            base = s['baseAsset']
            # Filter leveraged tokens heuristic
            if 'UP' in base or 'DOWN' in base or 'BULL' in base or 'BEAR' in base:
                 if base.endswith('UP') or base.endswith('DOWN') or base.endswith('BULL') or base.endswith('BEAR'):
                     continue
            
            spot_usdt.append(s['symbol'])
            
        spot_usdt.sort()
        print(f"✅ IDENTIFIED SPOT COINS: {len(spot_usdt)}")
        
        # Save
        out_path = "data/spot_whitelist_437.json"
        with open(out_path, "w") as f:
            json.dump(spot_usdt, f, indent=2)
            
        print(f"💾 Saved to: {out_path}")
        return spot_usdt

    except Exception as e:
        print(f"❌ FETCH FAILED: {e}")
        return []

if __name__ == "__main__":
    fetch_whitelist()
