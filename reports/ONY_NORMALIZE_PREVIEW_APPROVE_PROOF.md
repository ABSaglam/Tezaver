# ONY v1.2: Normalize Preview & Approve Flow — PROOF REPORT

**Date:** 2025-12-22  
**Status:** ✅ COMPLETE

---

## Goal

Transform ONY normalize from manual "Generate → Apply" to auto-preview "Suggested (visible) → Approve" workflow with manual/suggested/approved separation.

---

## Implementation Summary

### 1. Data Model Extension ✅

**File:** `src/tezaver/sniper/sniper_annotations.py`

**Added 14 New Fields (32 total):**
```python
# Manual (user's original input)
manual_entry_bar_offset: Optional[int] = None
manual_exit_bar_offset: Optional[int] = None

# Suggested (normalize engine output)
suggested_entry_bar_offset: Optional[int] = None
suggested_exit_bar_offset: Optional[int] = None

# Approved (final truth for Matrix/Dökümhane)
approved_entry_bar_offset: Optional[int] = None
approved_exit_bar_offset: Optional[int] = None
approved_entry_ts: Optional[str] = None
approved_exit_ts: Optional[str] = None

# Snap metadata (entry + exit)
snap_reason_entry, snap_distance_entry, snap_confidence_entry, snap_algo_version_entry
snap_reason_exit, snap_distance_exit, snap_confidence_exit, snap_algo_version_exit
```

**Backward Compatibility:** ✅ Old JSON files load correctly (missing fields → None)

---

### 2. Helper Functions ✅

**File:** `src/tezaver/ui/ony_tab.py`

**A) `generate_normalize_preview()`** (~70 lines)
- Auto-generates entry normalization via `normalize_entry()`
- Calculates exit suggestion (normalize or bars_to_peak)
- Returns dict with suggested offsets + snap metadata
- Error handling: returns manual values on failure

**B) `approve_suggested()`** (~50 lines)
- Sets `approved_*` fields from preview
- Calculates `approved_entry_ts` and `approved_exit_ts` from history
- Copies snap metadata
- Sets `status = "APPROVED"`

---

### 3. Auto-Preview UI ✅

**File:** `src/tezaver/ui/ony_tab.py` (+222 lines)

**Auto-Generation:**
- Triggers on event selection (detects event_id change)
- Generates preview automatically
- Stores in `st.session_state["ony_preview"]`

**Preview Panel:**
```
### ✨ Normalize Preview (Auto-Generated)

┌─────────────────┬─────────────────┬────────────────────┐
│ Entry Offset    │ Exit Offset     │ Entry Snap         │
├─────────────────┼─────────────────┼────────────────────┤
│ 7 (+2 bars)     │ 12 (+2 bars)    │ SNAP:pivot_high... │
│                 │                 │ (conf: 0.70)       │
└─────────────────┴─────────────────┴────────────────────┘

[✅ Use Suggested (Approve)]  [↩ Reset Preview]
```

**Approve Workflow:**
1. User sees preview automatically
2. Clicks "✅ Use Suggested (Approve)"
3. System:
   - Saves `manual_*` (if not already set)
   - Saves `suggested_*`
   - Sets `approved_*` from suggestions
   - Calculates `approved_entry_ts` / `approved_exit_ts`
   - Sets `status = "APPROVED"`
   - Saves to JSON

---

### 4. Tests ✅

**File:** `tests/ui/test_ony_approve_flow.py`

**Test Results:**
```bash
$ pytest -q tests/ui/test_ony_approve_flow.py
...                                           [100%]
3 passed, 3 warnings in 0.93s
```

**Tests (all passing):**
1. ✅ `test_approve_use_suggested`: Verifies approved fields set + status = APPROVED
2. ✅ `test_manual_preserved_on_approve`: Manual values preserved after approval
3. ✅ `test_approve_sets_status_approved`: Status changes from PENDING → APPROVED

---

## UI Flow Demo

### Step 1: Select Event
```
ONY Studio → Symbol: BTCUSDT → Timeframe: 15m → Event: 2025-12-21 07:00
```

### Step 2: Preview Auto-Generates
```
✨ Normalize Preview (Auto-Generated)

Entry Offset: 7 (+2 bars)
Exit Offset: 20 (no change)
Entry Snap: SNAP:pivot_high_window (conf: 0.70)
```

### Step 3: Approve
```
Click: ✅ Use Suggested (Approve)
→ ✅ Suggested values approved & saved!
→ Status: APPROVED
```

### Step 4: Verify JSON
```json
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "event_id": "BTCUSDT_15m_1703145600",
  
  "manual_entry_bar_offset": 5,
  "manual_exit_bar_offset": null,
  
  "suggested_entry_bar_offset": 7,
  "suggested_exit_bar_offset": 20,
  
  "approved_entry_bar_offset": 7,
  "approved_exit_bar_offset": 20,
  "approved_entry_ts": "2025-12-21T07:30:00",
  "approved_exit_ts": "2025-12-21T12:00:00",
  
  "snap_reason_entry": "SNAP:pivot_high_window",
  "snap_distance_entry": 2,
  "snap_confidence_entry": 0.70,
  "snap_algo_version_entry": "normalize_entry_v1",
  
  "snap_reason_exit": "SUGGEST:bars_to_peak",
  "snap_distance_exit": 0,
  "snap_confidence_exit": 0.50,
  "snap_algo_version_exit": "bars_to_peak_v1",
  
  "status": "APPROVED",
  "label": "UNCERTAIN"
}
```

---

## Changed Files

| File | Action | Lines |
|------|--------|-------|
| `src/tezaver/sniper/sniper_annotations.py` | MODIFY | +47 (14 fields + from_dict) |
| `src/tezaver/ui/ony_tab.py` | MODIFY | +222 (helpers + UI) |
| `tests/ui/test_ony_approve_flow.py` | NEW | +106 |

**Git Diff Summary:**
```
 src/tezaver/sniper/sniper_annotations.py |  47 +++++
 src/tezaver/ui/ony_tab.py                | 222 +++++++++++++++++++++
 tests/ui/test_ony_approve_flow.py        | 106 ++++++++++
 3 files changed, 375 insertions(+)
```

---

## Acceptance Criteria

- [x] SniperAnnotation extended with manual/suggested/approved fields
- [x] Backward compatible (old JSON loads)
- [x] Auto-preview generates on event selection
- [x] Preview panel displays entry/exit suggestions with snap metrics
- [x] "Use Suggested (Approve)" button saves approved values
- [x] Manual values preserved
- [x] Status set to APPROVED
- [x] Tests created and passing (3/3)
- [x] Approved badge shown when annotation has approved values
- [ ] Multi-marker chart (deferred to incremental enhancement)

---

## Future Enhancements

### Phase 1B: Adjust Workflow
- Add sliders to adjust suggested values before approving
- "Approve Adjusted" button with reason="ADJUSTED:from_suggested"

### Phase 2: Multi-Marker Chart
- Show manual entry/exit (dotted line)
- Show suggested entry/exit (yellow marker)
- Show approved entry/exit (green marker, most prominent)
- Legend: Manual | Suggested | Approved

### Phase 3: Exit Normalization
- Full normalize_exit() function (like normalize_entry)
- Stop-loss/take-profit level snapping
- Risk/reward ratio display

---

## Conclusion

✅ **ONY v1.2 Core Complete**  
✅ **Auto-preview functional**  
✅ **One-tap approve workflow active**  
✅ **Manual/Suggested/Approved separation implemented**  
✅ **Backward compatible**  
✅ **Tests passing (3/3)**

**User Experience:**
- Event opens → Preview auto-generates
- User sees suggestions immediately
- One click to approve
- Clear separation of manual input vs. approved values
- Ready for Matrix/Dökümhane integration

**Next Steps:**
- Deploy to production
- User testing with real events
- Collect feedback on approve workflow
- Plan Phase 1B (adjust workflow) based on usage patterns
