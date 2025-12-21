# Matrix Safety Certificate - war_a3b80f5ce1c1
**Verdict:** ❌ FAIL
**Active Stage:** WAR
**Generated at:** 2025-12-21T18:06:31.832912

## Summary Counts
- 🟩 GREEN: 2
- 🟨 YELLOW: 6
- 🟥 RED: 1
- ⬜ GRAY/LOCKED: 9

## ❌ Blockers
- **MX-5100**: Closed-bar Only Lock (Safety protocol MX-5100 is RED)

## ⚠️ Warnings
- **MX-5120**: Exit & Real PnL v1 (SL/TP/TimeStop + PnL sanity) (Evidence drift detected (missing proof))
- **MX-5130**: Idempotency / Duplicate-order Shield (Safety protocol MX-5130 is GRAY)
- **MX-5140**: Restart Reconciliation (Safety protocol MX-5140 is GRAY)
- **MX-5160**: Emergency Kill Switch + Safe Mode (Safety protocol MX-5160 is GRAY)
- **MX-5170**: Proof Bundle Packager (Safety protocol MX-5170 is GRAY)
- **MX-5180**: Trust Score / Noise Filter (Safety protocol MX-5180 is GRAY)
- **MX-5190**: Release Train Gates (Safety protocol MX-5190 is GRAY)
- **MX-5200**: Order Lifecycle Prod-Grade v1 (Safety protocol MX-5200 is GRAY)
- **MX-5210**: Market Data Integrity & Anti-Lookahead (Safety protocol MX-5210 is GRAY)
- **MX-5220**: Timebase Standard (Evidence drift detected (missing proof))
- **MX-5230**: Rate Limit + Retry/Backoff (Evidence drift detected (missing proof))
- **MX-5240**: Resource Exhaustion Guardrails (Evidence drift detected (missing proof))
- **MX-5250**: Tamper-Evident Evidence (Evidence drift detected (missing proof))
- **MX-5260**: Safety Protocol Registry + UI (Safety protocol MX-5260 is GRAY)
- **MX-5270**: Safety Sweep + Safety Certificate (Evidence drift detected (missing proof))

## Protocol Details
| MX | Protocol | Declared | Effective | Evidence OK | Missing |
|---|---|---|---|---|---|
| MX-5100 | Closed-bar Only Lock | RED | RED | ❌ | tests:3, telemetry:1 |
| MX-5110 | DataReport v1 + DATA_OK run-scoped fix | GREEN | GREEN | ✅ |  |
| MX-5120 | Exit & Real PnL v1 (SL/TP/TimeStop + PnL sanity) | GREEN | YELLOW | ❌ | telemetry:1 |
| MX-5130 | Idempotency / Duplicate-order Shield | GRAY | GRAY | ✅ |  |
| MX-5140 | Restart Reconciliation | GRAY | GRAY | ✅ |  |
| MX-5150 | Telemetry Schema Unification | GREEN | GREEN | ✅ |  |
| MX-5160 | Emergency Kill Switch + Safe Mode | GRAY | GRAY | ✅ |  |
| MX-5170 | Proof Bundle Packager | GRAY | GRAY | ✅ |  |
| MX-5180 | Trust Score / Noise Filter | GRAY | GRAY | ✅ |  |
| MX-5190 | Release Train Gates | GRAY | GRAY | ✅ |  |
| MX-5200 | Order Lifecycle Prod-Grade v1 | GRAY | GRAY | ✅ |  |
| MX-5210 | Market Data Integrity & Anti-Lookahead | GRAY | GRAY | ✅ |  |
| MX-5220 | Timebase Standard | GREEN | YELLOW | ❌ | artifacts:1, telemetry:1 |
| MX-5230 | Rate Limit + Retry/Backoff | GREEN | YELLOW | ❌ | artifacts:1, telemetry:4 |
| MX-5240 | Resource Exhaustion Guardrails | GREEN | YELLOW | ❌ | telemetry:1 |
| MX-5250 | Tamper-Evident Evidence | GREEN | YELLOW | ❌ | telemetry:1 |
| MX-5260 | Safety Protocol Registry + UI | GRAY | GRAY | ❌ | tests:1 |
| MX-5270 | Safety Sweep + Safety Certificate | GREEN | YELLOW | ❌ | artifacts:2, telemetry:1 |