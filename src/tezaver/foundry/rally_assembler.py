"""
Rally Assembler Service (The Assembly Line)
===========================================
"Çelik Gibi Sağlam Bir Pipeline İçin"

This service acts as the central brain for the Foundry Pipeline.
It unifies:
1. Raw Scanner Data (Parquet) -> Provides Gain, Bars, Tier (Metadata)
2. User Annotations (Repo)    -> Provides Status, Archetype, Custom Entry/Exit (Decisions)

It solves the "Data Fragmentation" problem by producing a single, trusted "AssembledRally" object
that flows through Revize -> Molder -> Alchemist.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime
import pandas as pd
import streamlit as st

from tezaver.core.annotations import SniperAnnotationRepository, SniperAnnotation, SniperStatus
from tezaver.core import coin_cell_paths
from tezaver.ui.ony_tab import normalize_tier, compute_tier_from_gain, TIERS

@dataclass
class AssembledRally:
    """
    The Single Source of Truth for a Rally in the UI.
    Merges raw data and human decision.
    """
    # Identity
    event_id: str
    symbol: str
    timeframe: str
    event_time: datetime
    
    # Metadata (From Raw/Parquet)
    tier: str  # DIAMOND, GOLD, etc.
    raw_tier: str # Original bucket (e.g. 5p_10p)
    gain_pct: float # 0.15 = 15%
    bars_to_peak: int
    
    # Human Decisions (From Repo)
    status: str # PENDING, APPROVED, REJECTED
    archetype: Optional[str] # PHOENIX, etc.
    entry_offset: int
    exit_offset: Optional[int]
    is_revised: bool
    note: str
    
    # Derivations
    display_label: str # For Selectbox
    
    def get_icon(self) -> str:
        """Get the status/archetype icon."""
        if self.archetype:
            # Map Archetype to Icon (Simple mapping)
            # You can import from core.molds if circular import not an issue
            return "🏷️" # Generic fallback or implementation specific
        
        tier_icons = {"DIAMOND": "💎", "GOLD": "🥇", "SILVER": "🥈", "BRONZE": "🥉"}
        return tier_icons.get(self.tier, "⚪")

class RallyAssembler:
    """
    The Assembly Line Manager.
    """
    
    def __init__(self):
        self.repo = SniperAnnotationRepository()
    
    def get_assembled_rallies(self, symbol: str, timeframe: str) -> List[AssembledRally]:
        """
        The Master Function. Returns fully merged rallies for a coin/tf.
        """
        # 1. Load Raw Data (The Ore)
        df_raw = self._load_raw_parquet(symbol, timeframe)
        
        # 2. Load Annotations (The Papers)
        annotations = self.repo.load_all(symbol, timeframe)
        ann_map = {str(a.event_id): a for a in annotations}
        
        # 3. Create Metadata Map from Raw
        meta_map = {}
        if not df_raw.empty:
            # Normalize ID column to string just in case
            if 'event_id' in df_raw.columns:
                df_raw['str_id'] = df_raw['event_id'].astype(str)
                # Create index
                # We need to handle the case where Parquet ID doesn't match Repo ID (e.g. _RVZ_ suffix)
                # Strategy: Map "Base ID" to Metadata.
                for idx, row in df_raw.iterrows():
                    eid = str(row['event_id'])
                    # Normalize Tier
                    if 'rally_grade' in row: t = normalize_tier(row['rally_grade'])
                    else: t = normalize_tier(compute_tier_from_gain(row.get('future_max_gain_pct', 0)))
                    
                    meta_map[eid] = {
                        'tier': t or "OTHER",
                        'raw_tier': row.get('rally_bucket', 'unknown'),
                        'gain': row.get('future_max_gain_pct', 0),
                        'bars': int(row.get('bars_to_peak', 0)),
                        'ts': row.get('event_time')
                    }

        # 4. Assembly Phase
        assembled = []
        
        # A) Process Annotations (Primary Source for Pipeline)
        # We iterate annotations because they represent the "Active" work items.
        # A) Process Annotations (Primary Source for Pipeline)
        # We iterate annotations because they represent the "Active" work items.
        for ann in annotations:
            # Immutable ID Architecture: ID is constant.
            # Revision is determined by Label OR custom offsets (backward compatibility)
            is_revised = (ann.label == "REV") or (ann.exit_bar_offset is not None) or (ann.entry_bar_offset != 0)
            
            # Find Metadata (Exact match only)
            meta = meta_map.get(ann.event_id)
            
            # Fallback Metadata
            if not meta:
                meta = {
                    'tier': self._extract_tier_from_id(ann.event_id),
                    'raw_tier': 'manual',
                    'gain': 0.0,
                    'bars': 0,
                    'ts': self._extract_ts_from_id(ann.event_id)
                }

            # Recalculate Logic for Revised Rallies
            final_bars = meta['bars']
            final_gain = meta['gain']
            
            if ann.exit_bar_offset is not None:
                # If we have explicit exit, duration is exit - entry
                calc_bars = ann.exit_bar_offset - ann.entry_bar_offset
                if calc_bars > 0:
                     final_bars = calc_bars
            
            # Use Revised Gain if available
            if getattr(ann, 'rev_gain', None) is not None:
                final_gain = ann.rev_gain
            
            # Build Object
            lbl = self._build_label(meta['tier'], final_gain, final_bars, ann)
            
            obj = AssembledRally(
                event_id=ann.event_id,
                symbol=ann.symbol,
                timeframe=ann.timeframe,
                event_time=meta['ts'],
                tier=meta['tier'],
                raw_tier=meta['raw_tier'],
                gain_pct=final_gain,
                bars_to_peak=final_bars,
                status=ann.status,
                archetype=ann.archetype,
                entry_offset=ann.entry_bar_offset,
                exit_offset=ann.exit_bar_offset,
                is_revised=is_revised,
                note=ann.note,
                display_label=lbl
            )
            assembled.append(obj)
            
        # B) (Optional) Include Raw Rallies that are NOT annotated yet?
        # For Molder/Alchemist, we usually only care about Annotated ones.
        # For a "Raw View", we might want them.
        # For now, we return only Annotated ones + Raw ones that match?
        # Wait, the user wants "Raw -> Revize". Revize sees Raw.
        # But Molder sees "Approved".
        # This function returns EVERYTHING so the caller can filter.
        
        # Actually, let's keep it simple. This function focuses on "Known" entities.
        # If we need "Pending Raw" items, we would iterate df_raw and add missing.
        
        return assembled

    def get_moldable_rallies(self, symbol: str, timeframe: str) -> List[AssembledRally]:
        """
        Get rallies ready for Molder (Approved).
        """
        all_rallies = self.get_assembled_rallies(symbol, timeframe)
        return [r for r in all_rallies if r.status == SniperStatus.APPROVED]

    def get_alchemist_ready_rallies(self, symbol: str, timeframe: str) -> List[AssembledRally]:
        """
        Get rallies ready for Alchemist (Approved + Optionally Archetyped).
        For now, we return all Approved, but sorted by Quality.
        """
        return self.get_moldable_rallies(symbol, timeframe)

    # --- Helpers ---
    
    def _load_raw_parquet(self, symbol: str, tf: str) -> pd.DataFrame:
        try:
            if tf == "15m":
                p = coin_cell_paths.get_fast15_rallies_path(symbol)
            else:
                p = coin_cell_paths.get_time_labs_rallies_path(symbol, tf)
            
            if p.exists():
                return pd.read_parquet(p)
        except:
            pass
        return pd.DataFrame()

    def _parse_id(self, eid: str):
        """Deprecated: Returns (eid, False) since we no longer mutate IDs."""
        return eid, False

    def _extract_tier_from_id(self, eid: str) -> str:
        parts = eid.split('_')
        for p in parts:
            if p in ['D','G','S','B']:
                return {"D":"DIAMOND","G":"GOLD","S":"SILVER","B":"BRONZE"}[p]
        return "OTHER"

    def _extract_ts_from_id(self, eid: str) -> datetime:
        try:
            parts = eid.split('_')
            ts = int(parts[-1])
            return datetime.fromtimestamp(ts)
        except:
            return datetime.now()

    def _build_label(self, tier: str, gain: float, bars: int, ann: SniperAnnotation) -> str:
        """Construct the consistent UI Label."""
        # Icons
        tier_map = {"DIAMOND": "💎", "GOLD": "🥇", "SILVER": "🥈", "BRONZE": "🥉", "OTHER": "🔹"}
        t_icon = tier_map.get(tier, "🔹")
        
        # Robust Revision Check
        is_revised_check = (ann.label == "REV") or (ann.exit_bar_offset is not None) or (ann.entry_bar_offset != 0)
        rev_icon = "🛠️" if is_revised_check else ""
        
        # Archetype
        arch_str = ""
        if ann.archetype:
            arch_str = f" [{ann.archetype}]"
            
        # Gain
        g_str = f"+{gain*100:.1f}%"
        
        # Debug Info
        rg_dbg = ""
        if getattr(ann, 'rev_gain', None) is not None:
            rg_dbg = f" [RG:{ann.rev_gain*100:.1f}%]"

        return f"[DBG] {t_icon} {rev_icon}{arch_str} | {g_str}{rg_dbg} | {bars}bar"
