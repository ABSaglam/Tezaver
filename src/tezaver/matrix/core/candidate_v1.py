from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import hashlib
import json

@dataclass
class MetricSourceBreakdown:
    join: float = 0.0
    join_1h_neighbor: float = 0.0
    derived_15m: float = 0.0
    fallback: float = 0.0
    unresolved: float = 0.0

@dataclass
class BundleMetrics:
    trigger_resolve_rate: float
    trigger_resolve_rate_by_source: MetricSourceBreakdown
    total_count: int
    resolved_count: int
    unresolved_count: int
    join_coverage: float
    unresolved_event_times: List[str] = field(default_factory=list)

@dataclass
class BundleFingerprints:
    data_fingerprint: str
    config_signature: str

@dataclass
class ManifestV1:
    version: str # v1.1.2
    repo_version: str
    bundle_id: str
    symbol: str
    tf: str
    export_time_utc: str
    metrics: BundleMetrics
    fingerprints: BundleFingerprints
    status: str

    def __post_init__(self):
        # MXI-1010: Support only 1.1.x
        if not self.version.startswith("1.1."):
            raise ValueError(f"Unsupported bundle version: {self.version}. Must be 1.1.x")

def manifest_from_dict(d: dict) -> ManifestV1:
    m = d['metrics']
    m_src = m['trigger_resolve_rate_by_source']
    metrics = BundleMetrics(
        trigger_resolve_rate=m['trigger_resolve_rate'],
        trigger_resolve_rate_by_source=MetricSourceBreakdown(**m_src),
        total_count=m['total_count'],
        resolved_count=m['resolved_count'],
        unresolved_count=m['unresolved_count'],
        join_coverage=m['join_coverage'],
        unresolved_event_times=m.get('unresolved_event_times', [])
    )
    fps = BundleFingerprints(**d['fingerprints'])
    return ManifestV1(
        version=d['version'],
        repo_version=d['repo_version'],
        bundle_id=d['bundle_id'],
        symbol=d['symbol'],
        tf=d['tf'],
        export_time_utc=d['export_time_utc'],
        metrics=metrics,
        fingerprints=fps,
        status=d['status']
    )

@dataclass
class Rhythm:
    summary_tr: str
    phase_sequence: List[str]
    tempo: Dict[str, Any]

@dataclass
class Spirit:
    summary_tr: str
    tags: List[str]
    regime_hint_tr: str

@dataclass
class Meaning:
    summary_tr: str
    thesis_tr: str
    invalidation_tr: str

@dataclass
class PrePattern:
    rhythm: Rhythm
    spirit: Spirit
    meaning: Meaning

@dataclass
class RallyStoryV1:
    version: str
    story_id: str
    symbol: str
    context: Dict[str, Any]
    entry: Dict[str, Any]
    target: Dict[str, Any]
    risk: Dict[str, Any]
    family: Dict[str, Any]
    quality: Dict[str, Any]
    evidence: Dict[str, Any]
    phases: List[Any] = field(default_factory=list)
    pre_pattern: Optional[PrePattern] = None # New Semantic Layer

@dataclass
class PayloadV1:
    stories: List[RallyStoryV1]
    compiled_stories: Dict[str, Any]

def payload_from_dict(d: dict) -> PayloadV1:
    stories = []
    for s in d['stories']:
        # Support optional pre_pattern mapping
        pp_dict = s.get('pre_pattern')
        pp = None
        if pp_dict:
            pp = PrePattern(
                rhythm=Rhythm(**pp_dict['rhythm']),
                spirit=Spirit(**pp_dict['spirit']),
                meaning=Meaning(**pp_dict['meaning'])
            )
        
        # Instantiate RallyStoryV1 manually to handle pp
        story = RallyStoryV1(
            version=s['version'],
            story_id=s['story_id'],
            symbol=s['symbol'],
            context=s['context'],
            entry=s['entry'],
            target=s['target'],
            risk=s['risk'],
            family=s['family'],
            quality=s['quality'],
            evidence=s['evidence'],
            phases=s.get('phases', []),
            pre_pattern=pp
        )
        stories.append(story)
    return PayloadV1(stories=stories, compiled_stories=d['compiled_stories'])

def generate_candidate_id(manifest: ManifestV1) -> str:
    """MXI-1000: Deterministic candidate_id based on bundle info and fingerprints."""
    raw = f"{manifest.bundle_id}_{manifest.fingerprints.data_fingerprint}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
