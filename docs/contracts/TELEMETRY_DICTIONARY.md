# Telemetry Dictionary v1.0

> **Status**: FROZEN
> **Scope**: Sniper / WAR / LIVE / Cloud (ortak)

## Event Structure

Her telemetry event aşağıdaki zorunlu alanları içerir:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ts` | ISO8601 | ✓ | Event timestamp |
| `kind` | string | ✓ | Event type (from dictionary) |
| `run_id` | string | ✓ | Run identifier |
| `scope` | string | - | SNIPER/WAR/LIVE/CLOUD |

---

## Event Kinds (Frozen)

### Lifecycle Events

| Kind | Scope | Description |
|------|-------|-------------|
| `RUN_START` | ALL | Run başladı |
| `RUN_STOP` | ALL | Run durdu |
| `RUN_ERROR` | ALL | Run hatası |

### Bar Events

| Kind | Scope | Description |
|------|-------|-------------|
| `BAR_CLOSED` | ALL | Bar kapandı |
| `BAR_SKIP` | ALL | Bar atlandı |

### Position Events

| Kind | Scope | Description |
|------|-------|-------------|
| `POSITION_OPEN` | ALL | Pozisyon açıldı |
| `POSITION_CLOSE` | ALL | Pozisyon kapandı |

### WAR-Specific Events

| Kind | Scope | Description |
|------|-------|-------------|
| `WAR_START` | WAR | WAR run başladı |
| `WAR_END` | WAR | WAR run bitti |
| `WAR_EMPTY_PLAN` | WAR | Boş plan |
| `WAR_CELL_INFRA_ERROR` | WAR | Cell altyapı hatası |
| `CELL_START` | WAR | Cell işleme başladı |
| `CELL_END` | WAR | Cell işleme bitti |

### LIVE-Specific Events

| Kind | Scope | Description |
|------|-------|-------------|
| `LIVE_START` | LIVE | LIVE run başladı |
| `LIVE_STOP` | LIVE | LIVE run durdu |
| `LIVE_EMPTY_PLAN` | LIVE | Boş plan |
| `LIVE_ERROR` | LIVE | LIVE hatası |
| `LIVE_SAFE_MODE_ENABLED` | LIVE | Safe mode aktif |
| `CELL_SKIP_SAFE_MODE` | LIVE | Cell atlandı (safe mode) |

### Reconciliation Events

| Kind | Scope | Description |
|------|-------|-------------|
| `RECONCILE_STARTED` | LIVE/CLOUD | Reconciliation başladı |
| `RECONCILE_FINISHED` | LIVE/CLOUD | Reconciliation bitti |
| `RECONCILE_ERROR` | LIVE/CLOUD | Reconciliation hatası |
| `RECONCILE_RESULT` | CLOUD | Reconciliation sonucu |

### Cloud-Specific Events

| Kind | Scope | Description |
|------|-------|-------------|
| `CLOUD_START` | CLOUD | Cloud run başladı |
| `CLOUD_STOP` | CLOUD | Cloud run durdu |
| `CLOUD_ERROR` | CLOUD | Cloud hatası |
| `SAFE_MODE_ENABLED` | CLOUD | Safe mode aktif |
| `SKIP_SAFE_MODE` | CLOUD | Skip (safe mode) |
| `SIGNAL_STOP` | CLOUD | Signal ile durdurma |

### Candidate Status Events

| Kind | Scope | Description |
|------|-------|-------------|
| `CANDIDATE_STATUS_UPDATED` | WAR | Aday statüsü değişti |
| `CANDIDATE_STATUS_RETAINED` | WAR | Aday statüsü korundu |

### Incident Events

| Kind | Scope | Description |
|------|-------|-------------|
| `INCIDENT_CREATED` | ALL | Incident bundle oluştu |

---

## Backward Compatibility

- Yeni event kind eklenebilir (minor)
- Event kind kaldırılamaz (v1.x içinde)
- Zorunlu alan kaldırılamaz

---

*Frozen: 2025-12-21*
