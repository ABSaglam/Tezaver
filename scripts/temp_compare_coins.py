
import os

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
KEYS_DIR = "/Users/alisaglam/TezaverMac/data/golden_keys_v2"

# 1. Get All Coins
all_coins = set([d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))])

# 2. Get Golden Keys
golden_coins = set()
if os.path.exists(KEYS_DIR):
    for f in os.listdir(KEYS_DIR):
        if f.endswith("_key.json"):
            symbol = f.replace("_key.json", "")
            golden_coins.add(symbol)

# 3. Find Difference
losers = sorted(list(all_coins - golden_coins))

print(f"TOPLAM KOIN: {len(all_coins)}")
print(f"GOLDEN KEY SAHIBI: {len(golden_coins)}")
print(f"LISTE DISI KALANLAR (DNA UYUMSUZ): {len(losers)}")
print("-" * 30)
print(", ".join(losers))
