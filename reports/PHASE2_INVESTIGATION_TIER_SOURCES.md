# Phase 2 Pre-Investigation Report: Tier/Grade Sources

**Date:** 2025-12-22  
**Status:** ✅ COMPLETE

---

## Executive Summary

**Objective:** Identify where Diamond/Gold/Silver/Bronze tier/grade originates for 15m/1h/4h timeframes and prevent drift in ONY tier filtering.

**Key Findings:**
1. ✅ **Canonical Source Found:** `rally_grade_cards.py` Line 17-22 defines `GRADE_THRESHOLDS`
2. ❌ **No `rally_grade` Column:** None of the rally datasets (15m/1h/4h) contain a pre-computed `rally_grade` column
3. ⚠️ **Drift Risk:** ONY currently uses custom `compute_tier_from_gain()` with correct thresholds BUT separately defined
4. ✅ **ONY Thresholds Match:** Current ONY implementation matches canonical source (30/20/10/5%)

---

## Detailed Findings

### 1. Canonical Tier Thresholds (SOURCE OF TRUTH)

**File:** `src/tezaver/rally/rally_grade_cards.py`  
**Lines:** 17-22

```python
GRADE_THRESHOLDS = {
    "Diamond": 0.30,  # 30%+
    "Gold": 0.20,     # 20%+
    "Silver": 0.10,   # 10%+
    "Bronze": 0.05,   # 5%+
}
```

**Usage:** Used in `_build_grade_summary()` to compute grade statistics from `future_max_gain_pct`

---

### 2. Alternative Grading System (NOT USED in datasets)

**File:** `src/tezaver/rally/rally_grading.py`  
**Lines:** 93-113

```python
def grade_rally(rally: pd.Series, use_context: bool = False) -> str:
    """
    Tiers based on COMPOSITE SCORE (not just gain):
    - 💎 Diamond: Score >= 85
    - 🥇 Gold: Score >= 70
    - 🥈 Silver: Score >= 55
    - 🥉 Bronze: Score < 55
    """
```

**Note:** This uses a weighted scoring system (gain 35%, quality 25%, momentum 20%, context 15%, retention 5%). NOT used in current rally datasets. Only gain-based thresholds are used.

---

### 3. Dataset Column Schemas

#### 15m (Fast15)
**Path:** `library/fast15_rallies/{SYMBOL}/fast15_rallies.parquet`  
**Key Columns:**
- `event_time` ✅
- `future_max_gain_pct` ✅ (used for tier computation)
- `bars_to_peak` ✅
- `quality_score`, `rally_shape`, `rally_bucket`
- Multi-TF features: `rsi_15m/1h/4h/1d`, `volume_rel_*`, `macd_*`, `trend_soul_*`, `regime_*`

**Has `rally_grade` column:** ❌ NO

#### 1h (Time Labs)
**Path:** `library/time_labs/1h/{SYMBOL}/rallies_1h.parquet`  
**Key Columns:**
- `event_time` ✅
- `future_max_gain_pct` ✅ (used for tier computation)
- `bars_to_peak` ✅
- Same multi-TF structure as 15m

**Has `rally_grade` column:** ❌ NO

#### 4h (Time Labs)
**Path:** `library/time_labs/4h/{SYMBOL}/rallies_4h.parquet`  
**Key Columns:**
- Same as 1h

**Has `rally_grade` column:** ❌ NO

---

### 4. ONY Current Implementation

**File:** `src/tezaver/ui/ony_tab.py`  
**Lines:** 68-90 (added in Phase 1)

```python
def compute_tier_from_gain(gain_pct: float) -> Optional[str]:
    if gain_pct >= 0.30:  return "DIAMOND"
    elif gain_pct >= 0.20: return "GOLD"
    elif gain_pct >= 0.10: return "SILVER"
    elif gain_pct >= 0.05: return "BRONZE"
    else: return None
```

**Thresholds:** ✅ Match  `GRADE_THRESHOLDS` from `rally_grade_cards.py`  
**Problem:** ⚠️ Separate definition = drift risk if canonical source changes

---

## Drift Risk Analysis

| Component | Source | Threshold Match | Drift Risk |
|-----------|--------|-----------------|------------|
| `rally_grade_cards.py` | Canonical | N/A | ✅ None (source) |
| `rally_grading.py` | Composite score | ❌ Different system | ⚠️ Not used |
| ONY `compute_tier_from_gain()` | Custom | ✅ Matches canonical | ⚠️ **MEDIUM** (separate def) |
| Rally datasets (15m/1h/4h) | None | N/A | ✅ None (computed) |

**Recommendation:** Centralize tier computation by importing/using `GRADE_THRESHOLDS` from `rally_grade_cards.py` in ONY.

---

## Action Items (Phase 2B)

1. **Create Centralized Helper:**
   - Add `compute_tier_from_gain_pct(gain: float, thresholds: dict = GRADE_THRESHOLDS)` to `rally_grade_cards.py`
   - Make it reusable across all tier computation use cases

2. **Update ONY:**
   - Import centralized helper from `rally_grade_cards.py`
   - Remove duplicate threshold definitions
   - Maintain backward compatibility

3. **Future-Proof:**
   - If rally datasets ever add `rally_grade` column, ONY should:
     1. First check `event.rally_grade` (if exists)
     2. Normalize using `normalize_tier()`
     3. Fallback to centralized `compute_tier_from_gain_pct()`

---

## Appendix: Tier Mapping Summary

| Tier | Threshold | Criteria |
|------|-----------|----------|
| 💎 DIAMOND | ≥30% | `future_max_gain_pct >= 0.30` |
| 🥇 GOLD | ≥20% | `0.20 <= future_max_gain_pct < 0.30` |
| 🥈 SILVER | ≥10% | `0.10 <= future_max_gain_pct < 0.20` |
| 🥉 BRONZE | ≥5% | `0.05 <= future_max_gain_pct < 0.10` |
| ❌ (Excluded) | <5% | `future_max_gain_pct < 0.05` |
