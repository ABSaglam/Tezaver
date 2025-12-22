# Phase 2C Investigation Report

## History Bar Data Sources ✅

**Path Pattern:**
```
coin_cells/{SYMBOL}/data/history_{timeframe}.parquet
```

**Loader Function:**
- File: `src/tezaver/ui/chart_area.py`
- Function: `load_history_data(symbol: str, timeframe: str)`
- Returns: DataFrame with columns: `open_time`, `open`, `high`, `low`, `close`, `volume`

**Verified Paths (ETHUSDT):**
```
coin_cells/ETHUSDT/data/history_15m.parquet
coin_cells/ETHUSDT/data/history_1h.parquet
coin_cells/ETHUSDT/data/history_4h.parquet
coin_cells/ETHUSDT/data/history_1d.parquet
coin_cells/ETHUSDT/data/history_1w.parquet
```

## Entry Offset Interpretation

Based on chart_area.py usage:
- `entry_bar_offset`: Relative bar index from event_time
- Positive offset = forward direction (toward peak)
- Example: event_time = "2025-12-21 07:00", offset = 5 → bar at "2025-12-21 08:15" (for 15m)

## Phase 2C Scope Analysis

### Required Components:

1. **NormalizeEngine Module** (~150 lines)
   - `normalize_entry()` function
   - Closed-bar lock
   - Pivot detection (±3 bars)
   - Snap confidence calculation

2. **ONY UI Integration** (~80 lines)
   - "Normalize (Entry)" button
   - Result display panel
   - Apply/Reset functionality

3. **Annotation Extension**
   - Add normalized fields to SniperAnnotation
   - Backward compatibility handling

4. **Tests** (~200 lines)
   - Offset-to-timestamp basic
   - Pivot snap detection
   - Edge cases

5. **Proof Report**
   - 3 examples (15m/1h/4h)
   - Snap reason documentation

**Total Estimated Work:** 3-4 hours for careful implementation

## Recommendation

Phase 2C is substantial. Current session has completed:
- ✅ Phase 2A (Tier Canonicalization)
- ✅ Phase 2B (Timeframe Event Sources)

Suggest taking backup and tackling Phase 2C in focused next session.
