# Rally Detector v2 REV.04 - Multi-Coin Calibration & UI Overlay

**Date:** 2025-12-09
**Status:** Implemented (Lab/Experimental)

## 1. Multi-Coin Calibration Results (Lab)

Rally Detector v2 Micro-Booster was evaluated on 4 major coins (15m timeframe).
**Goal:** Verify event counts are reasonable (<400) and gains are meaningful.

| Symbol | Event Count | Status | Notes |
|---|---|---|---|
| **BTCUSDT** | 66 | ✅ OK | High precision, lower frequency |
| **ETHUSDT** | 150 | ✅ OK | Healthy number of micro-rallies |
| **BNBUSDT** | 98 | ✅ OK | Balanced |
| **SOLUSDT** | 354 | ✅ OK | High activity, near upper limit (400) |

**Parameter Settings:**
- Min Gain: 5.5%
- Duration: 4-24 bars
- Volume Spike: 1.5x - 10.0x
- Ignition Lookback: 3 bars

**Conclusion:**
The V2 booster is well-calibrated. It provides additional high-momentum signals without flooding the system (Event counts << 1000). SOLUSDT is the most active, justifying its use as the calibration baseline.

## 2. Fast15 UI Overlay (Analist Modu)

A new **"Veri Kaynağı"** (View Mode) toggle has been added to the Fast15 Lab tab.

**Modes:**
1. **Core Fast15 (Production):** 
   - Default view.
   - Shows existing scanner events.
   - Unchanged behavior.
2. **Rally Detector v2 (Lab/Booster):**
   - **Analyst Mode.**
   - Calculates V2 micro-rallies in real-time.
   - Displays summary metrics (Count, Avg Gain).
   - Shows a dedicated table with `future_max_gain_pct`, `bars_to_peak`, `source`.

**Usage:**
- Select a coin (e.g., SOLUSDT).
- Switch toggle to "Rally Detector v2".
- Analyze the micro-booster events vs Core events.

## 3. System Integrity

- **Oracle v1:** Preserved (77 rallies, read-only). Tests passing.
- **Core Scanner:** Unchanged.
- **Offline Maintenance:** Unchanged.
- **V2 Artifacts:** Eval stats saved in `data/rally_detector_v2_stats/15m/`.

---
**Next Steps:**
- Gather analyst feedback on V2 signals via the UI.
- Consider merging V2 signals into Core Scanner in a future release if value is proven.
