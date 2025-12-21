# Warnings Analysis Table - MX-5280

| # | MX | Name | Declared | Effective | Evidence OK | Missing | Class | Fix |
|---|---|---|---|---|---|---|---|---|
| 1 | MX-5120 | Exit & Real PnL v1 | GREEN | YELLOW | ❌ | telemetry:1 | W4 | Fix evidence list |
| 2 | MX-5130 | Idempotency Shield | GRAY | GRAY | ✅ | - | W6 | Remove WAR from active_in |
| 3 | MX-5140 | Restart Reconciliation | GRAY | GRAY | ✅ | - | W6 | Remove WAR from active_in |
| 4 | MX-5160 | Emergency Kill Switch | GRAY | GRAY | ✅ | - | W6 | Remove WAR from active_in |
| 5 | MX-5170 | Proof Bundle Packager | GRAY | GRAY | ✅ | - | W6 | Remove WAR from active_in |
| 6 | MX-5180 | Trust Score / Noise Filter | GRAY | GRAY | ✅ | - | W6 | Remove WAR from active_in |
| 7 | MX-5190 | Release Train Gates | GRAY | GRAY | ✅ | - | W6 | Remove WAR from active_in |
| 8 | MX-5200 | Order Lifecycle Prod-Grade | GRAY | GRAY | ✅ | - | W6 | Remove WAR from active_in |
| 9 | MX-5210 | Market Data Integrity | GRAY | GRAY | ✅ | - | W6 | Remove WAR from active_in |
| 10 | MX-5220 | Timebase Standard | GREEN | YELLOW | ❌ | artifacts:1, telemetry:1 | W4 | Fix evidence list |
| 11 | MX-5230 | Rate Limit + Retry/Backoff | GREEN | YELLOW | ❌ | artifacts:1, telemetry:4 | W4 | Remove WAR active_in (LIVE only) |
| 12 | MX-5240 | Resource Exhaustion | GREEN | YELLOW | ❌ | telemetry:1 | W4 | Remove WAR active_in (LIVE only) |
| 13 | MX-5250 | Tamper-Evident Evidence | GREEN | YELLOW | ❌ | telemetry:1 | W4 | Fix evidence list |
| 14 | MX-5260 | Safety Protocol Registry + UI | GRAY | GRAY | ❌ | tests:1 | W6 | Update to GREEN + fix test path |
| 15 | MX-5270 | Safety Sweep + Certificate | GREEN | YELLOW | ❌ | artifacts:2, telemetry:1 | W4 | Fix evidence list |

## Summary
- **W6 (GRAY)**: 9 protocols not implemented for WAR → Remove WAR from active_in
- **W4 (Evidence Drift)**: 6 protocols with missing evidence → Fix evidence lists or remove from WAR

## Fix Strategy
1. Remove WAR from active_in for GRAY protocols that don't apply to WAR
2. For GREEN with drift: empty telemetry/artifact lists (they're optional run reports)
3. Mark MX-5260 as GREEN with correct test path
