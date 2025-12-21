# CandidateBundle Contract v1.1

> **Status**: FROZEN (v1.1.x)
> **Breaking Changes**: NONE ALLOWED in v1.x

## Bundle Structure

```
bundle_v1_{id}/
├── manifest.json      # Required
├── config.yaml        # Required
├── data/
│   └── history_{tf}.parquet
├── rally_story.json   # Optional (v1.1+)
└── pre_pattern.json   # Optional (v1.1+)
```

## manifest.json Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bundle_version` | string | ✓ | "1.1.x" |
| `bundle_id` | string | ✓ | Unique ID |
| `symbol` | string | ✓ | Trading pair |
| `tf` | string | ✓ | Timeframe |
| `created_at` | ISO8601 | ✓ | Creation time |
| `status` | string | ✓ | NEW/APPROVED_*/REJECTED_* |
| `fingerprints` | object | ✓ | Hash values |
| `pre_pattern` | object | - | Optional ritual values |

## Status Values (Frozen)

```
NEW → APPROVED_FOR_WAR → APPROVED_FOR_LIVE
         ↓                     ↓
    NEEDS_PATCH           REJECTED_BY_WAR
         ↓
    REJECTED_BY_WAR
```

## pre_pattern Schema (Optional)

| Field | Type | Description |
|-------|------|-------------|
| `ritim` | object | Rhythm pattern |
| `ruh` | object | Spirit pattern |
| `mana` | object | Mana pattern |

## Backward Compatibility

- v1.0 bundles: `bundle_version` → `version` fallback
- New fields MUST be optional
- Removal of fields: FORBIDDEN in v1.x

## Importer Compatibility

| Importer Version | Bundle v1.0 | Bundle v1.1 |
|------------------|-------------|-------------|
| ≥1.0.0 | ✓ | ✓ |

---

*Frozen: 2025-12-21*
