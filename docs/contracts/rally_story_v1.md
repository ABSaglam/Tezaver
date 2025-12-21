# CONTRACT — RallyStory v1

## Overview (Genel Bakış)
RallyStory, tek bir ralli olayının (event) tüm teknik, istatistiksel ve bağlamsal hikayesini içeren birincil veri objesidir.

---

## Veri Yapısı (Sections)

### 1. Core Metadata
| Alan | TR Açıklama | Zorunlu |
|------|-------------|:-------:|
| `version` | Obje sürümü (1.0.0, 1.1.0 vb) | Evet |
| `story_id` | Deterministik ID ({symbol}_{tf}_{YYMMDD_HHMM}) | Evet |
| `symbol` | İşlem çifti | Evet |

### 2. Context (Bağlam)
| Alan | TR Açıklama |
|------|-------------|
| `timeframe` | Event'in gerçekleştiği zaman dilimi |
| `regime` | Mevcut piyasa rejimi (chaotic, trendy vb) |
| `shock_risk` | Volatilite şok olasılığı |
| `trendiness_score` | Trendleşme gücü skoru |

### 3. Entry (Giriş)
| Alan | TR Açıklama |
|------|-------------|
| `event_time_utc` | Olayın UTC zamanı |
| `entry_price` | Giriş fiyatı (Mac History Close) |
| `trigger` | Tetikleyici adı (örn: macd_bull_cross) |
| `trigger_source` | Tetikleyicinin hangi dosyadan/paraman geldiği |
| `trust_score` | Tetikleyicinin tarihsel güven skoru |

### 4. Levels (Seviyeler)
| Alan | TR Açıklama |
|------|-------------|
| `nearest_support` | En yakın destek seviyesi |
| `support_strength`| Destek seviyesinin gücü |
| `nearest_resistance`| En yakın direnç seviyesi |

### 5. Risk (Risk Yönetimi)
| Alan | TR Açıklama |
|------|-------------|
| `stop_loss_price` | Hesaplanan Stop Loss fiyatı |
| `stop_loss_pct` | Girişe oranla SL yüzdesi |
| `atr_pct_15m` | Olay anındaki 15m ATR yüzdesi |
| `sl_k_multiplier` | SL hesaplamada kullanılan k çarpanı |

### 6. Evidence (Kanıt)
| Alan | TR Açıklama |
|------|-------------|
| `source_event` | Orijinal Fast15 event özeti |
| `event_row_hash` | Ham verinin bütünlük hash'i |
| `bar_window` | İncelenen data penceresi (start/end) |
