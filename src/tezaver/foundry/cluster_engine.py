"""
Foundry Cluster Engine
======================

Analyzes groups of rallies (e.g. BTC 15m Gold) to identify Archetypes (Common Structures)
and separate Outliers.

Logic:
1. Feature Extraction (Gain, Duration, Shape).
2. Centroid Calculation (Median).
3. Harmony Check (Deviation from Centroid).
4. Grouping (Main Cluster vs Outliers).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import numpy as np
import pandas as pd

from tezaver.sniper.sniper_annotations import SniperAnnotation

@dataclass
class RallyFeature:
    event_id: str
    gain: float
    duration: int
    signature: str       # e.g. "RSI_OS | VOL_High | BULL"
    signature_map: Dict[str, str] # raw components
    annotation: Optional[SniperAnnotation] = None

@dataclass
class ArchetypeCluster:
    cluster_id: str  # e.g. "A", "B"
    label: str       # e.g. "RSI Oversold REVERSAL (High Vol)"
    members: List[RallyFeature] = field(default_factory=list)
    centroid: Dict[str, float] = field(default_factory=dict) # Still useful for average stats of the group
    
    @property
    def size(self) -> int:
        return len(self.members)

class ClusterEngine:
    def cluster_rallies(self, features: List[RallyFeature]) -> List[ArchetypeCluster]:
        """
        Groups rallies based on EXACT Signal Signature.
        """
        if not features:
            return []
            
        # Group by Signature
        groups = {}
        for f in features:
            sig = f.signature
            if sig not in groups:
                groups[sig] = []
            groups[sig].append(f)
            
        # Convert to Clusters
        clusters = []
        
        # Sort groups by size (Dominant first)
        sorted_sigs = sorted(groups.keys(), key=lambda s: len(groups[s]), reverse=True)
        
        for idx, sig in enumerate(sorted_sigs):
            members = groups[sig]
            
            # Label comes from the signature
            # sig is like "RSI_OS | VOL_High | BULL"
            # Let's make it readable: "Oversold Reversal (High Vol)"
            readable_label = self._humanize_signature(members[0].signature_map)
            
            # Calculate stats for this group
            gains = [m.gain for m in members]
            durs = [m.duration for m in members]
            
            centroid = {
                "gain": float(np.mean(gains)),
                "duration": float(np.mean(durs)),
                "count": len(members),
                "signature": sig
            }
            
            clusters.append(ArchetypeCluster(
                cluster_id=generate_cluster_id(idx), # A, B, C
                label=readable_label,
                members=members,
                centroid=centroid
            ))
            
        return clusters

    def _humanize_signature(self, parts: Dict[str, str]) -> str:
        rsi = parts.get("rsi", "Neut")
        vol = parts.get("vol", "Norm")
        trend = parts.get("trend", "Neut")
        
        label_parts = []
        
        # RSI
        if rsi == "OS": label_parts.append("Oversold Reversal")
        elif rsi == "OB": label_parts.append("Overbought Continuation")
        else: label_parts.append("Neutral Setup")
        
        # Trend
        if trend == "BEAR": label_parts.append("(Bear Ctxt)")
        
        # Volume
        if vol == "Explosive": label_parts.append("w/ Explosive Vol")
        elif vol == "High": label_parts.append("w/ High Vol")
        
        return " ".join(label_parts)

def generate_cluster_id(idx: int) -> str:
    # 0->A, 1->B...
    return chr(65 + idx)

def extract_features(row: pd.Series, annotation: SniperAnnotation) -> RallyFeature:
    """Extract Signal Signature from Event Row"""
    # 1. Gain/Dur
    # Raw gain is decimal (e.g. 0.07 for 7%). Convert to Percentage (7.0).
    raw_gain = float(row.get('future_max_gain_pct', 0) if pd.notna(row.get('future_max_gain_pct')) else 0)
    gain = raw_gain * 100.0 
    dur = int(row.get('bars_to_peak', 0) if pd.notna(row.get('bars_to_peak')) else 0)
    
    # 2. Extract Signals (Safe parsing)
    # RSI
    rsi = float(row.get('rsi_14', 50))
    if rsi < 30: rsi_state = "OS"
    elif rsi > 70: rsi_state = "OB"
    else: rsi_state = "Neut"
    
    # Volume (Vol vs MA)
    vol = float(row.get('volume', 0))
    vol_ma = float(row.get('volume_ma_20', vol)) # Fallback if missing
    if vol_ma <= 0: vol_ratio = 1.0
    else: vol_ratio = vol / vol_ma
    
    if vol_ratio > 3.0: vol_state = "Explosive"
    elif vol_ratio > 1.5: vol_state = "High"
    else: vol_state = "Norm"
    
    # Trend (Close vs EMA50/200)
    close = float(row.get('close', 0))
    ema = float(row.get('ema_50', close))
    if close > ema: trend_state = "BULL"
    else: trend_state = "BEAR"
    
    # Signature Construction
    sig_map = {"rsi": rsi_state, "vol": vol_state, "trend": trend_state}
    signature = f"{rsi_state}|{vol_state}|{trend_state}"
    
    return RallyFeature(
        event_id=annotation.event_id,
        gain=gain,
        duration=dur,
        signature=signature,
        signature_map=sig_map,
        annotation=annotation
    )
