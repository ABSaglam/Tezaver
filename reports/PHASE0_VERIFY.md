# FAZ 0 — Doğrulama Raporu (PHASE0_VERIFY)

**Tarih:** 2025-12-22  
**Durum:** ✅ TAMAMLANDI — Faz 1'e geçilebilir

---

## MAC-0001: Output Roots & Manifest Varlığı

### Sonuç: ✅ VAR

| Kategori | Dosya | Durum |
|----------|-------|-------|
| Approved | `.tezaver_matrix/approved/BTCUSDT_15m_1766258510/manifest.json` | ✅ VAR |
| Candidate | `.tezaver_matrix/candidates/BTCUSDT_15m_1766258510/manifest.json` | ✅ VAR |
| Bundle | `out/matrix_candidates/BTCUSDT/15m/bundle_v1/manifest.json` | ✅ VAR |

### Örnek Manifest Snippet'leri

**Approved manifest:**
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

**Bundle manifest (trace bilgili):**
```json
{
  "bundle_id": "BTCUSDT_15m_bundle_20251221_074154",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "data_fingerprint": "7566d4ccd49cc73a...",
  "config_signature": "2cddf44a96ec24f5...",
  "story_count": 5,
  "engine_min_version": "0.1.0"
}
```

---

## MAC-0002: Envanter/Browser Mevcut mu?

### Sonuç: ✅ VAR

| UI Modül | Dosya | Boyut | Durum |
|----------|-------|-------|-------|
| Time Labs | `src/tezaver/ui/time_labs_tab.py` | 16 KB | ✅ VAR |
| Fast15 Lab | `src/tezaver/ui/fast15_lab_tab.py` | 16 KB | ✅ VAR |

### Fonksiyonlar
- `load_time_labs_rallies(symbol, timeframe)` — 1h/4h rally event'lerini yükler
- `render_rally_event_chart()` — Event chartı render eder
- Event listesi/tablo görünümü mevcut

### UI Erişim
- Streamlit sidebar → "Time Labs" veya "Fast15 Lab" sekmeleri
- Coin seçildikten sonra event listesi görüntülenir

---

## MAC-0003: Faz 0 Sonuç Özeti

### ✅ Var (Dokunma)
1. `.tezaver_matrix/approved/` — Approved manifest storage
2. `.tezaver_matrix/candidates/` — Candidate manifest storage
3. `out/matrix_candidates/` — Bundle manifest storage
4. `src/tezaver/ui/time_labs_tab.py` — Time Labs explorer
5. `src/tezaver/ui/fast15_lab_tab.py` — Fast15 explorer

### ⚠️ Eksik (Faz 1+ için eklenecek)
1. Entry/exit offset → timestamp dönüşümü (approved'a yazılmıyor)
2. snap_reason/snap_distance hesaplama
3. grade bilgisi approved manifest'te yok
4. trace (engine_version/data_fingerprint) approved'a kopyalanmıyor

---

## Faz 1'e Geçiş Onayı

> **Bu rapor doğrulama niteliğindedir. Kod değişikliği yapılmamıştır.**

| Kriter | Durum |
|--------|-------|
| Approved manifest var | ✅ |
| Candidate manifest var | ✅ |
| Bundle manifest var | ✅ |
| Envanter UI mevcut | ✅ |

**Sonuç: FAZ 1'e geçilebilir.**
