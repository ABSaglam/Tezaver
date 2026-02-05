# Task Checklist - Project Harmony (V7)

## Phase 1: The Grand Harvest (Tüm Rallilerin Tespiti)
- [ ] **Create `scripts/v7_rally_harvester.py`**
    - [ ] Logic to scan all parquet files for rallies (>10% gain within 24h).
    - [ ] Store raw rally events with start/end timestamps and basic metrics.
- [ ] **Run Harvest**
    - [ ] Execute scan on all coin history (~800 days).
    - [ ] Output: `v7_raw_rallies.json`

## Phase 2: The Archetype Lab (Arketip Sınıflandırma)
- [ ] **Create `scripts/v7_archetype_classifier.py`**
    - [ ] Define strict logic for SUP, GRI, NIN, SUR, GUI.
    - [ ] Process `v7_raw_rallies.json` and tag each event.
- [ ] **Run Classification**
    - [ ] Output: `v7_classified_rallies.json`

## Phase 3: The Art Critic (Ahenk Analizi)
- [ ] **Create `scripts/v7_aesthetic_analyzer.py`**
    - [ ] For each archetype, extract "Soul" metrics:
        - [ ] RSI Angle & Rhythm
        - [ ] Volatility State (ATR, ADX)
        - [ ] Trend Context (EMA Ribbon)
        - [ ] Smoothness Score (Linear Regression R^2)
        - [ ] **Genius Oracle Upgrades** <!-- id: 10 -->
    - [/] Phase 1: Implement V-Eff Liquidity Defense <!-- id: 11 -->
    - [/] Phase 2: Implement Symbiotic Sector Intelligence <!-- id: 12 -->
    - [ ] Refresh 2026 Audit with Oracle Filters <!-- id: 13 -->
- [ ] **Analyze & Profile**
    - [ ] Generate `v7_archetype_dna_profiles.json` (The "Ideal" Soul for each type).

## Phase 4: The Harmony Detectors (Arama Motoru)
- [ ] **Create `scripts/v7_harmony_scanner.py`**
    - [ ] Implement detectors using the extracted DNA profiles.
    - [ ] Scan Jan-Feb 2026.
    - [ ] Verify if F Coin and others are caught *early*.

## Legacy Tasks (Completed)
- [x] **V6 DNA Sequencer & Jan Report** (Completed 2026-02-03)
