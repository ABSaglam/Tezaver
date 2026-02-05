# Implementation Plan - Coin-Specific DNA Optimization (Final V6 - Independent Triggers)

## Goal
Optimize **Trigger Conditions AND Filters** individually for each archetype per coin.

## Strategy: " The Independent DNA Sequencer"

### [NEW] `scripts/ozel_rsi_ema_dna_sequencer.py`

#### 1. Core Paradigm Shift: "Unique Triggers"
Instead of forcing "RSI-EMA > 60" as the universal door, we test different doors for different guests.

| Arketip | Mantıklı Tetik Adayları (Genler) | Mantık |
|:---|:---|:---|
| **💥 SUPERNOVA** | `RSI > 65`, `RSI > 70`, `RSI > 75` | Momentum zaten çok yüksektir, trene son vagonunda binilir. |
| **🩸 GUILLOTINE** | `RSI < 25`, `RSI < 30`, `RSI < 35` (Yukarı kesince) | "Ölü Kedi Sıçraması" veya dip dönüşü için aşırı satım tetiği. |
| **🔥 PHOENIX** | `RSI > 50`, `RSI > 55` | Zaten trend var, küçük bir düzeltme sonrası erken giriş. |
| **🪜 GRIND** | `RSI > 50`, `RSI > 60` | Orta seviye teyitler. |
| **🥷 NINJA/GRIND** | `RSI > 50` | Henüz kimse uyanmadan sessiz giriş. |

#### 2. Optimization Loop (Nested Grid Search)
For **Each Coin**:
  For **Each Archetype** (e.g., Supernova):
    Test **All Triggers** (e.g., RSI > 65, >70...)
      Test **All Filters** (Vol > 2x, Trend 4H...)
        -> Save Best Combo.

#### 3. Output: `dna_manifest_v6.json`
```json
{
  "PEPEUSDT": [
    {
      "name": "SUPERNOVA_EXIT",
      "target": "SUPERNOVA",
      "trigger_cond": "RSI_EMA > 70", 
      "filters": {"vol": 3.0}
    },
    {
      "name": "GUILLOTINE_CATCH",
      "target": "GUILLOTINE",
      "trigger_cond": "RSI_EMA < 30",
      "filters": {"trend": "OFF"}
    }
  ]
}
```

## Execution Steps
1.  **Data Harvest:** Extract **Continuous Indicators** (not just point triggers) to simulate any trigger.
2.  **Sequencing:** Run the massively parallel genetic search.
3.  **Reporting:** Generate Jan 2026 report where `SIG` column indicates the Trigger used (e.g., `RSI<30`).
