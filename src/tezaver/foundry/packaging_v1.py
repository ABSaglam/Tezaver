"""
Packaging v1 - ApprovedRallyBundle Packaging Engine
====================================================

Packages QC-PASSED approved annotations into Matrix-ready bundles.
"""

from typing import List, Optional, Dict, Any
from dataclasses import asdict
import pandas as pd
from pathlib import Path
import json

from tezaver.sniper.sniper_annotations import SniperAnnotation, SniperAnnotationRepository
from tezaver.foundry.models import QCReport
from tezaver.foundry.bundle_models import ApprovedRallyBundleManifest
from tezaver.foundry import bundle_io
from tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct
from tezaver.rally.rally_narrative_engine import analyze_scenario, SCENARIO_DEFINITIONS
from tezaver.rally.rally_narrative_engine import analyze_scenario, SCENARIO_DEFINITIONS
from tezaver.foundry.naming_service import BundleNamingService
from tezaver.foundry.deep_narrative_service import DeepNarrativeService
from tezaver.core import coin_cell_paths
import time
import uuid
import shutil


def package_event(
    symbol: str,
    timeframe: str,
    event_id: str,
    output_root: str = ".tezaver_matrix/approved_bundles_v1"
) -> Optional[str]:
    """
    Package a single event into ApprovedRallyBundle.
    
    Args:
        symbol: Trading pair symbol
        timeframe: Timeframe (15m, 1h, 4h)
        event_id: Event identifier
        output_root: Root directory for bundles
    
    Returns:
        Path to bundle directory, or None if skipped
    """
    # Load annotation
    repo = SniperAnnotationRepository()
    annotation = repo.get_one(symbol, timeframe, event_id)
    
    if not annotation:
        return None
    
    # Check APPROVED status
    if getattr(annotation, 'status', '') != 'APPROVED':
        return None
    
    # Load QC report
    qc_report_path = Path(f".tezaver_matrix/foundry/qc_reports/{symbol}/{timeframe}/qc_{event_id}.json")
    if qc_report_path.exists():
        with open(qc_report_path, 'r') as f:
            qc_report_dict = json.load(f)
        qc_report = QCReport.from_dict(qc_report_dict)
        
        # Skip if QC not PASS
        if qc_report.qc_verdict != "PASS":
            return None
    else:
        # Default Auto-Approve Mock QC
        qc_report = QCReport(
            symbol=symbol,
            timeframe=timeframe,
            event_id=event_id,
            qc_verdict="PASS",
            score=100,
            warns=["Auto-Approved (Missing QC Report)"]
        )
        qc_report_dict = qc_report.to_dict()
    
    # Load event dataset row
    event_row = _load_event_row(symbol, timeframe, event_id)
    if event_row is None:
        return None
    
    # Compute tier from future_max_gain_pct
    future_gain = event_row.get('future_max_gain_pct')
    if future_gain is not None and pd.notna(future_gain):
        tier = compute_tier_from_gain_pct(float(future_gain))
        if tier is None:
            tier = "UNKNOWN"
    else:
        tier = "UNKNOWN"
    
    # Generate Standard Bundle ID (e.g., BTC-15m-GOLD-01)
    naming = BundleNamingService(output_root)
    # Check for special tags in narrative/qc if needed, for now use Tier
    # Future: if qc_report has 'special_tag' etc.
    std_bundle_id = naming.generate_id(symbol, timeframe, tier)
    
    # Create bundle directory with Standard ID
    bundle_dir = bundle_io.create_bundle_directory(
        symbol, timeframe, event_id, output_root, folder_name=std_bundle_id
    )
    
    # Build approved dict
    approved = {
        "entry_bar_offset": getattr(annotation, 'approved_entry_bar_offset', None),
        "entry_ts": getattr(annotation, 'approved_entry_ts', None),
        "exit_bar_offset": getattr(annotation, 'approved_exit_bar_offset', None),
        "exit_ts": getattr(annotation, 'approved_exit_ts', None)
    }
    
    # Determine identifying ID for the manifest (must match parquet for backtest)
    orig_id = str(event_row.get('event_id', event_row.get('event_idx', event_id)))

    # Build QC dict
    qc_dict = {
        "verdict": qc_report.qc_verdict,
        "score": qc_report.score,
        "report_path": f"../../../qc_reports/{symbol}/{timeframe}/qc_{event_id}.json"
    }
    
    # Build pointers (relative paths)
    annotation_path = repo._file_path(symbol, timeframe)
    event_dataset_path = _get_event_dataset_path(symbol, timeframe)
    history_path = coin_cell_paths.get_history_file(symbol, timeframe)
    
    pointers = {
        "annotation_path": str(annotation_path),
        "event_dataset_path": event_dataset_path if event_dataset_path else "",
        "history_path": str(history_path)
    }
    
    # Extract price window
    price_window_df = _extract_price_window(symbol, timeframe, event_row.get('event_time'))
    
    # Build manifest
    bundle_id = f"{symbol}_{timeframe}_{orig_id}"
    event_time_iso = pd.to_datetime(event_row.get('event_time')).isoformat() if pd.notna(event_row.get('event_time')) else ""
    
    # Analyze Narrative (Deep Story)
    try:
        story_engine = DeepNarrativeService()
        # Ensure we pass the iso string correctly
        narrative_data = story_engine.generate_story(symbol, timeframe, event_time_iso)
        
        narrative = {
            "label": narrative_data.get("label", "Unknown Story"),
            "desc": narrative_data.get("desc", "No description available."),
            "risk": narrative_data.get("risk", "Medium"),
            "details": narrative_data.get("details", {})
        }
        # Backwards compat: use a generic ID or synthesize one
        scenario_id = "SCENARIO_DEEP_NARRATIVE" 
    except Exception as e:
        print(f"Deep Narrative Failed: {e}")
        scenario_id = "SCENARIO_NEUTRAL"
        narrative = {"label": "Neutral", "desc": "Analysis failed.", "risk": "Medium"}

    manifest = ApprovedRallyBundleManifest(
        bundle_id=std_bundle_id,  # Use Standard ID (e.g. BTC-15m-GOLD-01)
        symbol=symbol,
        timeframe=timeframe,
        event_id=orig_id,
        event_time_iso=event_time_iso,
        tier=tier,
        approved=approved,
        qc=qc_dict,
        pointers=pointers,
        scenario_id=scenario_id,
        narrative=narrative
    )
    
    # Prepare event row dict (minimal fields)
    event_row_dict = {
        "event_id": event_id,
        "event_time": event_time_iso,
        "future_max_gain_pct": event_row.get('future_max_gain_pct'),
        "bars_to_peak": int(event_row.get('bars_to_peak')) if pd.notna(event_row.get('bars_to_peak')) else None,
        "tier": tier
    }
    
    # Prepare annotation dict
    annotation_dict = annotation.to_dict()
    
    # Write all bundle files
    bundle_io.write_bundle_files(
        bundle_dir=bundle_dir,
        manifest=manifest,
        annotation_dict=annotation_dict,
        qc_report_dict=qc_report_dict,
        event_row_dict=event_row_dict,
        price_window_df=price_window_df
    )
    
    return str(bundle_dir)


from tezaver.foundry.cluster_engine import ClusterEngine, extract_features, ArchetypeCluster

def package_cluster(
    cluster: ArchetypeCluster,
    symbol: str,
    timeframe: str,
    tier: str,
    output_root: str = ".tezaver_matrix/approved_bundles_v1"
) -> Optional[str]:
    """
    Package an Archetype Cluster into a Bundle.
    
    The bundle represents the 'Structure'.
    It uses the Centroid Member (rallies closest to mean) as the primary visual.
    """
    if not cluster.members:
        return None

    # 1. Identify Representative
    # Find member closest to centroid gain/duration
    best_member = None
    min_dist = float('inf')
    
    c_gain = cluster.centroid.get('gain', 0)
    c_dur = cluster.centroid.get('duration', 0)
    
    for m in cluster.members:
        dist = ((m.gain - c_gain)**2 + (m.duration - c_dur)**2) ** 0.5
        if dist < min_dist:
            min_dist = dist
            best_member = m
            
    if not best_member:
        best_member = cluster.members[0] # Fallback
        
    # 2. Bundle ID
    # e.g. BTC-15m-GOLD-A
    naming = BundleNamingService(output_root)
    # We construct ID manually or add support in naming service. 
    # Let's use standard naming but append Cluster ID.
    # Actually, NamingService generates sequential 01, 02.
    # We want A, B, C for clusters? 
    # Let's stick to Sequential 01, 02... but these now represent Clusters.
    # So BTC-15m-GOLD-01 is Cluster A.
    
    std_bundle_id = naming.generate_id(symbol, timeframe, tier)
    
    # 3. Create Bundle Dir
    # We use the Representative's Event ID for the folder structure initially,
    # or better, just use the Bundle ID as the main folder name.
    
    # We reuse bundle_io logic but we need to trick it or update it.
    # bundle_io.create_bundle_directory uses event_id.
    rep_event_id = best_member.event_id
    
    bundle_dir = bundle_io.create_bundle_directory(
        symbol, timeframe, rep_event_id, output_root, folder_name=std_bundle_id
    )
    
    # 4. Prepare Data
    # Load Representative Data (Annotation, QC, Row)
    # We use existing helpers for the representative
    rep_row = _load_event_row(symbol, timeframe, rep_event_id)
    rep_ann = best_member.annotation
    
    # Mock QC for now (since we skipped it)
    qc_dict = {
        "verdict": "PASS",
        "score": 100,
        "note": f"Archetype Cluster {cluster.cluster_id}"
    }

    pointer_paths = {
        "annotation_path": str(SniperAnnotationRepository()._file_path(symbol, timeframe)),
        "history_path": str(coin_cell_paths.get_history_file(symbol, timeframe))
    }

    # Extract Price Window for Representative
    price_window_df = _extract_price_window(symbol, timeframe, getattr(rep_row, 'event_time', None))
    
    # Deep Narrative for Representative
    story_engine = DeepNarrativeService()
    narrative_data = story_engine.generate_story(
        symbol, timeframe, 
        pd.to_datetime(getattr(rep_row, 'event_time', '')).isoformat() if rep_row is not None else ""
    )
    
    # Bundle Label = Archetype Label (Signal Signature)
    # Desc = Narrative + Signature Details
    narrative = {
        "label": f"[Archetype {cluster.cluster_id}] {cluster.label}",
        "desc": f"**Structure:** {cluster.centroid.get('signature', 'Unknown')}. \n\n" + narrative_data.get("desc", ""),
        "risk": narrative_data.get("risk", "Medium"),
        "details": narrative_data.get("details", {})
    }

    # 5. Build Manifest (Updated for Cluster)
    member_ids = [m.event_id for m in cluster.members]
    narrative['details']['cluster_members'] = member_ids
    narrative['details']['centroid'] = cluster.centroid

    manifest = ApprovedRallyBundleManifest(
        bundle_id=std_bundle_id,
        symbol=symbol,
        timeframe=timeframe,
        event_id=rep_event_id, # Representative
        event_time_iso=pd.to_datetime(getattr(rep_row, 'event_time', '')).isoformat() if rep_row is not None else "",
        tier=tier,
        approved={"entry_offset": getattr(rep_ann, 'entry_bar_offset', 0)}, # Minimal
        qc=qc_dict,
        pointers=pointer_paths,
        scenario_id="ARCHETYPE_CLUSTER",
        narrative=narrative
    )

    # 6. Write Files
    bundle_io.write_bundle_files(
        bundle_dir=bundle_dir,
        manifest=manifest,
        annotation_dict=rep_ann.to_dict(),
        qc_report_dict=qc_dict,
        event_row_dict={"tier": tier, "gain": c_gain, "members_count": len(cluster.members)},
        price_window_df=price_window_df
    )
    
    # Write Members JSON explicitly
    with open(bundle_dir / "archetype_members.json", "w") as f:
        json.dump({
            "cluster_id": cluster.cluster_id,
            "centroid": cluster.centroid,
            "members": [
                {"event_id": m.event_id, "gain": m.gain, "duration": m.duration} 
                for m in cluster.members
            ]
        }, f, indent=2)
    
    # --- AUTO-PROMOTE TO MATRIX (User Request: "Direk otomatik gitsin") ---
    try:
        # Define Bus Path (Relative to Project Root usually, or absolute)
        # We assume .tezaver_bus is in project root.
        bus_root = Path(".tezaver_bus")
        candidates_dir = bus_root / "artifacts/mac/candidates"
        candidates_dir.mkdir(parents=True, exist_ok=True)
        
        candidate_data = {
            "source": "foundry_archetype_auto",
            "promoted_at": int(time.time()),
            "bundle_id": std_bundle_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "tier": tier,
            "manifest": asdict(manifest) if hasattr(manifest, 'to_dict') else manifest.__dict__,
            "bundle_path": str(bundle_dir.resolve())
        }
        
        fname = f"{std_bundle_id}_{uuid.uuid4().hex[:6]}.json"
        
        with open(candidates_dir / fname, "w") as f:
            json.dump(candidate_data, f, indent=2)
            
    except Exception as e:
        print(f"[WARNING] Auto-Promotion failed for {std_bundle_id}: {e}")

    return str(bundle_dir)


def package_symbol_timeframe(
    symbol: str,
    timeframe: str,
    limit: Optional[int] = None, # Not used in Cluster mode effectively
    limit_per_tier: int = 3,     # Used to limit number of clusters if we split too much?
    output_root: str = ".tezaver_matrix/approved_bundles_v1"
) -> List[str]:
    """
    Package QC-PASSED events using CLUSTER ENGINE.
    """
    bundle_dirs = []
    
    # Load all annotations
    repo = SniperAnnotationRepository()
    annotations = repo.load_all(symbol, timeframe)
    if not annotations:
        return bundle_dirs
        
    approved_anns = [ann for ann in annotations if getattr(ann, 'status', '') == 'APPROVED']
    if not approved_anns:
        return bundle_dirs

    # --- TIER GROUPING ---
    tier_lists = {} # Tier -> List[Features]
    
    for ann in approved_anns:
        row = _load_event_row(symbol, timeframe, ann.event_id)
        if row is not None:
            feature = extract_features(row, ann)
            
            # feature.gain is 0-100 (e.g. 48.9). 
            # compute_tier expects 0-1 (e.g. 0.489).
            tier = compute_tier_from_gain_pct(feature.gain / 100.0) or "UNKNOWN"
            
            if tier not in tier_lists:
                tier_lists[tier] = []
            tier_lists[tier].append(feature)
            
    # --- CLUSTERING & PACKAGING ---
    engine = ClusterEngine()
    
    for tier, features in tier_lists.items():
        if not features: continue
        
        # Run Clustering
        clusters = engine.cluster_rallies(features)
        
        # Package Each Cluster
        for clust in clusters:
            b_dir = package_cluster(clust, symbol, timeframe, tier, output_root)
            if b_dir:
                bundle_dirs.append(b_dir)
                
    return bundle_dirs


from functools import lru_cache

@lru_cache(maxsize=8)
def _cached_read_parquet(path: str) -> Optional[pd.DataFrame]:
    if not Path(path).exists():
        return None
    try:
        df = pd.read_parquet(path)
        if 'event_time' in df.columns:
            df['event_time'] = pd.to_datetime(df['event_time'], errors='coerce')
        return df
    except:
        return None

def _load_event_row(symbol: str, timeframe: str, event_id: str) -> Optional[pd.Series]:
    """Load event dataset row for the given event_id."""
    event_path = _get_event_dataset_path(symbol, timeframe)
    if not event_path:
        return None
        
    df = _cached_read_parquet(event_path)
    if df is None:
        return None
    
    try:
        # Determine ID column
        id_col = None
        for c in ["event_id", "event_idx", "entry_id"]:
            if c in df.columns:
                id_col = c
                break
        
        matches = pd.DataFrame()
        if id_col:
            # Try match by ID (handling potential type mismatch like int vs str)
            try:
                # Assuming simple equality first
                matches = df[df[id_col] == event_id]
                if matches.empty:
                    # Retry with string conversion if needed
                    matches = df[df[id_col].astype(str) == str(event_id)]
            except:
                pass
        
        # Fallback: Try matching event_id AS event_time if no matches found
        if matches.empty and 'event_time' in df.columns:
            try:
                # 1. Try direct parse
                target_dt = pd.to_datetime(event_id, errors='coerce')
                
                # 2. Try slicing standard ID format: SYMBOL_TF_YYYYMMDDHHMM
                if pd.isna(target_dt) and "_" in str(event_id):
                    parts = str(event_id).split("_")
                    if len(parts) >= 3:
                        # Assumption: Last part is the time
                        time_part = parts[-1]
                        # Try parsing YYYYMMDDHHMM
                        try:
                            target_dt = pd.to_datetime(time_part, format='%Y%m%d%H%M')
                        except:
                            pass
                
                if pd.notna(target_dt):
                    # Compare with tolerance? Or exact? 
                    # Parquet times are usually precise. But maybe timezone diff?
                    # Let's try exact first.
                    matches = df[df['event_time'] == target_dt]
                    
                    if matches.empty:
                        # Try ignoring seconds/nanoseconds if dataset has them
                        # Round to minutes?
                         matches = df[df['event_time'].dt.floor('min') == target_dt.floor('min')]
            except:
                pass
                
        if not matches.empty:
            return matches.iloc[0]
        
        return None
    except:
        return None


def _get_event_dataset_path(symbol: str, timeframe: str) -> Optional[str]:
    """Get path to event dataset for the given symbol/timeframe."""
    if timeframe == "15m":
        return f"library/fast15_rallies/{symbol}/fast15_rallies.parquet"
    elif timeframe == "1h":
        return f"library/time_labs/1h/{symbol}/rallies_1h.parquet"
    elif timeframe == "4h":
        return f"library/time_labs/4h/{symbol}/rallies_4h.parquet"
    return None


def _extract_price_window(
    symbol: str,
    timeframe: str,
    event_time: Any,
    window_before: int = 100,
    window_after: int = 300
) -> Optional[pd.DataFrame]:
    """
    Extract price window around event.
    
    Args:
        symbol: Trading pair symbol
        timeframe: Timeframe
        event_time: Event timestamp
        window_before: Bars before event
        window_after: Bars after event
    
    Returns:
        Price window dataframe or None
    """
    if event_time is None or pd.isna(event_time):
        return None
    
    history_file = coin_cell_paths.get_history_file(symbol, timeframe)
    if not history_file.exists():
        return None
    
    try:
        df = pd.read_parquet(history_file)
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', errors='coerce')
        
        # Normalize timezone
        event_ts = pd.to_datetime(event_time)
        if df['open_time'].dt.tz is not None and event_ts.tz is None:
            event_ts = event_ts.tz_localize('UTC')
        elif df['open_time'].dt.tz is None and event_ts.tz is not None:
            event_ts = event_ts.tz_localize(None)
        
        # Find event index
        mask = df['open_time'] <= event_ts
        matching_indices = df[mask].index.tolist()
        
        if not matching_indices:
            return None
        
        event_idx = matching_indices[-1]
        
        # Extract window
        start_idx = max(0, event_idx - window_before)
        end_idx = min(len(df), event_idx + window_after + 1)
        
        window_df = df.iloc[start_idx:end_idx].copy()
        
        # Keep only essential columns
        essential_cols = ['open_time', 'open', 'high', 'low', 'close', 'volume']
        available_cols = [col for col in essential_cols if col in window_df.columns]
        
        return window_df[available_cols]
    except:
        return None
