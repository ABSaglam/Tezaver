# Matrix Safety Certificate - war_96defb7c4a64
**Verdict:** ✅ PASS
**Active Stage:** WAR
**Generated at:** 2025-12-21T18:26:35.323011

## Summary Counts
- 🟩 GREEN: 7
- 🟨 YELLOW: 3
- 🟥 RED: 0
- ⬜ GRAY/LOCKED: 8

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
- **MX-5230**: Rate Limit + Retry/Backoff (Evidence drift detected (missing proof))
- **MX-5240**: Resource Exhaustion Guardrails (Evidence drift detected (missing proof))

## Protocol Details
| MX | Protocol | Declared | Effective | Evidence OK | Missing |
|---|---|---|---|---|---|
| MX-5100 | Closed-bar Only Lock | GREEN | GREEN | ✅ |  |
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
| MX-5220 | Timebase Standard | GREEN | GREEN | ✅ |  |
| MX-5230 | Rate Limit + Retry/Backoff | GREEN | YELLOW | ❌ | artifacts:1, telemetry:4 |
| MX-5240 | Resource Exhaustion Guardrails | GREEN | YELLOW | ❌ | telemetry:1 |
| MX-5250 | Tamper-Evident Evidence | GREEN | GREEN | ✅ |  |
| MX-5260 | Safety Protocol Registry + UI | GREEN | GREEN | ✅ |  |
| MX-5270 | Safety Sweep + Safety Certificate | GREEN | GREEN | ✅ |  |