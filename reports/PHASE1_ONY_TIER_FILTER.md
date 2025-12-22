# FAZ 1 — ONY Tier Filter Raporu (PHASE1_ONY_TIER_FILTER)

**Tarih:** 2025-12-22  
**Durum:** ✅ COMPLETE

---

## Özellik Özeti

ONY Studio'ya **tier (DIAMOND/GOLD/SILVER/BRONZE) seçimi** eklendi:
- Event dropdown'ın ÜSTÜNDE tier seçici widget
- Her tier yanında adet gösterimi: `DIAMOND (12)`
- Seçilen tier'a göre event listesi FİLTRELENİYOR
- Unknown/düşük gain'li event'ler listeye girmez

---

## Değişen Dosyalar

| Dosya | Aksiyon | Satır |
|-------|---------|-------|
| `src/tezaver/ui/ony_tab.py` | MODIFY | +109 -5 |
| `tests/ui/test_ony_tier_filter.py` | NEW | +159 |

**Git Diff Summary:**
```
 src/tezaver/ui/ony_tab.py           | 114 +++++++++++++++++++++++++++++++--
 tests/ui/test_ony_tier_filter.py    | 159 +++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 268 insertions(+), 5 deletions(-)
```

---

## İmplementasyon Detayları

### 1. Tier Helper Functions

**`normalize_tier(value)`**
- Input: Tier string ("diamond", "DIAMOND", "DIA", "💎", vs.)
- Output: Standardize tier ("DIAMOND", "GOLD", "SILVER", "BRONZE") veya None
- Unknown/invalid değerler filtrelenir

**`compute_tier_from_gain(gain_pct)`**
- Input: `future_max_gain_pct` (örn: 0.30 = %30)
- Output: Tier mapping:
  - ≥30% → DIAMOND
  - ≥20% → GOLD
  - ≥10% → SILVER
  - ≥5% → BRONZE
  - <5% → None (exclude)

### 2. UI Değişiklikleri

**ONY Studio Tier Selector (Event Dropdown ÜZERİNDE):**
```python
st.radio(
    "🏆 Tier Seç:",
    ["DIAMOND (12)", "GOLD (25)", "SILVER (8)", "BRONZE (3)"],
    horizontal=True
)
```

**Davranış:**
- Tier değiştiğinde event dropdown resetlenir (stale selection kalmasın)
- Sadece seçili tier'ın event'leri gösterilir
- Counts dinamik olarak hesaplanır

### 3. Veri Akışı

```
Load Events → Compute/Normalize Tier → Filter by Tier → Count → Display
```

- Event'te `rally_grade` varsa normalize et
- Yoksa `future_max_gain_pct`'den compute et
- Tier==None olan event'leri DROP et
- Seçili tier'a göre filtrele

---

## Test Sonuçları

**Pytest Output:**
```bash
$ pytest -xvs tests/ui/test_ony_tier_filter.py
tests/ui/test_ony_tier_filter.py::TestNormalizeTier::test_normalize_tier_variants PASSED
tests/ui/test_ony_tier_filter.py::TestNormalizeTier::test_normalize_tier_unknown PASSED
tests/ui/test_ony_tier_filter.py::TestComputeTierFromGain::test_tier_boundaries PASSED
tests/ui/test_ony_tier_filter.py::TestComputeTierFromGain::test_tier_null_handling PASSED
tests/ui/test_ony_tier_filter.py::TestTierFiltering::test_counts_and_filtering PASSED

5 passed in 0.60s
```

**Test Coverage:**
- ✅ Tier variant normalization (diamond/DIAMOND/DIA/💎)
- ✅ Unknown tier handling (None return)
- ✅ Gain percentage tier boundaries
- ✅ Null/NA value handling
- ✅ Tier counting with mixed data
- ✅ Event filtering (unknown events excluded)

---

## Demo Senaryo

1. Kullanıcı ONY Studio'yu açar
2. Symbol: BTCUSDT, Timeframe: 15m seçer
3. **Tier selector görünür:**
   - DIAMOND (3)
   - GOLD (12)
   - SILVER (28)
   - BRONZE (15)
4. DIAMOND seçer → Dropdown'da sadece 3 DIAMOND event görünür
5. GOLD seçer → Event dropdown resetlenir, 12 GOLD event gösterilir
6. Event seçimi sadece filtered_events üzerinden gerçekleşir

---

## Acceptance Criteria

- [x] Tier selector event dropdown ÜZERINDE
- [x] 4 tier: DIAMOND, GOLD, SILVER, BRONZE
- [x] Her tier yanında count: "DIAMOND (X)"
- [x] Seçili tier'a göre event dropdown filtrelenir
- [x] Unknown/low-gain event'ler listeye girmez
- [x] Tier değiştiğinde event selection resetlenir
- [x] Test coverage: tier normalization + filtering
- [x] Tüm testler PASS

---

## Gelecek İyileştirmeler (Opsiyonel)

- Queue ekranında tier badge gösterimi
- Tier bazlı istatistikler (avg quality, avg bars_to_peak)
- Tier renk kodlaması (DIAMOND=💎, GOLD=🥇, vs.)
