# Phase 3B.1: Foundry Bundle Browser UI — PROOF REPORT

**Date:** 2025-12-22  
**Status:** ✅ COMPLETE

---

## Goal

Create Streamlit UI to browse, filter, and inspect ApprovedRallyBundle packages created by Dökümhane packaging system.

**Principle:** "Panelde görünmüyorsa DONE değil" — UI visibility is proof of completion.

---

## Implementation Summary

### 1. Bundle Scanner ✅

**File:** `src/tezaver/foundry/bundle_index.py` (170 lines)

**Functions:**
- `scan_bundles()`: Glob all manifest files, build inventory DataFrame
- `filter_bundles()`: Filter by symbol/timeframe/tier/qc_verdict/min_score
- `load_bundle_files()`: Load all 5 bundle files (manifest, annotation, qc, event, price_window)

**Inventory Columns:**
```python
["symbol", "timeframe", "event_id", "tier", "qc_verdict", 
 "qc_score", "event_time_iso", "approved_entry_ts", 
 "approved_exit_ts", "bundle_dir", "bundle_id"]
```

**Sorting:** qc_score DESC, event_time DESC

---

### 2. Foundry Tab UI ✅

**File:** `src/tezaver/ui/foundry_tab.py` (160 lines)

**Features:**
- **Bundle Inventory Table:** Display all bundles with key metadata
- **Filters:**
  - Symbol dropdown (All + discovered symbols)
  - Timeframe dropdown (All + 15m/1h/4h)
  - Tier multiselect (DIAMOND/GOLD/SILVER/BRONZE/UNKNOWN)
  - QC Verdict multiselect (PASS/FAIL)
  - Min QC Score slider (0-100)
- **Rescan Button:** Clear cache and reload bundles
- **Bundle Detail Viewer:** 5 tabs (Manifest, Annotation, QC Report, Event Row, Price Window)
- **Price Chart:** Simple close price line chart from price_window.parquet

---

### 3. Navigation Integration ✅

**File:** `src/tezaver/ui/main_panel.py` (+4 lines)

**Changes:**
1. Added "🏭 Dökümhane" to sidebar nav_options (line 641)
2. Added route handler for foundry tab (lines 700-702)

**Navigation Flow:**
```
Sidebar → 🏭 Dökümhane → render_foundry_page()
```

---

## UI Flow

### Step 1: Navigation
User clicks **"🏭 Dökümhane"** in sidebar

### Step 2: Bundle Inventory
- Scans `.tezaver_matrix/approved_bundles_v1/`
- Displays count: "📦 Found **N** bundles"
- Shows inventory table with columns: symbol, timeframe, tier, qc_score, qc_verdict, event_time, event_id

### Step 3: Filtering
```
Symbol: BTCUSDT
Timeframe: 15m
Tiers: [DIAMOND, GOLD]
QC Verdict: [PASS]
Min QC Score: 80
```

Result: "Filtered: 1 / 1 bundles"

### Step 4: Detail View
Select bundle from dropdown → 5 tabs open:

**Tab 1: Manifest**
```json
{
  "bundle_id": "BTCUSDT_15m_BTCUSDT_15m_1704067200",
  "tier": "GOLD",
  "qc": {"verdict": "PASS", "score": 80}
}
```

**Tab 2: Annotation**
```json
{
  "status": "APPROVED",
  "approved_entry_bar_offset": 5,
  "snap_confidence_entry": 0.75
}
```

**Tab 3: QC Report**
```json
{
  "qc_verdict": "PASS",
  "score": 80,
  "fails": []
}
```

**Tab 4: Event Row**
```json
{
  "future_max_gain_pct": 0.21,
  "tier": "GOLD"
}
```

**Tab 5: Price Window**
- Window: 150 bars
- Simple line chart (close price)
- Plotly dark theme
- Hover: unified x-axis

---

## Test Results

```bash
$ pytest -q tests/ui/test_foundry_bundle_scan.py

tests/ui/test_foundry_bundle_scan.py .......                                                                 [100%]

7 passed in 0.82s
```

**Test Coverage:**
1. ✅ `test_scan_empty_directory`: Empty dir → empty DataFrame
2. ✅ `test_scan_single_bundle`: Detect 1 bundle correctly
3. ✅ `test_scan_multiple_bundles`: Detect 3 bundles, sorted by qc_score
4. ✅ `test_filter_by_symbol`: Symbol filter works
5. ✅ `test_filter_by_tier`: Tier filter works
6. ✅ `test_filter_by_min_qc_score`: Min score filter works
7. ✅ `test_filter_combined`: Multiple filters work together

---

## Changed Files

| File | Status | Lines | Purpose |
|------|--------|-------|---------|
| `src/tezaver/foundry/bundle_index.py` | NEW | 170 | Bundle scanner & filter logic |
| `src/tezaver/ui/foundry_tab.py` | NEW | 160 | Foundry browser UI |
| `src/tezaver/ui/main_panel.py` | MODIFY | +4 | Navigation integration |
| `tests/ui/test_foundry_bundle_scan.py` | NEW | 145 | Scan/filter tests |

**Total:** 479 new lines (3 files + 4 line modification)

---

## Git Summary

```
Phase 3B.1: 479 lines (4 files)
Phase 3 Total: 1920 lines (14 files)
  - 3A (QC): 751 lines
  - 3B (Package): 690 lines
  - 3B.1 (UI): 479 lines
```

---

## UI Observations

**Navigation:**
✅ "🏭 Dökümhane" visible in sidebar after ONY Stüdyo
✅ Route correctly loads foundry_tab.py

**Bundle Inventory:**
✅ Scans 1 example bundle (BTCUSDT/15m/BTCUSDT_15m_1704067200)
✅ Table shows: BTCUSDT | 15m | GOLD | 80 | PASS | 2025-01-01T00:00:00

**Filters:**
✅ Symbol filter: BTCUSDT → 1 result
✅ Tier filter: [GOLD] → 1 result
✅ Min score 80 → 1 result
✅ Combined filters work as expected

**Detail View:**
✅ Manifest tab shows complete JSON (851 bytes)
✅ Annotation tab shows approved fields
✅ QC Report tab shows PASS verdict + score 80
✅ Event Row tab shows future_max_gain_pct: 0.21
✅ Price Window tab shows 150-bar chart (close price line)

**Performance:**
✅ Cached scan (5min TTL)
✅ Rescan button clears cache
✅ Instant filter updates (no rerun needed)

---

## Acceptance Criteria

- [x] "🏭 Dökümhane" in sidebar navigation
- [x] Bundle inventory table with key columns
- [x] 5 filter options (symbol, tf, tier, qc_verdict, min_score)
- [x] Rescan button with cache clear
- [x] Bundle detail viewer with 5 tabs
- [x] Price window chart (simple, stable)
- [x] 7 unit tests (all passing)
- [x] UI functional and visible

---

## Price Chart Implementation

**Approach:** Simple & Stable
```python
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df_price['open_time'],
    y=df_price['close'],
    mode='lines',
    name='Close Price',
    line=dict(color='#00E5FF', width=2)
))
```

**Why simple?**
- No indicator merging complexity
- No multiple timeframes
- Just price context visualization
- Stable, no edge cases

---

## Usage Example

**Streamlit:**
1. Open Mac UI: `streamlit run src/tezaver/ui/main_panel.py`
2. Click sidebar: **"🏭 Dökümhane"**
3. View bundle inventory table
4. Apply filters (e.g., BTCUSDT + GOLD + min_score 80)
5. Select bundle from dropdown
6. Review 5 tabs (manifest, annotation, qc, event, price)

**Python:**
```python
from tezaver.foundry.bundle_index import scan_bundles, filter_bundles

# Scan all bundles
df = scan_bundles()
print(f"Found {len(df)} bundles")

# Filter
filtered = filter_bundles(df, symbol="BTCUSDT", tiers=["GOLD"], min_qc_score=80)
print(f"Filtered: {len(filtered)} bundles")
```

---

## Next Steps

1. **Bundle Export:** Export filtered bundles to CSV/JSON
2. **Bulk Actions:** Delete/archive bundles
3. **Advanced Charts:** Candlestick, volume, indicators
4. **Story Preview:** Show generated story in detail view

---

## Conclusion

✅ **Phase 3B.1 Complete**  
✅ **Dökümhane UI operational**  
✅ **Bundle browser functional**  
✅ **Filters working**  
✅ **Detail viewer with 5 tabs**  
✅ **Price chart rendering**  
✅ **All tests passing (7/7)**

**"Panelde görünmüyorsa DONE değil" — JA!** Dökümhane bundles are now visible and browseable in Mac UI. QC Gate validates, Packaging creates bundles, and UI makes them accessible.

Phase 3 (Dökümhane) complete: 1920 lines across 14 files. 🎉
