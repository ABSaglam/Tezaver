# Matrix Safety Inventory v1

**Date:** 2025-12-23
**Snapshot Version:** v1
**Status:** 🛡️ LIVE

---

## 1. Executive Summary

The Matrix Safety System is a comprehensive, registry-driven framework designed to ensure the integrity, safety, and correctness of algorithmic operations across SNIPER, WAR, and LIVE environments.

At its core is the **Safety Protocol Registry (MX-5260)**, a single-source-of-truth YAML file (`protocols/safety_protocol_registry.yaml`) that defines 18 distinct safety protocols. These protocols cover areas from market data integrity (MX-5210) to emergency kill switches (MX-5160).

The system enforces safety through a **"Sweep & Certificate"** mechanism (MX-5270). During every run (and specifically before release), a Safety Sweep is performed. This sweep:
1.  Reads the Registry.
2.  Checks for **Evidence Drift** (verifying that expected telemetry, artifacts, and tests exist).
3.  Combines the declared protocol status (GREEN/YELLOW/RED) with the evidence check.
4.  Generates a **Safety Certificate** (`safety_certificate_v1.json`) which serves as a tamper-evident seal of approval.

**Key Stats:**
- **Total Protocols:** 18
- **Active in WAR/LIVE:** ~12
- **Critical Blocking Protocols (RED):** Checked dynamically by `release_gate.py`.
- **Primary Enforcer:** `evaluate_release_gate` in `release_gate.py`.

---

## 2. "Source of Truth" Map

The flow of safety truth flows downwards from the Registry to the Release Gate.

```mermaid
graph TD
    REG[**Registry YAML**<br>safety_protocol_registry.yaml] -->|Loads Definitions| LOADER[**Loader Code**<br>safety_registry.py]
    LOADER -->|Checks Evidence| DRIFT[**Drift Checker**<br>check_evidence()]
    DRIFT -->|Sweep Logic| SWEEP[**Safety Sweep**<br>safety_sweep.py]
    SWEEP -->|Generates| CERT[**Safety Certificate**<br>safety_certificate_v1.json]
    CERT -->|Consumed By| GATE[**Release Gate**<br>release_gate.py]
    GATE -->|Displays On| UI[**Matrix UI**<br>Panel Health / Release Tab]
```

- **Definition:** `src/tezaver/matrix/protocols/safety_protocol_registry.yaml`
- **Logic:** `src/tezaver/matrix/protocols/safety_registry.py`
- **Enforcement:** `src/tezaver/matrix/core/release_gate.py`
- **Visibility:** `src/tezaver/matrix/ops/safety_certificate.py` (Markdown generator)

---

## 3. PROTOKOL TABLOSU (Inventory)

| ID | Ad | Tür | Active_in | Nerede Çalışır? (File/Logic) | Ne Üretir? (Telemetry) | UI Route | Block Cond. |
|---|---|---|---|---|---|---|---|
| **MX-5100** | Closed-bar Only Lock | Protocol | S, W, L | `lookahead_guard.py` | `LOOKAHEAD_GUARD_OK` | PANEL_HEALTH | **RED** |
| **MX-5110** | DataReport v1 + DATA_OK | Protocol | S, W, L | `release_gate.py` | - | PANEL_HEALTH | - |
| **MX-5120** | Exit & Real PnL v1 | Protocol | S, W, L | `audit.py` / `jury.py` | - | RUNS/REPORTS | - |
| **MX-5130** | Idempotency Shield | Protocol | - | *Not Implemented* | - | - | - |
| **MX-5140** | Restart Reconciliation | Protocol | - | `reconcile_bundles_v1.py` | `BOOT_RECONCILE_STARTED` | - | - |
| **MX-5150** | Telemetry Schema Unification | Protocol | S, W, L | `telemetry.py` | `WAR_START`, `CELL_START` | RUNS/DETAIL | - |
| **MX-5160** | Emergency Kill Switch | Protocol | - | *Not Implemented* | - | - | **SAFE_MODE** |
| **MX-5170** | Proof Bundle Packager | Protocol | - | *Not Implemented* | - | - | - |
| **MX-5180** | Trust Score / Noise Filter | Protocol | - | *Not Implemented* | - | - | - |
| **MX-5190** | Release Train Gates | Release Gate | - | `release_gate.py` | - | RELEASE TAB | **CRITICAL** |
| **MX-5200** | Order Lifecycle Prod-Grade | Protocol | - | `order_lifecycle.py` | - | - | - |
| **MX-5210** | Market Data Integrity | Protocol | - | `data_quality.py` (?) | - | - | - |
| **MX-5220** | Timebase Standard | Protocol | S, W, L | `timeframes.py` | - | PANEL_HEALTH | - |
| **MX-5230** | Rate Limit + Retry | Protocol | S, W, L | `binance_rest_client.py` | `API_CALL_RESULT` | PANEL_HEALTH | - |
| **MX-5240** | Resource Guardrails | Protocol | S, W, L | `ops_health.py` | `RESOURCE_GUARD_TRIPPED` | PANEL_HEALTH | - |
| **MX-5250** | Tamper-Evident Evidence | Protocol | S, W, L | `manifest.py` (Implied) | - | PANEL_HEALTH | - |
| **MX-5260** | Safety Protocol Registry | Protocol | S, W, L | `safety_registry.py` | - | OPS/PANEL_HEALTH | **RED** |
| **MX-5270** | Safety Sweep/Certificate | Protocol | S, W, L | `safety_sweep.py` | - | RELEASE TAB | **RED** |

---

## 4. "Sealed" (Stable) Protocols

These protocols have reached a stable state and are critical for system trust. **DO NOT MODIFY** without a dedicated RFC/Task.

1.  **MX-5100 (Closed-bar Only):** The foundation of simulation accuracy. Verified by `test_mx_5100_lookahead.py`.
2.  **MX-5260 (Safety Registry):** The master logic for all safety. Changes here break the entire evidence chain.
3.  **MX-5270 (Safety Sweep):** The mechanism that produces the certificate.
4.  **MX-5150 (Telemetry):** The data contract for all downstream logs.

---

## 5. Eksik / Belirsiz (Missing/Unclear)

The following protocols appear in the registry but lack full implementation or evidence:

*   **MX-5140 (Restart Reconciliation):** Logic exists in `src/tezaver/matrix/bootstrap/reconcile_bundles_v1.py` but Registry status is GRAY/Inactive. **Action:** Needs activation.
*   **MX-5160 (Kill Switch):** No dedicated implementation found. "Safe Mode" logic is mentioned in `release_gate.py` but explicit switch code is missing.
*   **MX-5130 (Idempotency):** Status GRAY. No specific idempotency layer found in `order_lifecycle.py`.
*   **MX-5170 (Proof Bundle):** Status GRAY. Likely a manual process currently.
