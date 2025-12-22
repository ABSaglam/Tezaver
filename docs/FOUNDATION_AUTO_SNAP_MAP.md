# FOUNDATION_AUTO_SNAP_MAP — Dökümhane v1 Öncesi Arkeoloji

**Tarih:** 2025-12-22  
**Amaç:** Auto-snap + ONY approval akışını belgelemek ve Dökümhane v1 için kilitlenecek kontratları tespit etmek.

---

## 1) Call Graph (UI → Approve → Write)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ONY APPROVAL FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [UI: Sniper Lab / Chart Area]                                              │
│         │                                                                    │
│         ▼                                                                    │
│  ┌──────────────────┐                                                       │
│  │ User marks entry │  (entry_bar_offset seçilir)                           │
│  │ on chart         │                                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                  │
│           ▼                                                                  │
│  ┌────────────────────────────────────────────┐                             │
│  │ SniperAnnotationRepository.append()        │                             │
│  │ - symbol, timeframe, event_id              │                             │
│  │ - entry_bar_offset, exit_bar_offset        │                             │
│  │ - status: PENDING → APPROVED               │                             │
│  │ - label: GOOD / BAD / UNCERTAIN            │                             │
│  └────────┬───────────────────────────────────┘                             │
│           │                                                                  │
│           │ Writes to:                                                       │
│           │ data/sniper/{symbol}/{timeframe}/sniper_annotations_v1.json     │
│           ▼                                                                  │
│  ┌────────────────────────────────────────────┐                             │
│  │ sniper_story_builder.py                    │                             │
│  │ - Joins entry_bar_offset with patterns     │                             │
│  │ - Finds nearest timestamp                  │                             │
│  │ - Outputs: sniper_entries_v1.parquet       │                             │
│  └────────────────────────────────────────────┘                             │
│                                                                              │
│  [Matrix V4 Approval Flow - Ayrı]                                           │
│         │                                                                    │
│         ▼                                                                    │
│  ┌────────────────────────────────────────────┐                             │
│  │ platform_bindings.approve_export()         │                             │
│  │ - home/candidates/{cid}/manifest.json      │                             │
│  │ - Writes: home/approved/{cid}/manifest.json│                             │
│  │ - approved_at, status: APPROVED            │                             │
│  └────────────────────────────────────────────┘                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Anahtar Noktalar
- **Entry/Exit kaynağı:** UI'de `entry_bar_offset` olarak seçilir
- **Onay yazım yeri:** `SniperAnnotationRepository.save_all()` → `data/sniper/{symbol}/{tf}/sniper_annotations_v1.json`
- **Candidate→Approved:** `platform_bindings.approve_export()` veya `approved_pool.promote_candidate_from_run()`

---

## 2) Auto-Snap Algoritmaları

### 2.1) `_find_nearest_levels()` — mac/export/story_builder.py:304-316
```python
def _find_nearest_levels(self, entry_price: float, levels: List[Dict]) -> Dict:
    supports = [l for l in levels if l['type'] == 'support' and l['level_price'] < entry_price]
    supports.sort(key=lambda x: x['level_price'], reverse=True)
    
    resistances = [l for l in levels if l['type'] == 'resistance' and l['level_price'] > entry_price]
    resistances.sort(key=lambda x: x['level_price'])
    
    return {
        "nearest_support": supports[0]['level_price'] if supports else None,
        "support_strength": supports[0]['strength_score'] if supports else None,
        "nearest_resistance": resistances[0]['level_price'] if resistances else None,
        "resistance_strength": resistances[0]['strength_score'] if resistances else None
    }
```

| Özellik | Değer |
|---------|-------|
| Girdi | `entry_price`, `levels` listesi |
| Çıktı | `nearest_support`, `nearest_resistance` + strength |
| Closed-bar kuralı | ❌ Yok (fiyat bazlı) |
| Pivot bazlı | ✅ Evet (levels pivot'tan geliyor) |
| snap_distance | ❌ Hesaplanmıyor |
| snap_reason | ❌ Üretilmiyor |

### 2.2) Pivot Detection — levels/trend_levels_engine.py:37-68
```python
def detect_pivots(df: pd.DataFrame, window: int = PIVOT_WINDOW) -> pd.DataFrame:
    # Pivot High: high[i] > neighbors (window bars each side)
    # Pivot Low: low[i] < neighbors
    df.loc[is_high, "pivot_high"] = 1
    df.loc[is_low, "pivot_low"] = 1
```

| Özellik | Değer |
|---------|-------|
| Window | PIVOT_WINDOW = 2 (2 sol, 2 sağ) |
| Çıktı | `pivot_high`, `pivot_low` sütunları |
| Zone merge | %0.3 tolerans |

### 2.3) Nearest Timestamp Match — sniper_story_builder.py:196-205
```python
# Try to find nearest timestamp
ts_diffs = abs(full_df["ts"] - pattern_ts)
min_idx = ts_diffs.idxmin()
if ts_diffs.iloc[min_idx] < pd.Timedelta(minutes=20):
    start_bar_index = int(full_df.loc[min_idx, "bar_index"])
```

| Özellik | Değer |
|---------|-------|
| Tolerans | 20 dakika |
| Girdi | pattern_ts, full_df["ts"] |
| Çıktı | `start_bar_index` |

---

## 3) ONY Veri Modeli (Annotation + Storage)

### 3.1) SniperAnnotation — sniper/sniper_annotations.py:22-54
```python
@dataclass
class SniperAnnotation:
    symbol: str
    timeframe: str
    event_id: str              # rally / pattern ID
    entry_bar_offset: int      # Bar offset (0 = ilk bar)
    note: str = ""
    created_at: str = ...
    
    # Optional
    exit_bar_offset: Optional[int] = None
    tags: Optional[List[str]] = None
    
    # V2 Workflow
    status: SniperStatus = "PENDING"   # PENDING | REVIEWED | APPROVED | REJECTED
    label: SniperLabel = "UNCERTAIN"   # GOOD | BAD | UNCERTAIN
```

### 3.2) Storage Path
```
data/sniper/{SYMBOL}/{TIMEFRAME}/sniper_annotations_v1.json
```

### 3.3) Okuma/Yazma
| Fonksiyon | Dosya |
|-----------|-------|
| `SniperAnnotationRepository.load_all(sym, tf)` | Okur |
| `SniperAnnotationRepository.save_all(sym, tf, anns)` | Yazar |
| `SniperAnnotationRepository.upsert_annotation(ann)` | Günceller |

### 3.4) Entry/Exit Birim
- **Entry:** `entry_bar_offset` (int) — Rally penceresindeki bar offset
- **Exit:** `exit_bar_offset` (Optional[int]) — Aynı şekilde offset
- **Timestamp yok!** Offset'ten timestamp hesaplanır

---

## 4) Kontrat Gap Listesi (Field-by-Field)

### 4.1) Mevcut approved manifest örneği
```json
{
  "candidate_id": "BTCUSDT_15m_1766258510",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "build_ts": 1766258510,
  "builder": "mac_agent",
  "params": {"entry": "breakout"},
  "approved_at": 1766258609,
  "status": "APPROVED"
}
```

### 4.2) Gap Analizi

| Alan | Mevcut | Dökümhane v1 için | Kaynak |
|------|--------|-------------------|--------|
| `approved_entry_ts` | ❌ | ✅ GEREKLİ | annotation'dan hesaplanabilir |
| `approved_exit_ts` | ❌ | ✅ GEREKLİ | exit_bar_offset'ten hesaplanabilir |
| `entry_bar_offset` | ❌ (manifest) | ✅ GEREKLİ | SniperAnnotation'da VAR |
| `exit_bar_offset` | ❌ (manifest) | ✅ GEREKLİ | SniperAnnotation'da VAR (Optional) |
| `snap_reason` | ❌ | ✅ GEREKLİ | Hesaplanmıyor, EKLENMELİ |
| `snap_distance_bars` | ❌ | ⚡ Önerilen | Hesaplanmıyor |
| `snap_confidence` | ❌ | ⚡ Önerilen | `resolve_confidence` var ama farklı |
| `snap_algo_version` | ❌ | ⚡ Önerilen | Yok |
| `grade` | ❌ (manifest) | ✅ GEREKLİ | rally_grade_cards.py'de hesaplanıyor |
| `engine_version` | ❌ (approved) | ✅ GEREKLİ | bundle manifest'te VAR |
| `data_fingerprint` | ❌ (approved) | ✅ GEREKLİ | bundle manifest'te VAR |
| `config_signature` | ❌ (approved) | ✅ GEREKLİ | bundle manifest'te VAR |

### 4.3) Kaybolma Noktaları

1. **SniperAnnotation → Approved Manifest:**
   - `entry_bar_offset` annotation'da var ama approved manifest'e aktarılmıyor
   - `grade` hesaplanıyor ama kayıt edilmiyor

2. **Bundle Manifest → Approved Manifest:**
   - `engine_version`, `data_fingerprint`, `config_signature` bundle'da var
   - Approved manifest'e kopyalanmıyor

3. **Auto-Snap:**
   - `snap_reason`, `snap_distance` hiçbir yerde hesaplanmıyor
   - `_find_nearest_levels()` sonucu saklanmıyor, sadece story'ye yazılıyor

---

## 5) Minimum Şema Önerileri (JSON)

### 5.1) NormalizeEvent v1
```json
{
  "version": "normalize_event_v1",
  "event_id": "rally_BTCUSDT_15m_20251221_1430",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  
  "raw_entry": {
    "bar_offset": 5,
    "timestamp": null
  },
  
  "normalized_entry": {
    "bar_offset": 4,
    "timestamp": "2025-12-21T14:30:00Z",
    "close_price": 98500.0
  },
  
  "snap": {
    "reason": "PIVOT_ALIGN",
    "distance_bars": 1,
    "confidence": 0.92,
    "algo_version": "snap_v1.0"
  },
  
  "target_level": {
    "nearest_support": 97800.0,
    "nearest_resistance": 99200.0
  }
}
```

### 5.2) ApprovedBundle v1
```json
{
  "version": "approved_bundle_v1",
  "candidate_id": "BTCUSDT_15m_1766258510",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  
  "approved_at": 1766258609,
  "status": "APPROVED",
  
  "entry": {
    "approved_entry_ts": "2025-12-21T14:30:00Z",
    "entry_bar_offset": 4,
    "entry_price": 98500.0
  },
  
  "exit": {
    "approved_exit_ts": "2025-12-21T16:15:00Z",
    "exit_bar_offset": 11,
    "exit_price": 99800.0
  },
  
  "snap": {
    "reason": "PIVOT_ALIGN",
    "distance_bars": 1,
    "confidence": 0.92,
    "algo_version": "snap_v1.0"
  },
  
  "grade": "SILVER",
  
  "trace": {
    "engine_version": "v4",
    "data_fingerprint": "7566d4ccd49cc73a0ea3dd48027f7abcf5b80b2...",
    "config_signature": "2cddf44a96ec24f52c565b7330b4ea7849044304..."
  },
  
  "params": {
    "entry": "breakout"
  }
}
```

---

## Sonuç: Dökümhane v1 İçin Kilit Kontratlar

1. **entry/exit timestamp hesaplaması:** bar_offset + pattern_ts → approved_entry_ts
2. **snap_reason mekanizması:** pivot/level/breakout alignment algılama
3. **trace propagation:** bundle → approved manifest'e kopyalama
4. **grade propagation:** rally_grade_cards → approved manifest'e yazma
