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
    """
    PNL-1100: Canonical Manifest Adapter with flexible schema support.
    Handles:
    - tf vs timeframe
    - nested vs flat metrics/fingerprints
    - Missing optional fields
    """
    # Normalize tf/timeframe
    tf = d.get('tf') or d.get('timeframe') or 'UNKNOWN'
    
    # Normalize version
    version = d.get('version') or d.get('bundle_version') or '1.1.0'
    
    # Normalize metrics (nested vs flat)
    if 'metrics' in d and isinstance(d['metrics'], dict):
        m = d['metrics']
        m_src_raw = m.get('trigger_resolve_rate_by_source', {})
        m_src = MetricSourceBreakdown(
            join=m_src_raw.get('join', 0.0),
            join_1h_neighbor=m_src_raw.get('join_1h_neighbor', 0.0),
            derived_15m=m_src_raw.get('derived_15m', 0.0),
            fallback=m_src_raw.get('fallback', 0.0),
            unresolved=m_src_raw.get('unresolved', 0.0)
        )
        metrics = BundleMetrics(
            trigger_resolve_rate=m.get('trigger_resolve_rate', 0.0),
            trigger_resolve_rate_by_source=m_src,
            total_count=m.get('total_count', 0),
            resolved_count=m.get('resolved_count', 0),
            unresolved_count=m.get('unresolved_count', 0),
            join_coverage=m.get('join_coverage', 0.0),
            unresolved_event_times=m.get('unresolved_event_times', [])
        )
    else:
        # Flat metrics (legacy)
        metrics = BundleMetrics(
            trigger_resolve_rate=d.get('trigger_resolve_rate', 0.0),
            trigger_resolve_rate_by_source=MetricSourceBreakdown(),
            total_count=d.get('story_count', 0),
            resolved_count=d.get('story_count', 0),
            unresolved_count=0,
            join_coverage=d.get('join_coverage', 0.0),
            unresolved_event_times=[]
        )
    
    # Normalize fingerprints (nested vs flat)
    if 'fingerprints' in d and isinstance(d['fingerprints'], dict):
        fps = BundleFingerprints(
            data_fingerprint=d['fingerprints'].get('data_fingerprint', 'N/A'),
            config_signature=d['fingerprints'].get('config_signature', 'N/A')
        )
    else:
        # Flat fingerprints (legacy)
        fps = BundleFingerprints(
            data_fingerprint=d.get('data_fingerprint', 'N/A'),
            config_signature=d.get('config_signature', 'N/A')
        )
    
    return ManifestV1(
        version=version,
        repo_version=d.get('repo_version', 'N/A'),
        bundle_id=d.get('bundle_id', 'unknown'),
        symbol=d.get('symbol', 'UNKNOWN'),
        tf=tf,
        export_time_utc=d.get('export_time_utc', d.get('build_ts', '')),
        metrics=metrics,
        fingerprints=fps,
        status=d.get('status', 'unknown')
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
    """
    PNL-1100: Canonical Payload Adapter with flexible schema support.
    """
    # Support 'stories', 'rally_stories_v1', or 'rally_stories'
    stories_key = None
    for key in ['stories', 'rally_stories_v1', 'rally_stories']:
        if key in d:
            stories_key = key
            break
    
    if not stories_key:
        raise ValueError("payload missing 'stories' or 'rally_stories_v1'")
    
    raw_stories = d.get(stories_key, [])
    
    stories = []
    for s in raw_stories:
        # Support optional pre_pattern mapping
        pp_dict = s.get('pre_pattern')
        pp = None
        if pp_dict:
            try:
                pp = PrePattern(
                    rhythm=Rhythm(**pp_dict.get('rhythm', {'summary_tr': '', 'phase_sequence': [], 'tempo': {}})),
                    spirit=Spirit(**pp_dict.get('spirit', {'summary_tr': '', 'tags': [], 'regime_hint_tr': ''})),
                    meaning=Meaning(**pp_dict.get('meaning', {'summary_tr': '', 'thesis_tr': '', 'invalidation_tr': ''}))
                )
            except:
                pp = None
        
        # PNL-1100: Flexible story fields with defaults
        story = RallyStoryV1(
            version=s.get('version', '1.0.0'),
            story_id=s.get('story_id', 'unknown'),
            symbol=s.get('symbol', 'UNKNOWN'),
            context=s.get('context', {}),
            entry=s.get('entry', {}),
            target=s.get('target', {}),
            risk=s.get('risk', {}),
            family=s.get('family', {}),
            quality=s.get('quality', {}),
            evidence=s.get('evidence', {}),
            phases=s.get('phases', []),
            pre_pattern=pp
        )
        stories.append(story)
    
    # PNL-1100: compiled_stories is optional
    return PayloadV1(stories=stories, compiled_stories=d.get('compiled_stories', {}))

def generate_candidate_id(manifest: ManifestV1) -> str:
    """MXI-1000: Deterministic candidate_id based on bundle info and fingerprints."""
    raw = f"{manifest.bundle_id}_{manifest.fingerprints.data_fingerprint}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
