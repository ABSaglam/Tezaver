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
        Run one polling cycle for all symbols.
        Returns count of successfully ingested bars.
        """
        start_ts = time.time()
        
        # Create tasks with semaphore
        tasks = [self._fetch_and_ingest(sym) for sym in universe]
        results = await asyncio.gather(*tasks)
        
        ingested_count = sum(1 for r in results if r)
        duration = time.time() - start_ts
        
        # Determine flags
        flags = []
        if ingested_count < len(universe):
            flags.append("PARTIAL_INGEST")
            
        # Telemetry
        self._telemetry.emit("BARS_INGEST_CYCLE", {
            "universe_size": len(universe),
            "ingested_count": ingested_count,
            "duration_s": round(duration, 3),
            "concurrency": self._config.poll_concurrency,
            "flags": flags
        })
        
        print(f"[POLLER] Ingested {ingested_count}/{len(universe)} bars in {duration:.2f}s ({', '.join(flags) if flags else 'OK'})")
        return ingested_count

    async def _fetch_and_ingest(self, symbol: str) -> bool:
        """Fetch and ingest single symbol."""
        async with self._sem:
            try:
                bar = await self._client.get_latest_closed_bar(symbol, interval=self._config.base_tf)
                if bar:
                    self._store.ingest_bar(bar)
                    return True
                return False
            except Exception as e:
                # Log error sparingly or to debug
                return False
