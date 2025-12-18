# Tezaver Bulut - Market Data Poller Engine
"""
Orchestrates fetching of market data (bars).
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import List

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.binance_futures_rest import BinanceFuturesRest
from tezaver.bulut.services.bars_15m_store import Bars15mStore
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry


class MarketDataPoller:
    """
    Polls market data for the entire universe.
    """
    
    def __init__(
        self,
        config: BulutConfig,
        rest_client: BinanceFuturesRest,
        bars_store: Bars15mStore,
        telemetry: NdjsonTelemetry,
    ):
        self._config = config
        self._client = rest_client
        self._store = bars_store
        self._telemetry = telemetry
        self._sem = asyncio.Semaphore(config.poll_concurrency)
        
    async def run_cycle(self, universe: List[str]) -> int:
        """
        Run one polling cycle. Returns count of Updated Symbols.
        """
        start_ts = time.time()
        
        # Create tasks
        tasks = [self._fetch_and_ingest(sym) for sym in universe]
        results = await asyncio.gather(*tasks) # List[int] bars ingested per symbol
        
        updated_symbols = sum(1 for r in results if r > 0)
        total_bars = sum(results)
        
        duration = time.time() - start_ts
        
        # Flags
        flags = []
        if updated_symbols < len(universe):
            flags.append("PARTIAL_INGEST")
        
        # Catch-up detected?
        if total_bars > updated_symbols:
            flags.append("CATCH_UP")
            
        # Telemetry
        self._telemetry.emit("BARS_INGEST_CYCLE", {
            "universe_size": len(universe),
            "updated_symbols": updated_symbols,
            "total_bars_ingested": total_bars,
            "duration_s": round(duration, 3),
            "concurrency": self._config.poll_concurrency,
            "flags": flags
        })
        
        print(f"[POLLER] Updated {updated_symbols}/{len(universe)} symbols ({total_bars} bars) in {duration:.2f}s ({', '.join(flags) if flags else 'OK'})")
        return updated_symbols

    async def _fetch_and_ingest(self, symbol: str) -> int:
        """
        Fetch and ingest bars. Returns number of NEW bars ingested.
        """
        async with self._sem:
            try:
                # 1. Check last stored bar
                last_stored = self._store.get_last_closed(symbol)
                
                # Default limit 2 (Current open + Last closed)
                limit = 2
                is_catchup = False
                
                # Metric: Estimated gap
                if last_stored:
                    # e.g. 15m = 900s
                    # gap = now - last_close_ts
                    # If gap > 2 * 900, we might need more
                    # For v0.11.1, simple catch-up: try 3 bars if we suspect data loss
                    # This covers "missed one cycle" scenario
                    now_ms = int(time.time() * 1000)
                    gap_ms = now_ms - last_stored.close_ts
                    interval_ms = 15 * 60 * 1000 # hardcoded 15m for now as base
                    
                    if gap_ms > (interval_ms * 2.1):
                        limit = 5 # Fetch a bit more to be safe (Catch-up)
                        is_catchup = True
                
                # 2. Fetch
                raw_data = await self._client.fetch_klines(
                    symbol, 
                    interval=self._config.base_tf, 
                    limit=limit
                )
                
                if not raw_data:
                    return 0
                    
                # 3. Parse and Ingest Closed Bars
                # Binance: [open_time, open, high, low, close, vol, close_time, ...]
                ingested = 0
                current_time_ms = int(time.time() * 1000)
                
                from tezaver.bulut.core.models import BarV1
                
                for k in raw_data:
                    c_time = k[6]
                    
                    # Store only if closed
                    if current_time_ms > c_time:
                        # Check against last_stored to avoid dup (Store handles dedupe usually, but optimization)
                        if last_stored and c_time <= last_stored.close_ts:
                             continue
                             
                        bar = BarV1(
                            symbol=symbol,
                            interval=self._config.base_tf,
                            open_ts=k[0],
                            close_ts=c_time,
                            o=float(k[1]),
                            h=float(k[2]),
                            l=float(k[3]),
                            c=float(k[4]),
                            v=float(k[5]),
                            is_closed=True
                        )
                        self._store.ingest_bar(bar)
                        ingested += 1
                        
                return ingested
            except Exception as e:
                # Log error sparingly
                return 0
