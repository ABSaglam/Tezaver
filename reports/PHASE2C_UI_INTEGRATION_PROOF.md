# FAZ 2C-UI — ONY STUDIO NORMALIZE INTEGRATION PROOF

**Tarih:** 2025-12-22  
**Durum:** ✅ COMPLETE

---

## Amaç

ONY Studio'ya Normalize v1 entegrasyonu: Normalize (Entry) butonu + sonuç paneli + Apply/Reset fonksiyonelliği.

---

## İmplementasyon Özeti

### 1. ONY Studio UI Enhancements

**Dosya:** `src/tezaver/ui/ony_tab.py` (+149 lines)

**A) Helper Function:**
```python
def apply_normalize_to_annotation(annotation, norm_result) -> annotation:
    """Apply NormalizeResult to SniperAnnotation."""
    annotation.entry_bar_offset = norm_result.entry_offset_out
    annotation.normalized_entry_bar_offset = norm_result.entry_offset_out
    annotation.normalized_entry_ts = norm_result.entry_ts_iso
    annotation.snap_reason = norm_result.snap_reason
    annotation.snap_distance_bars = norm_result.snap_distance_bars
    annotation.snap_confidence = norm_result.snap_confidence
    annotation.snap_algo_version = norm_result.snap_algo_version
    return annotation
```

**B) Normalize Button:**
- Location: After entry/exit configuration, before status/label
- Label: "🧲 Normalize (Entry)"
- Action:
  1. Parse `event_time` to pd.Timestamp
  2. Call `normalize_entry(symbol, timeframe, event_time, entry_bar_offset)`
  3. Store result in `st.session_state["ony_norm_result"]`
  4. Show success/error message

**C) Result Panel (Expander):**
- Title: "📊 Normalize Result"
- 3 columns showing:
  - **Col 1:** Entry Offset (in/out)
  - **Col 2:** Snap Distance, Snap Confidence
  - **Col 3:** Normalized Entry TS, Snap Reason
- Expanded by default when result exists

**D) Apply Button:**
- Label: "✅ Apply"
- Type: Primary (blue)
- Action:
  1. Load or create SniperAnnotation
  2. Call `apply_normalize_to_annotation(ann, norm_result)`
  3. Save to repository via `repo.append(...)`
  4. Show success message + `st.rerun()`

**E) Reset Button:**
- Label: "↩ Reset"
- Action:
  1. Clear `st.session_state["ony_norm_result"]`
  2. If annotation exists, set all normalized fields to None
  3. Save + `st.rerun()`
  4. Note: Does NOT change `entry_bar_offset` (preserves manual edits)

**F) Normalized Badge:**
- Shown when annotation has `normalized_entry_ts`
- Format: `✅ Normalized: {snap_reason} | TS: {normalized_entry_ts}`
- Location: Below Normalize section

---

### 2. Error Handling

**History Not Found:**
```
❌ History data not found: FileNotFoundError(...)
```

**Invalid Event Time:**
```
❌ Normalize error: ...
```

**Debug Mode:**
- On exception, shows full traceback with `st.code(traceback.format_exc())`

---

### 3. Test Coverage ✅

**Dosya:** `tests/ui/test_ony_normalize_ui_apply.py`

**Test Results:**
```bash
$ pytest -q tests/ui/test_ony_normalize_ui_apply.py
...                                     [100%]
3 passed, 3 warnings in 0.78s
```

**Tests (all passing):**
1. ✅ `test_apply_populates_all_fields`: Verifies all normalized fields populated
2. ✅ `test_apply_updates_entry_offset`: Verifies entry_bar_offset updated to snapped value
3. ✅ `test_apply_with_keep_reason`: Verifies KEEP case (no snap)

**Warnings:** Deprecation warning for `datetime.utcnow()` (non-critical)

---

## UI Flow Demo

### Step 1: Select Event
```
ONY Studio → Symbol: BTCUSDT → Timeframe: 15m → Event: 2025-12-21 07:00
```

### Step 2: Set Entry Offset
```
Entry Bar Offset: 5
```

### Step 3: Click Normalize
```
🧲 Normalize (Entry) → ✅ Normalize computed successfully!
```

### Step 4: View Result Panel
```
📊 Normalize Result (expanded)
┌─────────────────┬──────────────────┬────────────────────────┐
│ Entry Offset    │ Snap Metrics     │ Timestamp & Reason     │
├─────────────────┼──────────────────┼────────────────────────┤
│ In:  5          │ Distance: 2 bars │ TS: 2025-12-21T07:30:00│
│ Out: 7          │ Confidence: 0.70 │ Reason: SNAP:pivot_... │
└─────────────────┴──────────────────┴────────────────────────┘
```

### Step 5: Apply Normalize
```
✅ Apply → ✅ Normalize applied & saved!
```

### Step 6: Verify JSON
```json
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "event_id": "BTCUSDT_15m_1734849600",
  "entry_bar_offset": 7,
  "normalized_entry_bar_offset": 7,
  "normalized_entry_ts": "2025-12-21T07:30:00",
  "snap_reason": "SNAP:pivot_high_window",
  "snap_distance_bars": 2,
  "snap_confidence": 0.70,
  "snap_algo_version": "normalize_entry_v1",
  "note": "",
  "status": "PENDING",
  "label": "UNCERTAIN"
}
```

---

## Değişen Dosyalar

| Dosya | Aksiyon | Satır Değişimi |
|-------|---------|----------------|
| `src/tezaver/ui/ony_tab.py` | MODIFY | +149 |
| `tests/ui/test_ony_normalize_ui_apply.py` | NEW | +106 |

**Git Diff Summary:**
```
 src/tezaver/ui/ony_tab.py                     | 149 +++++++++++++++++++
 tests/ui/test_ony_normalize_ui_apply.py       | 106 +++++++++++++
 2 files changed, 255 insertions(+)
```

---

## Acceptance Criteria

- [x] "🧲 Normalize (Entry)" button added to ONY Studio
- [x] Result panel displays metrics (offset in/out, distance, confidence, TS, reason)
- [x] "✅ Apply" button saves normalized fields to annotation JSON
- [x] "↩ Reset" button clears normalized fields
- [x] Normalized badge shown when annotation has normalized data
- [x] Error handling for missing history data
- [x] Helper function `apply_normalize_to_annotation()` created
- [x] Tests created and passing (3/3)
- [x] Backward compatible (old annotations still work)

---

## Gelecek İyileştirmeler

1. **Chart Marker Update:**
   - After Apply, update chart marker to show snapped offset position
   - Visual feedback on normalized entry point

2. **Batch Normalize:**
   - "Normalize All Events" button
   - Apply normalize to multiple events at once

3. **Exit Normalization:**
   - Extend to exit_bar_offset → normalized_exit_ts
   - Snap to stop-loss/take-profit levels

4. **History Validation:**
   - Pre-check history availability before showing Normalize button
   - Gracefully handle missing data

---

## Sonuç

✅ **Phase 2C-UI Integration complete**  
✅ **ONY Studio now has Normalize functionality**  
✅ **Test coverage: 3/3 passing**  
✅ **Backward compatible**  
✅ **User-visible and functional**

**Phase 2 (A+B+C+C-UI) TAMAMLANDı! 🎉**
