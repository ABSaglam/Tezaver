from typing import List, Dict, Any

def validate_candles(candles: List[Dict], timeframe_ms: int) -> Dict[str, Any]:
    """
    MX-5210: Validates market data integrity.
    Tr: Market data bütünlüğünü kontrol eder.
    
    Detects:
    - OUT_OF_ORDER: Timestamps moving backward.
    - DUPLICATE_TS: Multiple candles with same timestamp.
    - GAP_DETECTED: Missing candles in the sequence.
    """
    if not candles:
        return {
            "ok": True,
            "reasons": [],
            "out_of_order_count": 0,
            "duplicate_count": 0,
            "gap_count": 0,
            "max_gap_bars": 0
        }

    reasons = []
    out_of_order_count = 0
    duplicate_count = 0
    gap_count = 0
    max_gap_ms = 0

    prev_ts = None
    for i, candle in enumerate(candles):
        ts = candle.get("timestamp", 0)
        
        # 1. Out of Order Check
        if prev_ts is not None and ts < prev_ts:
            out_of_order_count += 1
            
        # 2. Duplicate Check
        if i > 0 and ts == candles[i-1].get("timestamp"):
            duplicate_count += 1
            
        # 3. Gap Check (Based on expected timeframe)
        if prev_ts is not None and ts > prev_ts + timeframe_ms:
            gap_ms = ts - (prev_ts + timeframe_ms)
            if gap_ms > 0:
                gap_count += 1
                max_gap_ms = max(max_gap_ms, gap_ms)
        
        prev_ts = ts

    if out_of_order_count > 0: reasons.append("OUT_OF_ORDER")
    if duplicate_count > 0: reasons.append("DUPLICATE_TS")
    if gap_count > 0: reasons.append("GAP_DETECTED")

    max_gap_bars = max_gap_ms // timeframe_ms if timeframe_ms > 0 else 0

    return {
        "ok": len(reasons) == 0,
        "reasons": reasons,
        "out_of_order_count": out_of_order_count,
        "duplicate_count": duplicate_count,
        "gap_count": gap_count,
        "max_gap_bars": max_gap_bars,
        "first_ts": candles[0].get("timestamp"),
        "last_ts": candles[-1].get("timestamp"),
        "count": len(candles)
    }
