import json
import os
from typing import List
from tezaver.matrix.ports.data_port import DataPort
from tezaver.matrix.core.bars import Bar

class JsonFileDataPort(DataPort):
    def __init__(self, path: str):
        self.path = path
        
    def get_closed_bars(self, symbol: str, timeframe: str) -> List[Bar]:
        if not os.path.exists(self.path):
            # For robustness, return empty or raise? Protocol says List[Bar].
            # Let's return empty if file missing but maybe log warning (if logging existed)
            return []
            
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
            
        bars = []
        for b in raw:
            # Protocol: internal ms
            # Source: likely sec if from bars.json (Phase-2 compat)
            # Logic: check if ts small (< 30000000000 ?), treat as sec -> ms
            
            ts = b['ts']
            if ts < 100000000000: # heuristic: epoch seconds usually 1.7e9, ms 1.7e12
                ts = int(ts * 1000)
                
            # Filter logic?
            # Ideally data source should provide correct time range.
            # Here we just load ALL from file.
            
            # Use Bar constructor from Phase-0
            bar = Bar(
                ts=ts,
                open=b['open'],
                high=b['high'],
                low=b['low'],
                close=b['close'],
                is_closed=b.get('is_closed', True) # Assume closed if not specified in historic source
            )
            
            if bar.is_closed:
                bars.append(bar)
                
        # Sort by TS
        bars.sort(key=lambda x: x.ts)
        return bars
