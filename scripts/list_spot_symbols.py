import ccxt

def list_spot_usdt_pairs():
    exchange = ccxt.binance()
    markets = exchange.load_markets()
    spot_usdt_pairs = [symbol for symbol, market in markets.items() 
                      if market['active'] and market['type'] == 'spot' and symbol.endswith('/USDT')]
    
    print(f"Total Spot USDT pairs found: {len(spot_usdt_pairs)}")
    for pair in sorted(spot_usdt_pairs):
        print(pair.replace('/', ''))

if __name__ == "__main__":
    list_spot_usdt_pairs()
