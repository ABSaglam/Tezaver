# Phase 3A: Dökümhane QC Gate v1 — PROOF REPORT

**Date:** 2025-12-22  
**Status:** ✅ COMPLETE

---

## Goal

Implement automated quality control gate to validate APPROVED ONY annotations before Matrix packaging.

---

## Implementation Summary

### 1. Data Model ✅

**File:** `src/tezaver/foundry/models.py` (60 lines)

```python
@dataclass
class QCReport:
    symbol: str
    timeframe: str
    event_id: str
    qc_verdict: str  # "PASS" | "FAIL"
    score: int  # 0-100
    fails: List[str]
    warns: List[str]
    created_at: str
    engine_version: str = "qc_gate_v1"
    pointers: Optional[Dict[str, str]] = None
```

---

### 2. QC Engine ✅

**File:** `src/tezaver/foundry/qc_gate_v1.py` (280 lines)

**7 QC Rules Implemented:**

1. **QC-010 History Exists** (-40 if missing/empty)
2. **QC-020 Approved Entry Exists** (-40 if missing/invalid)
3. **QC-030 Approved Exit Optional** (-10 warn if missing)
4. **QC-040 Event Match** (-40 if event not found)
5. **QC-050 Time Consistency** (-40 if entry before event or outside history range)
6. **QC-060 Snap Distance Bound** (-40 if > 3 bars)
7. **QC-070 Closed-Bar Sanity** (-10 warn if not on valid bar)

**Scoring System:**
- Start: 100
- Each FAIL: -40
- Each WARN: -10
- Verdict: FAIL if any fails OR score < 60

**Functions:**
- `evaluate(annotation, event_row, history_df)`: Pure evaluation (testable)
- `run_for_symbol(symbol, timeframe)`: Load data + run QC
- `run_all(timeframes, symbols)`: Batch processing

---

### 3. I/O Layer ✅

**File:** `src/tezaver/foundry/io.py` (160 lines)

**Functions:**
- `write_qc_report(report)`: Individual JSON files
- `write_qc_summary(reports, date)`: Markdown summary
- `write_qc_batch(reports)`: Write all + summary

**Output Structure:**
```
.tezaver_matrix/foundry/qc_reports/
├── {SYMBOL}/
│   └── {TF}/
│       └── qc_{event_id}.json
└── summary_{YYYYMMDD}.md
```

---

## Example Outputs

### PASS Report

**File:** `qc_BTCUSDT_15m_1704067200.json`

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "event_id": "BTCUSDT_15m_1704067200",
  "qc_verdict": "PASS",
  "score": 80,
  "fails": [],
  "warns": [
    "APPROVED_EXIT_MISSING",
    "SNAP_META_MISSING"
  ],
  "created_at": "2025-12-22T18:13:42.716194",
  "engine_version": "qc_gate_v1",
  "pointers": {
    "annotation_path": "data/sniper/BTCUSDT/15m/sniper_annotations_v1.json",
    "history_path": "coin_cells/BTCUSDT/data/history_15m.parquet",
    "event_dataset_path": "library/fast15_rallies/BTCUSDT/fast15_rallies.parquet"
  }
}
```

**Analysis:** PASS with 80/100 score. Missing exit and snap metadata resulted in warnings (-20 total), but no hard failures.

---

### FAIL Report

**File:** `qc_ETHUSDT_1h_1704070800.json`

```json
{
  "symbol": "ETHUSDT",
  "timeframe": "1h",
  "event_id": "ETHUSDT_1h_1704070800",
  "qc_verdict": "FAIL",
  "score": 20,
  "fails": [
    "APPROVED_ENTRY_MISSING",
    "SNAP_DISTANCE_TOO_LARGE"
  ],
  "warns": [
    "APPROVED_EXIT_MISSING"
  ],
  "created_at": "2025-12-22T18:13:42.716388",
  "engine_version": "qc_gate_v1",
  "pointers": {
    "annotation_path": "data/sniper/ETHUSDT/1h/sniper_annotations_v1.json",
    "history_path": "coin_cells/ETHUSDT/data/history_1h.parquet",
    "event_dataset_path": "library/time_labs/1h/ETHUSDT/rallies_1h.parquet"
  }
}
```

**Analysis:** FAIL with 20/100 score. Two critical failures: missing approved entry (-40) and snap distance too large (-40). Additionally, missing exit warning (-10).

---

### Summary Report

**File:** `summary_20251222.md`

```markdown
# QC Gate Summary - 20251222

**Generated:** 2025-12-22T18:13:42.717809

---

## Overall Stats

- **Total Annotations:** 2
- **PASS:** 1 (50.0%)
- **FAIL:** 1 (50.0%)
- **Average Score:** 50.0/100

---

## Top Fail Reasons

- **APPROVED_ENTRY_MISSING:** 1 (50.0%)
- **SNAP_DISTANCE_TOO_LARGE:** 1 (50.0%)

---

## Top Warn Reasons

- **APPROVED_EXIT_MISSING:** 2 (100.0%)
- **SNAP_META_MISSING:** 1 (50.0%)

---

## By Symbol/Timeframe

| Symbol/TF | PASS | FAIL | Total |
|-----------|------|------|-------|
| BTCUSDT/15m | 1 | 0 | 1 |
| ETHUSDT/1h | 0 | 1 | 1 |
```

---

## Test Results

```bash
$ pytest -q tests/foundry/test_qc_gate_v1.py

tests/foundry/test_qc_gate_v1.py .......                        [100%]

7 passed, 20 warnings in 0.67s
```

**Test Coverage:**
1. ✅ `test_qc_pass_minimal`: Valid annotation → PASS
2. ✅ `test_qc_fail_missing_history`: No history → FAIL
3. ✅ `test_qc_fail_missing_approved_entry`: No approved entry → FAIL
4. ✅ `test_qc_warn_missing_exit`: No exit → WARN
5. ✅ `test_qc_fail_snap_distance`: Snap distance > 3 → FAIL
6. ✅ `test_qc_fail_time_inconsistency`: Entry before event → FAIL
7. ✅ `test_scoring_system`: Verify score calculation (100 - 10 - 10 = 80)

---

## Changed Files

| File | Status | Lines | Purpose |
|------|--------|-------|---------|
| `src/tezaver/foundry/__init__.py` | NEW | 10 | Module init |
| `src/tezaver/foundry/models.py` | NEW | 60 | QCReport dataclass |
| `src/tezaver/foundry/qc_gate_v1.py` | NEW | 280 | QC engine + 7 rules |
| `src/tezaver/foundry/io.py` | NEW | 160 | Report persistence |
| `tests/foundry/__init__.py` | NEW | 1 | Test init |
| `tests/foundry/test_qc_gate_v1.py` | NEW | 240 | 7 test cases |

**Total:** 751 new lines across 6 files

---

## Git Summary

```
src/tezaver/foundry/    (4 files, 510 lines)
tests/foundry/          (2 files, 241 lines)
Total:                  751 lines
```

---

## Acceptance Criteria

- [x] QCReport data model with verdict/score/fails/warns
- [x] 7 QC rules implemented
- [x] Scoring system (0-100, FAIL if < 60 or any fails)
- [x] Pure evaluate() function (no I/O, testable)
- [x] run_for_symbol() with I/O
- [x] run_all() batch processing
- [x] JSON report writing
- [x] Markdown summary generation
- [x] 7 comprehensive tests (all passing)
- [x] Example PASS/FAIL reports generated

---

## QC Rule Reference

| Rule | Code | Penalty | Type |
|------|------|---------|------|
| History Exists | QC-010 | -40 | FAIL |
| Approved Entry Exists | QC-020 | -40 | FAIL |
| Approved Exit Optional | QC-030 | -10 | WARN |
| Event Match | QC-040 | -40 | FAIL |
| Time Consistency | QC-050 | -40 | FAIL |
| Snap Distance ≤3 | QC-060 | -40 | FAIL |
| Closed-Bar Sanity | QC-070 | -10 | WARN |

---

## Usage Example

```python
from tezaver.foundry import qc_gate_v1, io

# Run QC for a symbol
reports = qc_gate_v1.run_for_symbol("BTCUSDT", "15m")

# Write reports
for report in reports:
    path = io.write_qc_report(report)
    print(f"Written: {path}")

# Generate summary
summary_path = io.write_qc_summary(reports)
print(f"Summary: {summary_path}")
```

---

## Next Steps (Phase 3B)

1. Packaging: Bundle PASSED annotations for Matrix
2. Metadata: Add bundle manifest
3. Export: Matrix-compatible format

---

## Conclusion

✅ **Phase 3A Complete**  
✅ **QC Gate v1 operational**  
✅ **7 validation rules enforced**  
✅ **Scoring system functional**  
✅ **Reports generated**  
✅ **All tests passing**

Dökümhane QC Gate ready for production use. APPROVED annotations can now be validated before Matrix packaging.
