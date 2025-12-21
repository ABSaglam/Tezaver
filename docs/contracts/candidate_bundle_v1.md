# CONTRACT — CandidateBundle v1

## Overview (Genel Bakış)
CandidateBundle, Tezaver Mac tarafından üretilen ve Matrix/Sniper sistemlerine girdi olarak sunulan ralli adayları paketidir.

---

## 1. Manifest (`manifest.json`)
Paketin meta verilerini ve veri parmak izini içerir.

| Alan Name | TR Açıklama | Tip | Zorunlu |
|-----------|-------------|-----|:-------:|
| `bundle_id` | Paketin benzersiz kimliği | String | Evet |
| `symbol` | İşlem çifti (örn: BTCUSDT) | String | Evet |
| `timeframe` | Baz zaman dilimi (örn: 15m) | String | Evet |
| `bundle_version` | Kontrat sürümü (1.0.0) | String | Evet |
| `build_ts` | Üretim zamanı (ISO) | String | Evet |
| `engine_min_version` | Gereken minimum Mac sürümü | String | Evet |
| `data_fingerprint` | Kaynak verilerin SHA256 birleşik hash'i | String | Evet |
| `config_signature` | Üretim konfigürasyonu hash'i | String | Evet |
| `story_count` | İçerdiği toplam RallyStory sayısı | Integer | Evet |
| `join_coverage` | Trigger eşleşme oranı (0.0 - 1.0) | Float | Evet (Sprint-2) |
| `sources` | Kullanılan kaynak dosyaların listesi | List[Str] | Evet |

---

## 2. Payload (`payload.json`)
Gerçek veri içeriğini barındırır.

| Alan Name | TR Açıklama | Tip |
|-----------|-------------|-----|
| `rally_stories_v1` | Üretilen ralli hikayeleri listesi | List[Object] |
| `compiled_stories_1h` | (Opsiyonel) 1 saatlik özet hikayeler | List[Object] |
| `compiled_stories_4h` | (Opsiyonel) 4 saatlik özet hikayeler | List[Object] |
| `config` | Üretimde kullanılan teknik parametreler | Object |
| `metadata` | Exporter ve üretim ortamı bilgileri | Object |
