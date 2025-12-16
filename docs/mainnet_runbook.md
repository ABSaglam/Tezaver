# Mainnet Runbook v1

## Overview
This document describes the required steps to safely run REAL_MAINNET trading.

## Prerequisites Checklist

Before running REAL_MAINNET:

- [ ] API keys configured and tested on TESTNET
- [ ] Preflight checks passing (preflight decision = PASS)
- [ ] Risk limits properly configured
- [ ] Incident export enabled

---

## Step 1: Dry Run Verification

Run in DRY_RUN mode first to verify configuration:

```bash
# Verify with DRY_RUN (no real trades)
python -m tezaver.matrix.live.live_loop run \
  --exchange-mode DRY_RUN \
  --preflight \
  --symbols "BTCUSDT" \
  --tf 15m \
  --runtime 3600
```

Ensure:
- Preflight decision = PASS
- No errors in log
- Events emitting correctly

---

## Step 2: Testnet Verification

Run on REAL_TESTNET before mainnet:

```bash
python -m tezaver.matrix.live.live_loop run \
  --exchange-mode REAL_TESTNET \
  --exchange-enabled \
  --armed \
  --preflight \
  --preflight-enforce BLOCK \
  --auto-export-on-block \
  --symbols "BTCUSDT" \
  --tf 15m \
  --runtime 3600
```

---

## Step 3: Arm Mainnet

REAL_MAINNET requires ALL of these flags:

```bash
python -m tezaver.matrix.live.live_loop run \
  --exchange-mode REAL_MAINNET \
  --exchange-enabled \
  --armed \
  --mainnet-arm \
  --mainnet-ack "I_UNDERSTAND_REAL_MAINNET" \
  --mainnet-max-notional 1000 \
  --mainnet-allowlist "BTCUSDT,ETHUSDT" \
  --preflight \
  --preflight-enforce BLOCK \
  --auto-export-on-block \
  --symbols "BTCUSDT" \
  --tf 15m \
  --runtime 3600
```

### Required Flags for REAL_MAINNET

| Flag | Description |
|------|-------------|
| `--mainnet-arm` | Explicit mainnet arm confirmation |
| `--mainnet-ack "I_UNDERSTAND_REAL_MAINNET"` | Acknowledgment string (exact) |
| `--mainnet-max-notional <USD>` | Maximum total notional exposure |
| `--mainnet-allowlist "SYM1,SYM2"` | Comma-separated allowed symbols |
| `--preflight` | Preflight checks enabled |
| `--auto-export-on-block` | Auto-export incident bundles |

---

## Rollback / Incident Handling

If an incident occurs:
1. Kill the live loop process immediately
2. Check `data/incidents/` for exported bundles
3. Review `data/logs/live_events.ndjson` for BLOCK events
4. Cancel any open orders on exchange manually if needed

Incident bundles contain:
- Manifest with timestamp and reason
- Recent NDJSON events
- Config snapshot (secrets redacted)

---

## Monitoring

Key telemetry events to monitor:
- `MAINNET_GUARD_EVAL`: Guard check result
- `MAINNET_ARMED`: Mainnet successfully armed
- `RISK_LIMIT_BLOCK`: Risk limit exceeded
- `INCIDENT_BUNDLE_EXPORTED`: Bundle created

---

## Safety Reminders

> ⚠️ **WARNING**: REAL_MAINNET uses real funds. Always verify on TESTNET first.

> ⚠️ **WARNING**: Never share API keys or incident bundles publicly.

> ⚠️ **WARNING**: Set conservative `--mainnet-max-notional` limits.
