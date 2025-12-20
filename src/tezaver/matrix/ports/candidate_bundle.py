from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
import re

@dataclass
class Phase:
    name: str
    start_bar: int
    end_bar: int

@dataclass
class Anchors:
    entry_bar: int
    invalidation_bar: int

@dataclass
class RallyStory:
    phases: List[Phase]
    anchors: Anchors
    tags: List[str] = field(default_factory=list)
    signatures: Dict[str, Dict[str, float]] = field(default_factory=dict)

@dataclass
class CandidateBundle:
    symbol: str
    timeframe: str
    bundle_version: str
    build_ts: str
    story: RallyStory
    engine_min_version: str = ""
    data_fingerprint: str = ""
    config_signature: str = ""
    notes: str = ""

def sanitize_id_part(s: str) -> str:
    """Replaces unsafe characters with underscore."""
    return re.sub(r'[^a-zA-Z0-9]', '_', s)

def candidate_id(bundle: CandidateBundle) -> str:
    """Generates deterministic ID: {symbol}_{timeframe}_{bundle_version}_{build_ts}"""
    ts_clean = sanitize_id_part(bundle.build_ts)
    return f"{bundle.symbol}_{bundle.timeframe}_{bundle.bundle_version}_{ts_clean}"

def bundle_to_dict(bundle: CandidateBundle) -> dict:
    return asdict(bundle)

def bundle_from_dict(d: dict) -> CandidateBundle:
    try:
        story_data = d.get('story', {})
        phases_data = story_data.get('phases', [])
        anchors_data = story_data.get('anchors', {})
        
        phases = [Phase(**p) for p in phases_data]
        anchors = Anchors(**anchors_data)
        
        story = RallyStory(
            phases=phases,
            anchors=anchors,
            tags=story_data.get('tags', []),
            signatures=story_data.get('signatures', {})
        )
        
        return CandidateBundle(
            symbol=d['symbol'],
            timeframe=d['timeframe'],
            bundle_version=d['bundle_version'],
            build_ts=d['build_ts'],
            story=story,
            engine_min_version=d.get('engine_min_version', ""),
            data_fingerprint=d.get('data_fingerprint', ""),
            config_signature=d.get('config_signature', ""),
            notes=d.get('notes', "")
        )
    except Exception as e:
        raise ValueError(f"Invalid bundle dictionary: {e}")

def validate_bundle_dict(d: dict) -> List[str]:
    errors = []
    
    # Required top level fields
    required_fields = ['symbol', 'timeframe', 'bundle_version', 'build_ts', 'story']
    for f in required_fields:
        if f not in d or not d[f]:
            errors.append(f"Missing required field: {f}")
            
    if errors: return errors
    
    # Story struct
    story = d.get('story')
    if not isinstance(story, dict):
        errors.append("Field 'story' must be a dictionary")
        return errors
        
    phases = story.get('phases')
    if not phases or not isinstance(phases, list):
        errors.append("Story phases must be a non-empty list")
    else:
        for idx, p in enumerate(phases):
            if not isinstance(p, dict):
                errors.append(f"Phase {idx} is not a dictionary")
                continue
            s = p.get('start_bar')
            e = p.get('end_bar')
            if not isinstance(s, int) or not isinstance(e, int):
                errors.append(f"Phase {idx} bars must be integers")
            elif s > e:
                errors.append(f"Phase {idx} start_bar ({s}) > end_bar ({e})")
                
    anchors = story.get('anchors')
    if not anchors or not isinstance(anchors, dict):
        errors.append("Story anchors must be a dictionary")
    else:
        if not isinstance(anchors.get('entry_bar'), int):
            errors.append("Anchor entry_bar must be an int")
        if not isinstance(anchors.get('invalidation_bar'), int):
            errors.append("Anchor invalidation_bar must be an int")
            
    # Signatures validation (Optional)
    signatures = story.get('signatures')
    if signatures:
        if not isinstance(signatures, dict):
             errors.append("Story signatures must be a dictionary")
        else:
             from tezaver.matrix.core.story_signatures import check_signatures
             sig_errors = check_signatures(signatures)
             errors.extend(sig_errors)
             
    return errors
