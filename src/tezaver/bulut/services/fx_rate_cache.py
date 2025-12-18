# Tezaver Bulut - FX Rate Cache
"""
Service for fetching and caching FX rates (e.g., BNBUSDT).
"""
import time
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

class FxRateCache:
    def __init__(self, config: BulutConfig, client: BinanceFuturesSigned, persistence: SqlitePersistence, telemetry: NdjsonTelemetry):
        self._config = config
        self._client = client
        self._persistence = persistence
        self._telemetry = telemetry
        
    async def get_rate(self, asset: str) -> Optional[float]:
        """
        Get rate to convert 'asset' to 'quote_asset'.
        Returns cached rate if valid, else triggers refresh.
        If asset == quote_asset, returns 1.0.
        """
        quote = getattr(self._config, "fx_quote_asset", "USDT")
        
        if asset == quote:
            return 1.0
            
        cached = self._persistence.get_fx_rate(asset)
        if cached:
            # Check TTL
            updated_str = cached["updated_ts"]
            try:
                updated_ts = datetime.fromisoformat(updated_str).timestamp()
                age = time.time() - updated_ts
                ttl = getattr(self._config, "fx_ttl_seconds", 300)
                
                if age < ttl:
                    return cached["rate"]
            except Exception:
                pass
                
        # Needs refresh
        return await self.refresh_asset(asset)

    async def refresh_asset(self, asset: str) -> Optional[float]:
        """Fetch and cache new rate from Binance."""
        if not getattr(self._config, "fx_enabled", True):
            return None
            
        quote = getattr(self._config, "fx_quote_asset", "USDT")
        symbol = f"{asset}{quote}" # Simple concatenation (e.g. BNBUSDT)
        
        rate = None
        source = "NONE"
        
        try:
            # 1. Try Book Ticker (Mid Price)
            # Weight: 2
            if getattr(self._config, "fx_price_mode", "BOOK_MID") == "BOOK_MID":
                try:
                    book = await self._client.get_book_ticker(symbol)
                    if book and "bidPrice" in book and "askPrice" in book:
                        bid = float(book["bidPrice"])
                        ask = float(book["askPrice"])
                        if bid > 0 and ask > 0:
                            rate = (bid + ask) / 2.0
                            source = "BOOK_MID"
                except Exception as e:
                    pass # Fallback
            
            # 2. Fallback to Last Price
            # Weight: 1
            if rate is None and getattr(self._config, "fx_fallback_last_price", True):
                 try:
                     ticker = await self._client.get_last_price(symbol)
                     if ticker and "price" in ticker:
                         rate = float(ticker["price"])
                         source = "LAST_PRICE"
                 except Exception as e:
                     pass
                     
            if rate is not None:
                self._persistence.upsert_fx_rate(asset, quote, rate, source)
                self._telemetry.emit("FX_RATE_OK", {"asset": asset, "rate": rate, "source": source})
                return rate
            else:
                self._telemetry.emit("FX_RATE_FAIL", {"asset": asset, "error": f"Could not fetch rate for {symbol}"})
                return None
                
        except Exception as e:
            self._telemetry.emit("FX_RATE_FAIL", {"asset": asset, "error": str(e)})
            return None

    def convert_to_usdt(self, asset: str, amount: float, known_rate: float = None) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Convert to USDT.
        Returns (amount_usdt, rate_used, source_used).
        If fails or no rate, returns (None, None, None).
        
        This method is synchronous and relies on CACHED rate if known_rate is not provided.
        It does NOT trigger async refresh (use get_rate for that).
        """
        quote = getattr(self._config, "fx_quote_asset", "USDT")
        if asset == quote:
            return amount, 1.0, "PEG"
            
        rate = known_rate
        source = "PASSED"
        
        if rate is None:
            cached = self._persistence.get_fx_rate(asset)
            if cached:
                rate = cached["rate"]
                source = cached["source"] + "(CACHE)"
        
        if rate is not None:
            return amount * rate, rate, source
            
        return None, None, None
