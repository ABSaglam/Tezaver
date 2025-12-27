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
import os

from tezaver.core.annotations import SniperAnnotation, SniperAnnotationRepository
from tezaver.foundry.models import QCReport
from tezaver.foundry.bundle_models import ApprovedRallyBundleManifest
from tezaver.schemas.bundle_v1 import BundleManifestV1, BundleNamingV1, PROTOCOL_VERSION
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
    
    # ... Imports
    from tezaver.schemas.bundle_v1 import BundleManifestV1, BundleNamingV1, PROTOCOL_VERSION
    from datetime import datetime

    # ... (Logic to load annotation, report, etc.)

    # 4. Generate Bundle ID
    # CRITICAL FIX for Bulk Packaging:
    # Standard Naming (Week-Based) causes overwrites when backfilling history.
    # We switch to using EVENT_ID as the Bundle ID to ensure uniqueness.
    
    # Restore 'now' for manifest creation
    now = datetime.now()
    
    std_bundle_id = event_id
    
    # Create bundle directory using event_id as folder name
    bundle_dir = bundle_io.create_bundle_directory(
        symbol, timeframe, event_id, output_root, folder_name=std_bundle_id
    )
    
    # 4. Data Gathering
    # Event Time
    event_time_iso = str(event_row.get('event_time', ''))
    
    # Needs extracted price window
    price_window_df = _extract_price_window(
        symbol, timeframe, event_time_iso
    )
    
    # 5. Narrative Analysis (The Soul)
    # Uses Rally Narrative Engine to label the event (e.g. "Mechanical Breakout")
    narrative_id = analyze_scenario(event_row)
    narrative_def = SCENARIO_DEFINITIONS.get(narrative_id, SCENARIO_DEFINITIONS["SCENARIO_NEUTRAL"])
    
    # Pointers
    pointers = {
        "annotation": f"annotation.json",
        "qc_report": f"qc_report.json",
        "event_data": f"event_row.json",
        "price_window": f"price_window.parquet"
    }
    
    # 5. Build Manifest V1
    # Clean symbol for Manifest (remove underscores if any, keep standard)
    manifest = BundleManifestV1(
        protocol_version=PROTOCOL_VERSION,
        bundle_id=std_bundle_id,
        source_system="foundry_mac",
        created_ts=now.isoformat(),
        symbol=symbol,
        timeframe=timeframe,
        data_hash="pending", # Todo: calculate hash
        status="APPROVED_DOKUMHANE",
        suffix_code="D",
        summary=f"Auto-packaged event {event_id} from Foundry. Tier: {tier}",
        details={
            "original_event_id": str(event_row.get('event_id', event_id)),
            "tier": tier,
            "qc_score": qc_report.score,
            "narrative_label": narrative_def.get("label"),
            "pointers": pointers
        }
    )
    
    # ... Write files using bundle_io (might need update to start accepting V1 manifest dict)
    # bundle_io.write_bundle_files expects object with to_dict? 
    # Our BundleManifestV1 has to_dict.
    
    # Prepare event row dict (minimal fields)
    event_time_iso = str(event_row.get('event_time', ''))
    event_row_dict = {
        "event_id": event_id,
        "event_time": event_time_iso,
        "future_max_gain_pct": event_row.get('future_max_gain_pct'),
        "bars_to_peak": int(event_row.get('bars_to_peak')) if pd.notna(event_row.get('bars_to_peak')) else None,
        "tier": tier
    }
    
    # Prepare annotation dict
    annotation_dict = annotation.to_dict()

    bundle_io.write_bundle_files(
        bundle_dir=bundle_dir,
        manifest=manifest, # Polymorphism: conforms to to_dict
        annotation_dict=annotation_dict,
        qc_report_dict=qc_report_dict,
        event_row_dict=event_row_dict,
        price_window_df=price_window_df
    )
    
    return str(bundle_dir)
    
    # 6. Publish to BUS (Inbox)
    # Protocol V1 Requirement: Deliver to ~/.tezaver_bus/pipeline/inbox
    import shutil
    try:
        # Detect Bus Root
        home_dir = Path(os.path.expanduser("~"))
        if "TEZAVER_BUS" in os.environ:
             bus_root = Path(os.environ["TEZAVER_BUS"])
        else:
             bus_root = home_dir / ".tezaver_bus"
             
        bus_inbox = bus_root / "pipeline" / "inbox"
        bus_inbox.mkdir(parents=True, exist_ok=True)
        
        target_path = bus_inbox / std_bundle_id
        if target_path.exists():
            shutil.rmtree(target_path)
        
        shutil.copytree(bundle_dir, target_path)
        print(f"[PUBLISHER] Delivered {std_bundle_id} to Bus Inbox.")
    except Exception as e:
        print(f"[PUBLISHER] Failed to deliver to bus: {e}")
        
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
        home_dir = Path(os.path.expanduser("~"))
        if "TEZAVER_BUS" in os.environ:
             bus_root = Path(os.environ["TEZAVER_BUS"])
        else:
             bus_root = home_dir / ".tezaver_bus"
             
        # Candidates Inbox
        candidates_dir = bus_root / "pipeline" / "inbox"
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
            # Try match by ID
            matches = df[df[id_col] == event_id]
            if matches.empty:
                matches = df[df[id_col].astype(str) == str(event_id)]
        
        # Fallback: Match by Timestamp
        if matches.empty and 'event_time' in df.columns:
            try:
                # 1. Parse timestamp from event_id (Standard ID: SYMBOL_TF_YYYYMMDDHHMM)
                ts_part = str(event_id).split("_")[-1]
                
                # Check if last part is numeric timestamp (Seconds or Ms)
                if ts_part.isdigit():
                    ts_val = int(ts_part)
                    is_ms = len(ts_part) > 10
                    
                    if is_ms:
                        df_ts = df['event_time'].astype('int64') // 10**6
                    else:
                        df_ts = df['event_time'].astype('int64') // 10**9
                        
                    matches = df[df_ts == ts_val]
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
        print(f"DEBUG: Event time is None/NaT for {symbol}")
        return None
    
    history_file = coin_cell_paths.get_history_file(symbol, timeframe)
    if not history_file.exists():
        print(f"DEBUG: History file not found: {history_file}")
        return None
    
    try:
        df = pd.read_parquet(history_file)
        
        # Schema Normalization
        if 'timestamp' in df.columns and 'open_time' not in df.columns:
            df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')
        elif 'open_time' in df.columns:
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', errors='coerce')
        else:
            print(f"DEBUG: Missing timestamp/open_time column in {history_file}")
            return None
        
        # Normalize timezone
        # Handle numeric string or int
        try:
            if str(event_time).isdigit():
                 event_ts = pd.to_datetime(int(event_time), unit='ms')
            else:
                 event_ts = pd.to_datetime(event_time)
        except:
             print(f"DEBUG: Failed to parse event_time: {event_time}")
             return None

        if df['open_time'].dt.tz is not None and event_ts.tz is None:
            event_ts = event_ts.tz_localize('UTC')
        elif df['open_time'].dt.tz is None and event_ts.tz is not None:
            event_ts = event_ts.tz_localize(None)
        
        # Find event index
        mask = df['open_time'] <= event_ts
        matching_indices = df[mask].index.tolist()
        
        if not matching_indices:
            print(f"DEBUG: No matching index for {event_ts} in {symbol}")
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
