# Cancel Rule Sanity Check

**Rule:** `IF Wick_Ratio_4h_avg > 0.28 THEN CANCEL`

## Verification
- **FAIL Day (2025-11-30):** Val=0.29 -> **CANCELLED** (Correct) ✅
- **SUCCESS Day (2025-12-02):** Val=0.28 -> **KEPT** (Correct) ✅
