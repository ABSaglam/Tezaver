# Tezaver Bulut - ExchangeInfo Cache
"""
Service to fetch, parse, and cache Binance ExchangeInfo.
Provides filters like tickSize, stepSize, minQty.
"""

import json
import time
import aiohttp
import asyncio
from typing import Dict, Optional, Any
from pathlib import Path

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.paths import get_project_root  # We might need project root for relative paths if needed, but config usually has full/relative path

    def __init__(self, config: BulutConfig, telemetry_service=None):
        self._config = config
        self._telemetry = telemetry_service
        
        # Path resolution
        raw_path = Path(config.exchangeinfo_cache_path)
        if raw_path.is_absolute():
            self._cache_path = raw_path
        else:
            self._cache_path = get_project_root().parent / raw_path

        self._filters: Dict[str, Dict[str, float]] = {}
        self._last_refresh = 0.0
        
        # Ensure dir exists
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load initially
        self.load_from_disk()

    def get_filters(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get filters for symbol: tickSize, stepSize, minQty, maxQty."""
        return self._filters.get(symbol)

    def is_fresh(self) -> bool:
        """Check if cache is within TTL."""
        age = time.time() - self._last_refresh
        return age < self._config.exchangeinfo_ttl_seconds

    def load_from_disk(self):
        """Load cache from disk."""
        if not self._cache_path.exists():
            return
            
        try:
            with open(self._cache_path, "r") as f:
                data = json.load(f)
                self._filters = data.get("filters", {})
                self._last_refresh = data.get("ts", 0.0)
                # Ensure float conversion just in case JSON loaded strings? 
                # JSON loads numbers as numbers usually.
        except Exception as e:
            print(f"[EXCHANGE_INFO] Failed to load cache: {e}")

    def save_to_disk(self):
        """Save cache to disk."""
        try:
            data = {
                "ts": self._last_refresh,
                "filters": self._filters
            }
            with open(self._cache_path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"[EXCHANGE_INFO] Failed to save cache: {e}")

    async def refresh(self) -> bool:
        """Fetch fresh data from Binance."""
        base_url = "https://testnet.binancefuture.com" if "TESTNET" in self._config.mode.name else "https://fapi.binance.com"
        url = f"{base_url}/fapi/v1/exchangeInfo"
        
        print(f"[EXCHANGE_INFO] Refreshing from {url}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    data = await resp.json()
                    
            # Parse
            new_filters = {}
            symbols = data.get("symbols", [])
            for s in symbols:
                sym = s.get("symbol")
                if not sym: continue
                
                # Parse filters
                f_map = {}
                for f in s.get("filters", []):
                    if f["filterType"] == "PRICE_FILTER":
                        f_map["tickSize"] = float(f.get("tickSize", 0))
                    elif f["filterType"] == "LOT_SIZE":
                        f_map["stepSize"] = float(f.get("stepSize", 0))
                        f_map["minQty"] = float(f.get("minQty", 0))
                        f_map["maxQty"] = float(f.get("maxQty", 0))
                    elif f["filterType"] == "MARKET_LOT_SIZE":
                        # Some pairs use this for market orders
                        pass
                
                # We need at least tickSize and stepSize
                if "tickSize" in f_map and "stepSize" in f_map:
                    new_filters[sym] = f_map
            
            self._filters = new_filters
            self._last_refresh = time.time()
            self.save_to_disk()
            
            if self._telemetry:
                self._telemetry.emit_exchangeinfo_refresh(True, {
                    "count": len(new_filters),
                    "ts": self._last_refresh
                })
            
            print(f"[EXCHANGE_INFO] Refreshed {len(new_filters)} symbols.")
            return True
            
        except Exception as e:
            msg = f"Refresh failed: {e}"
            print(f"[EXCHANGE_INFO] {msg}")
            if self._telemetry:
                self._telemetry.emit_exchangeinfo_refresh(False, {"error": str(e)})
            return False

    def get_status(self) -> Dict:
        return {
            "age_seconds": time.time() - self._last_refresh,
            "symbols_count": len(self._filters),
            "cache_path": str(self._cache_path),
            "is_fresh": self.is_fresh()
        }
