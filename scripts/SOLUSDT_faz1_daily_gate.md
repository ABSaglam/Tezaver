# 🚪 SOLUSDT Faz-1: Daily Gate Analizi
Tarih: 2026-01-31 17:50

> [!NOTE]
> Perspektif: 'Gün kapanışında ne oldu da ertesi gün tier oldu/olmadı?'

## 📊 Özet
| Metrik | Değer |
|---|---|
| Toplam Gün | 1095 |
| Tier Olan Günler | 118 (10.8%) |
| Tier Olmayan Günler | 977 (89.2%) |

## 🔬 Günlük Kapanış Metrikleri
| Metrik | Tier Günleri Ort | No-Tier Günleri Ort | Fark |
|---|---|---|---|
| d_adx | 39.24 | 35.84 | 🟢 +3.40 |
| d_atr_pct | 7.89 | 7.03 | 🟢 +0.85 |
| d_rsi | 55.65 | 51.78 | 🟢 +3.88 |
| d_vol_ratio | 1.28 | 0.98 | 🟢 +0.31 |
| d_above_ema21 | 0.62 | 0.52 | 🟢 +0.10 |
| d_above_ema50 | 0.64 | 0.57 | 🟢 +0.08 |
| d_ema21_above_50 | 0.64 | 0.59 | 🟢 +0.05 |
| d_daily_ret | 1.33 | 0.22 | 🟢 +1.12 |
| d_body_pct | 1.33 | 0.22 | 🟢 +1.11 |

## 🚪 Eleme Kuralları (Tier Koruma Öncelikli)
| Kural | Elenen Gün | Kaybedilen Tier | No-Tier Elenen | Tier Koruma |
|---|---|---|---|---|
| d_adx < 15 | 43 | 3 | 40 | ✅ 97.5% |
| d_vol_ratio < 0.5 | 139 | 10 | 129 | ⚠️ 91.5% |
| d_adx < 20 | 152 | 13 | 139 | ❌ 89.0% |
| d_rsi < 30 | 97 | 14 | 83 | ❌ 88.1% |
| d_vol_ratio < 0.6 | 230 | 16 | 214 | ❌ 86.4% |
| d_rsi < 35 | 163 | 22 | 141 | ❌ 81.4% |
| d_vol_ratio < 0.7 | 330 | 26 | 304 | ❌ 78.0% |
| d_rsi < 40 | 273 | 28 | 245 | ❌ 76.3% |
| d_adx < 25 | 282 | 29 | 253 | ❌ 75.4% |
| d_vol_ratio < 0.8 | 421 | 30 | 391 | ❌ 74.6% |

## 💡 Dahi Modu Önerisi
**En İyi Kural:** `d_adx < 15`

- 43 gün eleniyor
- Sadece 3 tier kaybediliyor
- 40 başarısız gün elemden geçiyor
- Tier Koruma: **97.5%**
