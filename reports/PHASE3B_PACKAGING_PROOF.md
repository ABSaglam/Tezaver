# Phase 3B: Dökümhane Packaging v1 — PROOF REPORT

**Date:** 2025-12-22  
**Status:** ✅ COMPLETE

---

## Goal

Package QC-PASSED approved annotations into Matrix-ready ApprovedRallyBundle v1 format with manifest, annotation snapshot, QC report, event data, and price window.

---

## Implementation Summary

### 1. Bundle Data Models ✅

**File:** `src/tezaver/foundry/bundle_models.py` (75 lines)

```python
@dataclass
class ApprovedRallyBundleManifest:
    bundle_version: str = "approved_rally_bundle_v1"
    bundle_id: str  # {symbol}_{tf}_{event_id}
    
    symbol: str
    timeframe: str
    event_id: str
    event_time_iso: str
    tier: str  # DIAMOND|GOLD|SILVER|BRONZE|UNKNOWN
    
    approved: Dict[str, Any]  # entry/exit offsets & timestamps
    qc: Dict[str, Any]  # verdict, score, report_path
    pointers: Dict[str, str]  # file paths (relative)
    trace: Optional[Dict[str, str]]
    build_ts_iso: str
```

---

### 2. Bundle I/O Layer ✅

**File:** `src/tezaver/foundry/bundle_io.py` (180 lines)

**Functions:**
- `create_bundle_directory()`: Creates directory structure
- `write_bundle_manifest()`: Writes manifest.json
- `write_annotation_snapshot()`: Writes annotation.json
- `write_qc_report_copy()`: Writes qc_report.json
- `write_event_row()`: Writes event_row.json
- `write_price_window()`: Writes price_window.parquet
- `get_relative_path()`: Calculates relative paths
- `write_bundle_files()`: Writes all files in one call

---

### 3. Packaging Engine ✅

**File:** `src/tezaver/foundry/packaging_v1.py` (270 lines)

**Core Functions:**

**`package_event(symbol, timeframe, event_id)`:**
1. Load annotation → verify APPROVED status
2. Load QC report → verify PASS verdict
3. Load event dataset row
4. Compute tier from `future_max_gain_pct`
5. Extract price window (100 bars before, 300 after)
6. Build manifest with all metadata
7. Write 5 bundle files

**`package_symbol_timeframe(symbol, timeframe, limit)`:**
- Package all QC-PASSED events for a symbol/timeframe
- Returns list of created bundle paths

**Tier Computation Integration:**
```python
from tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct

tier = compute_tier_from_gain_pct(future_max_gain_pct)
# Returns: DIAMOND (30%+), GOLD (20%+), SILVER (10%+), BRONZE (5%+), None (<5%)
```

---

## Bundle Structure

**Output Directory:**
```
.tezaver_matrix/approved_bundles_v1/{SYMBOL}/{TF}/{event_id}/
├── manifest.json           # Bundle metadata (851 bytes)
├── annotation.json         # Approved annotation snapshot (356 bytes)
├── qc_report.json         # QC report copy (187 bytes)
├── event_row.json         # Event dataset row (152 bytes)
└── price_window.parquet   # Price bars (8.9 KB, 150 bars)
```

---

## Example Bundle

**Path:**
```
.tezaver_matrix/approved_bundles_v1/BTCUSDT/15m/BTCUSDT_15m_1704067200/
```

**Bundle Contents:**
```
✅ manifest.json (851 bytes)
✅ annotation.json (356 bytes)
✅ qc_report.json (187 bytes)
✅ event_row.json (152 bytes)
✅ price_window.parquet (8896 bytes, 150 bars)
```

---

### manifest.json

```json
{
  "bundle_version": "approved_rally_bundle_v1",
  "bundle_id": "BTCUSDT_15m_BTCUSDT_15m_1704067200",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "event_id": "BTCUSDT_15m_1704067200",
  "event_time_iso": "2025-01-01T00:00:00",
  "tier": "GOLD",
  "approved": {
    "entry_bar_offset": 5,
    "entry_ts": "2025-01-01T01:15:00",
    "exit_bar_offset": 20,
    "exit_ts": "2025-01-01T05:00:00"
  },
  "qc": {
    "verdict": "PASS",
    "score": 80,
    "report_path": "../../../qc_reports/BTCUSDT/15m/qc_BTCUSDT_15m_1704067200.json"
  },
  "pointers": {
    "annotation_path": "data/sniper/BTCUSDT/15m/sniper_annotations_v1.json",
    "event_dataset_path": "library/fast15_rallies/BTCUSDT/fast15_rallies.parquet",
    "history_path": "coin_cells/BTCUSDT/data/history_15m.parquet"
  },
  "trace": null,
  "build_ts_iso": "2025-12-22T19:33:46.064970"
}
```

**Key Features:**
- **Tier:** GOLD (computed from future_max_gain_pct = 0.21 = 21%)
- **Approved values:** Entry at 5 bars (+1h15m), Exit at 20 bars (+5h)
- **QC metadata:** PASS verdict with 80/100 score
- **Pointers:** Relative paths to source data

---

### annotation.json (excerpt)

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "event_id": "BTCUSDT_15m_1704067200",
  "entry_bar_offset": 5,
  "status": "APPROVED",
  "approved_entry_bar_offset": 5,
  "approved_entry_ts": "2025-01-01T01:15:00",
  "approved_exit_bar_offset": 20,
  "approved_exit_ts": "2025-01-01T05:00:00",
  "snap_distance_entry": 2,
  "snap_confidence_entry": 0.75
}
```

---

### qc_report.json (excerpt)

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "event_id": "BTCUSDT_15m_1704067200",
  "qc_verdict": "PASS",
  "score": 80,
  "fails": [],
  "warns": ["APPROVED_EXIT_MISSING"]
}
```

---

### event_row.json

```json
{
  "event_id": "BTCUSDT_15m_1704067200",
  "event_time": "2025-01-01T00:00:00",
  "future_max_gain_pct": 0.21,
  "bars_to_peak": 20,
  "tier": "GOLD"
}
```

---

### price_window.parquet

**Specifications:**
- **Rows:** 150 bars
- **Columns:** open_time, open, high, low, close, volume
- **Window:** 100 bars before event + event bar + 49 bars after (configurable)
- **Size:** 8.9 KB (compressed parquet)

**Purpose:** Provides price context around the event for Matrix analysis without requiring full history file access.

---

## Test Results

```bash
$ pytest -q tests/foundry/test_packaging_v1.py

tests/foundry/test_packaging_v1.py .........                    [100%]

9 passed, 3 warnings in 0.85s
```

**Test Coverage:**
1. ✅ `test_manifest_creation`: Manifest serialization/deserialization
2. ✅ `test_bundle_directory_creation`: Directory structure
3. ✅ `test_bundle_files_writing`: All 5 files written
4. ✅ `test_tier_computation_gold`: 21% → GOLD
5. ✅ `test_tier_computation_diamond`: 35% → DIAMOND
6. ✅ `test_tier_computation_silver`: 12% → SILVER
7. ✅ `test_tier_computation_bronze`: 7% → BRONZE
8. ✅ `test_tier_computation_unknown`: 3% → None
9. ✅ `test_price_window_extraction_bounds`: Window slicing correct

---

## Changed Files

| File | Status | Lines | Purpose |
|------|--------|-------|---------|
| `src/tezaver/foundry/bundle_models.py` | NEW | 75 | ApprovedRallyBundleManifest model |
| `src/tezaver/foundry/bundle_io.py` | NEW | 180 | Bundle file I/O operations |
| `src/tezaver/foundry/packaging_v1.py` | NEW | 270 | Packaging engine logic |
| `tests/foundry/test_packaging_v1.py` | NEW | 165 | 9 comprehensive tests |

**Total:** 690 new lines across 4 files

**Phase 3 Total (3A + 3B):** 1441 lines across 10 files

---

## Git Summary

```
Phase 3A (QC):      751 lines (6 files)
Phase 3B (Package): 690 lines (4 files)
Total Phase 3:     1441 lines (10 files)
```

---

## Acceptance Criteria

- [x] ApprovedRallyBundleManifest data model
- [x] 5-file bundle structure (manifest, annotation, qc, event, price_window)
- [x] Tier computation from future_max_gain_pct
- [x] QC PASS validation (skip if FAIL)
- [x] APPROVED status validation
- [x] Price window extraction (configurable window)
- [x] Relative path pointers in manifest
- [x] package_event() function
- [x] package_symbol_timeframe() function
- [x] 9 comprehensive tests (all passing)
- [x] Example bundle generated

---

## Bundle Policy

**Packaging Requirements:**
1. Annotation status must be "APPROVED"
2. QC verdict must be "PASS"
3. QC report must exist
4. Event dataset row must exist

**Skipped Cases:**
- Non-APPROVED annotations
- QC FAIL verdicts
- Missing QC reports
- Missing event data

---

## Usage Example

```python
from tezaver.foundry import packaging_v1

# Package single event
bundle_dir = packaging_v1.package_event("BTCUSDT", "15m", "BTCUSDT_15m_1704067200")
print(f"Bundle created: {bundle_dir}")

# Package all QC-PASSED events for symbol/timeframe
bundles = packaging_v1.package_symbol_timeframe("BTCUSDT", "15m", limit=10)
print(f"Created {len(bundles)} bundles")

# Output:
# .tezaver_matrix/approved_bundles_v1/BTCUSDT/15m/BTCUSDT_15m_1704067200/
# ├── manifest.json
# ├── annotation.json
# ├── qc_report.json
# ├── event_row.json
# └── price_window.parquet
```

---

## Tier Computation

**Mapping (from rally_grade_cards.py):**
```python
future_max_gain_pct >= 0.30  →  DIAMOND
future_max_gain_pct >= 0.20  →  GOLD
future_max_gain_pct >= 0.10  →  SILVER
future_max_gain_pct >= 0.05  →  BRONZE
future_max_gain_pct < 0.05   →  UNKNOWN (None)
```

**Example:**
- 21% gain → GOLD tier
- 35% gain → DIAMOND tier
- 3% gain → UNKNOWN (not packaged with tier)

---

## Next Steps (Matrix Integration)

1. **Matrix Loader:** Read ApprovedRallyBundle manifests
2. **Story Generation:** Use approved entry/exit for story construction
3. **Pattern Signatures:** Extract patterns from price windows
4. **Training Dataset:** Bundle manifests as training labels

---

## Conclusion

✅ **Phase 3B Complete**  
✅ **ApprovedRallyBundle v1 packaging operational**  
✅ **5-file bundle structure**  
✅ **Tier computation integrated**  
✅ **QC validation enforced**  
✅ **Price window extraction functional**  
✅ **All tests passing (9/9)**

**Dökümhane complete!** QC Gate (Phase 3A) validates annotations, Packaging (Phase 3B) creates Matrix-ready bundles. Ready for Matrix consumption.
