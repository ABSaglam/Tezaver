from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class TraceIds:
    engine_version: str
    data_fingerprint: str
    config_signature: str

def require_trace_ids(trace: TraceIds) -> None:
    """Validates that all trace IDs are present."""
    if not trace.engine_version:
        raise ValueError("TraceIds: engine_version is missing")
    if not trace.data_fingerprint:
        raise ValueError("TraceIds: data_fingerprint is missing")
    if not trace.config_signature:
        raise ValueError("TraceIds: config_signature is missing")
