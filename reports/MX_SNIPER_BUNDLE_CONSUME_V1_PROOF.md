# MX-4B: Sniper Bundle Consume v1 Proof Report

**Date:** 2025-12-23  
**Phase:** 4B - Sniper Bundle Consume  
**Status:** ✅ COMPLETE

---

## Summary

Implemented adapter for running Sniper from Matrix-loaded ApprovedRallyBundle v1 packages:
- Bundle → SniperRunConfig mapping with validation
- Telemetry with bundle_id included in SNIPER_RUN_STARTED/FINISHED events
- UI integration with "Run from Bundle" section on SNIPER page

---

## Changed Files

### New Files

| File | Description |
|------|-------------|
| `src/tezaver/matrix/sniper/__init__.py` | Module init |
| `src/tezaver/matrix/sniper/sniper_bundle_adapter_v1.py` | Core adapter for bundle → config mapping |
| `tests/matrix/sniper/__init__.py` | Test module init |
| `tests/matrix/sniper/test_sniper_bundle_adapter_v1.py` | 12 unit tests |

### Modified Files

| File | Changes |
|------|---------|
| `src/tezaver/ui/matrix_v4_tab.py` | +70 lines: Added "Run from Bundle" section to render_sniper() |

---

## Key Components

### 1. SniperBundleRunConfig (dataclass)

Config fields extracted from bundle:
- `symbol`, `timeframe`, `bundle_id`
- `entry_ts` (approved_entry_ts from manifest)
- `exit_ts` (optional - allows "exit by policy" mode)
- `qc_score`, `tier`
- `bundle_dir`, `manifest_path`, `price_window_path`
- `exit_missing` flag for telemetry

### 2. Validation Rules

```python
# Must be LOADED_OK status
if bundle.status != "LOADED_OK":
    raise ValueError("BUNDLE_NOT_LOADED_OK")

# Must have PASS QC verdict
if manifest.qc_verdict != "PASS":
    raise ValueError("BUNDLE_NOT_PASS")

# Must have approved_entry_ts
if not manifest.approved_entry_ts:
    raise ValueError("APPROVED_ENTRY_MISSING")

# exit_ts is optional (sets exit_missing=True flag)
```

### 3. Telemetry Events

**SNIPER_RUN_STARTED:**
```json
{
  "event_type": "SNIPER_RUN_STARTED",
  "ts": "2025-12-23T02:42:00+00:00",
  "run_id": "sniper_bundle_abc123",
  "bundle_id": "BTCUSDT_15m_rally_...",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "entry_ts": "2025-01-01T01:00:00",
  "exit_ts": null,
  "qc_score": 85,
  "tier": "GOLD",
  "exit_missing": true
}
```

**SNIPER_RUN_FINISHED:**
```json
{
  "event_type": "SNIPER_RUN_FINISHED",
  "ts": "2025-12-23T02:43:00+00:00",
  "run_id": "sniper_bundle_abc123",
  "bundle_id": "BTCUSDT_15m_rally_...",
  "result": {"cycles": 10, "pnl": 150.0}
}
```

---

## UI: Run from Bundle

Added to SNIPER page (`render_sniper()`):

```
📦 Run from Bundle (Expander)
├── Caption: LOADED_OK durumundaki ApprovedRallyBundle'lardan Sniper run başlat
├── Dropdown: Bundle Seç (lists LOADED_OK bundles)
├── Button: ▶ Run Sniper
└── Result:
    ├── Success: ✅ Sniper run başlatıldı: run_id
    ├── Config JSON display (symbol, timeframe, qc_score, etc.)
    └── Telemetry expander
```

---

## Test Results

### Adapter Tests (12/12 PASS)

```
$ pytest -q tests/matrix/sniper/test_sniper_bundle_adapter_v1.py

tests/matrix/sniper/test_sniper_bundle_adapter_v1.py ............ [100%]
12 passed in 0.02s
```

**Test Coverage:**
- `test_build_config_pass` - Valid PASS bundle builds config correctly
- `test_reject_qc_fail` - QC_FAIL bundle raises ValueError
- `test_reject_not_loaded_ok` - REJECTED bundle raises ValueError
- `test_reject_discovered_status` - DISCOVERED status raises ValueError
- `test_missing_entry_reject` - Missing approved_entry_ts raises ValueError
- `test_exit_missing_allowed` - Missing exit_ts allowed with flag set
- `test_config_to_dict` - Config serializes to dict correctly
- `test_sniper_run_started_contains_bundle_id` - Telemetry includes bundle_id
- `test_sniper_run_finished_contains_bundle_id` - Finish event includes bundle_id
- `test_start_valid_bundle` - High-level start function works
- `test_start_invalid_bundle_returns_error` - Invalid bundle returns error status
- `test_auto_generates_run_id` - Run ID auto-generated if not provided

### Core Gate Tests (7/7 PASS)

```
$ pytest -q tests/matrix -m core --ignore=tests/matrix/test_matrix_v4_bridge.py

7 passed, 227 deselected in 0.88s
```

---

## Git Status

```
## matrix_rebuild_v4
 M src/tezaver/ui/matrix_v4_tab.py       (+70 lines)
?? src/tezaver/matrix/sniper/            (new directory)
?? tests/matrix/sniper/                  (new directory)
```

---

## UI Run from Bundle - Flow

1. Navigate to Matrix → SNIPER
2. Expand "📦 Run from Bundle" section
3. Select bundle from dropdown (shows LOADED_OK bundles as "SYMBOL/TF - bundle_id...")
4. Click "▶ Run Sniper"
5. See:
   - Success message with run_id
   - Config JSON (bundle_id, symbol, timeframe, qc_score, exit_missing)
   - Telemetry in expandable section

**UI works:** ✅ Yes (with LOADED_OK bundles available)

---

## Notes

- Exit timestamp is optional - allows "exit by policy" Sniper mode
- Telemetry uses timezone-aware UTC timestamps for Python 3.10+ compatibility
- UI gracefully handles case when no LOADED_OK bundles exist
