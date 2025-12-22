# FAZ 2A — Tier Kanonikleştirme Raporu (PHASE2A_TIER_CANONICALIZATION)

**Tarih:** 2025-12-22  
**Durum:** ✅ COMPLETE

---

## Amaç

ONY'deki DIAMOND/GOLD/SILVER/BRONZE tier hesaplamasını **tek kaynağa** bağlayarak threshold drift riskini tamamen ortadan kaldırmak.

**Ilke:** Minimal risk, sıfır davranış değişikliği, tek kaynak (single source of truth).

---

## Değişen Dosyalar

| Dosya | Aksiyon | Satır Değişimi |
|-------|---------|----------------|
| `src/tezaver/rally/rally_grade_cards.py` | MODIFY | +36 |
| `src/tezaver/ui/ony_tab.py` | MODIFY | +5 -13 (net -8) |
| `tests/ui/test_ony_tier_filter.py` | MODIFY | +58 |

**Git Diff Summary:**
```
 src/tezaver/rally/rally_grade_cards.py | 36 +++++++++++++++++++++++++
 src/tezaver/ui/ony_tab.py              | 18 ++++---------
 tests/ui/test_ony_tier_filter.py       | 58 +++++++++++++++++++++++++++++++++++++++++
 3 files changed, 99 insertions(+), 13 deletions(-)
```

---

## İmplementasyon Detayları

### 1. Kanonik Helper (SOURCE OF TRUTH)

**Dosya:** `src/tezaver/rally/rally_grade_cards.py`  
**Fonksiyon:** `compute_tier_from_gain_pct(gain_pct: float) -> Optional[str]`

```python
def compute_tier_from_gain_pct(gain_pct: float) -> Optional[str]:
    """
    Canonical tier computation from future_max_gain_pct.
    
    This is the SINGLE SOURCE OF TRUTH for tier thresholds.
    All other tier computations should use this function.
    
    Thresholds (from GRADE_THRESHOLDS):
        - DIAMOND: >= 30%
        - GOLD:    >= 20%
        - SILVER:  >= 10%
        - BRONZE:  >= 5%
        - None:    < 5% (excluded)
    """
    if pd.isna(gain_pct) or gain_pct is None:
        return None
    
    if gain_pct >= GRADE_THRESHOLDS["Diamond"]:
        return "DIAMOND"
    elif gain_pct >= GRADE_THRESHOLDS["Gold"]:
        return "GOLD"
    elif gain_pct >= GRADE_THRESHOLDS["Silver"]:
        return "SILVER"
    elif gain_pct >= GRADE_THRESHOLDS["Bronze"]:
        return "BRONZE"
    else:
        return None
```

**Kaynak Eşikler:**
```python
GRADE_THRESHOLDS = {
    "Diamond": 0.30,  # 30%+
    "Gold": 0.20,     # 20%+
    "Silver": 0.10,   # 10%+
    "Bronze": 0.05,   # 5%+
}
```

---

### 2. ONY Wrapper (Drift Önleme)

**Dosya:** `src/tezaver/ui/ony_tab.py`  
**Değişiklik:** `compute_tier_from_gain()` içi boşaltıldı, canonical helper'a wrapper yapıldı.

**ÖNCE:**
```python
def compute_tier_from_gain(gain_pct: float) -> Optional[str]:
    if pd.isna(gain_pct):
        return None
    
    if gain_pct >= 0.30:      # HARDCODED THRESHOLDS
        return "DIAMOND"
    elif gain_pct >= 0.20:
        return "GOLD"
    # ... vs
```

**SONRA:**
```python
def compute_tier_from_gain(gain_pct: float) -> Optional[str]:
    """
    WRAPPER: This function now delegates to the canonical implementation
    in rally_grade_cards.py to prevent threshold drift.
    """
    from tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct
    return compute_tier_from_gain_pct(gain_pct)
```

**Sonuç:**
- ✅ ONY artık hardcoded threshold içermiyor
- ✅ `GRADE_THRESHOLDS` değişirse ONY otomatik uyumlu olur
- ✅ Davranış %100 aynı (backward compatible)

---

### 3. Test Coverage (Drift Detection)

**Dosya:** `tests/ui/test_ony_tier_filter.py`  
**Yeni Test Class:** `TestCanonicalTierSync`

**Test 1: Boundary Verification**
```python
def test_canonical_tier_sync(self):
    # 15 boundary case test:
    # 0.50 -> DIAMOND
    # 0.30 -> DIAMOND (exact boundary)
    # 0.299 -> GOLD (just below)
    # ...
    # 0.049 -> None (excluded)
    
    for gain, expected in test_cases:
        canonical_result = compute_tier_from_gain_pct(gain)
        ony_result = compute_tier_from_gain(gain)
        
        assert canonical_result == ony_result, \
            f"DRIFT DETECTED: canonical != ony at gain={gain}"
```

**Test 2: Null Handling**
```python
def test_canonical_tier_null_handling(self):
    # Verify None and pd.NA handled identically
    assert compute_tier_from_gain_pct(None) == compute_tier_from_gain(None) == None
    assert compute_tier_from_gain_pct(pd.NA) == compute_tier_from_gain(pd.NA) == None
```

---

## Test Sonuçları

**Pytest Output:**
```bash
$ pytest -q tests/ui/test_ony_tier_filter.py
.......                                        [100%]
7 passed in 0.56s
```

**Yeni Testler:**
- ✅ `test_canonical_tier_sync` (15 boundary cases)
- ✅ `test_canonical_tier_null_handling` (None/NA handling)

**Mevcut Testler (değişmeden geçti):**
- ✅ `test_normalize_tier_variants`
- ✅ `test_normalize_tier_unknown`
- ✅ `test_tier_boundaries`
- ✅ `test_tier_null_handling`
- ✅ `test_counts_and_filtering`

---

## Drift Risk Analizi

### Önceki Durum (Phase 1)
| Bileşen | Threshold Source | Drift Riski |
|---------|------------------|-------------|
| `rally_grade_cards.py` | `GRADE_THRESHOLDS` | ✅ Yok (canonical) |
| ONY | Hardcoded (0.30/0.20/0.10/0.05) | ⚠️ **ORTA** |

**Problem:** Eğer `GRADE_THRESHOLDS` değişirse, ONY'deki hardcoded değerler manuel güncellenmesi gerekir → Drift riski.

### Yeni Durum (Phase 2A)
| Bileşen | Threshold Source | Drift Riski |
|---------|------------------|-------------|
| `rally_grade_cards.py` | `GRADE_THRESHOLDS` | ✅ Yok (canonical) |
| ONY | `compute_tier_from_gain_pct()` wrapper | ✅ **YOK** |

**Sonuç:** `GRADE_THRESHOLDS` tek kaynak, tüm bileşenler otomatik senkronize.

---

## Acceptance Criteria

- [x] Kanonik helper `compute_tier_from_gain_pct()` eklendi
- [x] `GRADE_THRESHOLDS` tek source of truth
- [x] ONY wrapper'a dönüştürüldü (hardcoded thresholds silindi)
- [x] Davranış değişmedi (backward compatible)
- [x] Boundary tests eklendi (drift detection)
- [x] Tüm testler geçti (7/7)
- [x] Circular import yok

---

## Gelecek İyileştirmeler (Opsiyonel)

1. **Diğer Bileşenlerde Kullanım:**
   - Eğer başka dosyalarda da tier computation varsa (örn: `rally_grading.py`), onları da wrapper'layabilir.

2. **Event Dataset'e `rally_grade` Kolonu Ekleme:**
   - Eğer gelecekte scanner'lar `rally_grade` kolonunu eklerse:
     - ONY önceliği: `event.rally_grade` (varsa) → `compute_tier_from_gain_pct()` (fallback)

3. **Grade Label Format:**
   - Şu an canonical "DIAMOND", mevcut `GRADE_THRESHOLDS` "Diamond" kullanıyor.
   - İhtiyaç olursa `compute_grade_label_from_gain_pct()` eklenebilir (lowercase/emoji formatları için).

---

## Sonuç

✅ **Drift riski ortadan kaldırıldı.**  
✅ **Tek kaynak:** `rally_grade_cards.GRADE_THRESHOLDS`  
✅ **ONY artık wrapper:** Threshold değişikliği → Otomatik senkronizasyon  
✅ **Test coverage:** Drift detection testleri eklendi
