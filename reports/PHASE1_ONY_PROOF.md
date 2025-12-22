# FAZ 1 — ONY v1 Kanıt Paketi (PHASE1_ONY_PROOF)

**Tarih:** 2025-12-22  
**Durum:** ✅ TAMAMLANDI

---

## Değişen Dosyalar

| Aksiyon | Dosya |
|---------|-------|
| **YENİ** | `src/tezaver/ui/ony_tab.py` |
| **MODIFY** | `src/tezaver/ui/main_panel.py` (+3 satır) |
| **YENİ** | `tests/ui/test_ony_storage.py` |

### Git Diff Summary
```
src/tezaver/ui/main_panel.py | 3 +++   (import + nav + routing)
src/tezaver/ui/ony_tab.py    | NEW     (340 satır)
tests/ui/test_ony_storage.py | NEW     (110 satır)
```

---

## Nasıl Çalıştırılır?

```bash
# Streamlit UI
cd /Users/alisaglam/TezaverMac
source venv/bin/activate
streamlit run src/tezaver/ui/main_panel.py

# Test
pytest tests/ui/test_ony_storage.py -v
```

---

## Demo Senaryosu

### Adımlar
1. **Streamlit aç** → Sidebar'da **"🎯 ONY Stüdyo"** butonuna tıkla
2. **Coin seç:** BTCUSDT, **Timeframe:** 15m
3. **Event seç:** Dropdown'dan bir event seç
4. **Entry ayarla:** `entry_bar_offset = 10`
5. **Exit etkinleştir:** ✅ checkbox → `exit_bar_offset = 40`
6. **💾 Kaydet** butonuna tıkla
7. **✅ Onayla** butonuna tıkla
8. **📋 Kuyruk** sekmesine geç → APPROVED listesinde gör

---

## Test Sonuçları

```
tests/ui/test_ony_storage.py::test_sniper_annotation_upsert_roundtrip PASSED
tests/ui/test_ony_storage.py::test_sniper_annotation_list_by_status PASSED
tests/ui/test_ony_storage.py::test_sniper_annotation_json_roundtrip PASSED

================================== 3 passed ==================================
```

---

## Kanıt: JSON Kayıt Örneği

**Dosya:** `data/sniper/BTCUSDT/15m/sniper_annotations_v1.json`

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "event_id": "3",
  "entry_bar_offset": 3,
  "note": "",
  "created_at": "2024-12-12T05:05:50.584217",
  "exit_bar_offset": 39,
  "tags": [],
  "status": "APPROVED",
  "label": "GOOD"
}
```

---

## ONY Tab Fonksiyonları

| Fonksiyon | Açıklama |
|-----------|----------|
| `render_ony_studio()` | Event seçimi, entry/exit offset, grafik, kaydet, onayla |
| `render_ony_queue()` | PENDING/APPROVED/REJECTED listesi |
| `render_ony_page()` | Ana giriş noktası (tabs) |

---

## Kabul Kriterleri Kontrolü

| MAC-ID | Kriter | Durum |
|--------|--------|-------|
| MAC-1001 | Grafik 4 panel çiziliyor | ✅ `render_sniper_studio_chart` |
| MAC-1001 | Entry/Exit marker görünüyor | ✅ cyan/red markers |
| MAC-1002 | entry_bar_offset değişince marker yeri değişiyor | ✅ |
| MAC-1002 | exit_bar_offset opsiyonel çalışıyor | ✅ checkbox |
| MAC-1003 | `sniper_annotations_v1.json` dosyasına yazıyor | ✅ |
| MAC-1004 | status PENDING→APPROVED akıyor | ✅ |

---

## Not

Bu fazda **auto-snap** ve **QC** yok. Bunlar Faz 2 ve Faz 3 kapsamında eklenecek.
