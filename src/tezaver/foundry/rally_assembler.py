"""
Rally Assembler Service (The Assembly Line)
===========================================
"Çelik Gibi Sağlam Bir Pipeline İçin"

This service acts as the central brain for the Foundry Pipeline.
It unifies rally data using the "One Record, One Place" (SQLite) architecture.

It solves the "Data Fragmentation" problem by producing a single, trusted "AssembledRally" object
that flows through Revize -> Molder -> Alchemist.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime
import pandas as pd
from tezaver.core.annotations import SniperStatus
from tezaver.core import coin_cell_paths
from tezaver.core.tier_utils import normalize_tier, compute_tier_from_gain, TIERS
from tezaver.core.rally_store import RallyStore
from tezaver.core.molds import Archetype, ARCHETYPE_LABELS


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
            return "🏷️"
        
        tier_icons = {"DIAMOND": "💎", "GOLD": "🥇", "SILVER": "🥈", "BRONZE": "🥉"}
        return tier_icons.get(self.tier, "⚪")

class RallyAssembler:
    """
    The Assembly Line Manager.
    Uses RallyStore (SQLite) to fetch unified documents.
    """
    
    def __init__(self):
        self.store = RallyStore()

    def get_assembled_rallies(self, symbol: str, timeframe: str) -> List[AssembledRally]:
        """
        The Master Function. Returns fully merged rallies for a coin/tf using SQLite.
        """
        # 1. Fetch from SQLite
        rows = self.store.list_rallies(symbol=symbol, timeframe=timeframe)
        return [self._assemble_rally_from_row(row) for row in rows]

    def get_ony_review_rallies(self, symbol: str, timeframe: str) -> List[AssembledRally]:
        """
        Returns ALL rallies (Raw + Annotated) for the Revize/Ony Review Screen.
        Identical to get_assembled_rallies() now because Store holds everything unified.
        """
        return self.get_assembled_rallies(symbol, timeframe)

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

    def _assemble_rally_from_row(self, row: Dict) -> AssembledRally:
        # Extract layers
        # Security: defaults to empty dict if None
        raw = row.get('raw_data', {}) or {}
        rev = row.get('rev_data', {}) or {}
        eid = row['id']
        ts = row['event_time']
        tier = row.get('tier', 'OTHER') # Might not match raw bucket
        
        # Defaults from raw
        raw_gain = raw.get('future_max_gain_pct')
        if raw_gain is None: raw_gain = 0.0
        
        raw_bars = int(raw.get('bars_to_peak', 0))
        raw_bucket = raw.get('rally_bucket', 'unknown')
        
        # Rev overrides
        status = rev.get('status', 'PENDING')
        entry_offset = rev.get('entry_bar_offset', 0)
        exit_offset = rev.get('exit_bar_offset')
        note = rev.get('note', '')
        archetype = rev.get('archetype')
        
        is_revised = (status != 'PENDING') or (entry_offset != 0) or (exit_offset is not None)
        
        # Calculations: Paranoid Gain Check
        final_gain = rev.get('rev_gain')
        if final_gain is None:
            final_gain = raw_gain
            
        # Ensure float
        try:
            final_gain = float(final_gain)
        except (TypeError, ValueError):
            final_gain = 0.0
            
        final_bars = raw_bars
        if exit_offset is not None:
            try:
                calc_bars = int(exit_offset) - int(entry_offset)
                if calc_bars > 0: final_bars = calc_bars
            except:
                pass
            
        # Label Construction
        tier_map = {"DIAMOND": "💎", "GOLD": "🥇", "SILVER": "🥈", "BRONZE": "🥉", "OTHER": "🔹"}
        t_icon = tier_map.get(tier, "🔹")
        rev_icon = "🛠️" if is_revised else ""
        
        # Archetype Icon Logic
        arch_str = ""
        if archetype:
            try:
                # Try to map to Icon
                a_enum = Archetype(archetype)
                lbl = ARCHETYPE_LABELS.get(a_enum, "")
                # Extract icon (last part)
                if " " in lbl: arch_str = f" {lbl.split(' ')[-1]}"
                else: arch_str = " 🏷️"
            except:
                # Fallback
                arch_str = f" [{archetype}]"

        g_str = f"+{final_gain*100:.1f}%"
        
        # Ensure Timestamp is datetime
        if isinstance(ts, str):
             try: ts = pd.to_datetime(ts)
             except: pass
             
        # Date Formatting (DD MMM YYYY HH:MM)
        try:
            date_str = ts.strftime('%d %b %Y %H:%M')
        except:
            date_str = str(ts)
        
        # Standardized Label: ICON | DATE | GAIN | BARS
        # User requested Vertical Bar separator
        display_label = f"{t_icon} {rev_icon}{arch_str} | {date_str} | {g_str} | {final_bars}bar"
        
        return AssembledRally(
            event_id=eid,
            symbol=row['symbol'],
            timeframe=row['timeframe'],
            event_time=ts,
            tier=tier,
            raw_tier=raw_bucket,
            gain_pct=final_gain,
            bars_to_peak=final_bars,
            status=status,
            archetype=archetype,
            entry_offset=entry_offset,
            exit_offset=exit_offset,
            is_revised=is_revised,
            note=note,
            display_label=display_label
        )
