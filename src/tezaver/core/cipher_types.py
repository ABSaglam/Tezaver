
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime

class ParticleType(Enum):
    """
    Classifies the type of market event (The 'Atom' of a Rally).
    """
    RSI_OVERSOLD = "RSI_OVERSOLD"     # RSI < 30
    RSI_BREAKOUT = "RSI_BREAKOUT"     # RSI breaks 50/70
    VOL_SPIKE = "VOL_SPIKE"           # Volume > 2x Moving Average
    PRICE_SQUEEZE = "PRICE_SQUEEZE"   # Bollinger Band Width < Threshold
    MOMENTUM_SHIFT = "MOMENTUM_SHIFT" # MACD Cross etc.
    SUPPORT_BOUNCE = "SUPPORT_BOUNCE" # Price touching support
    STRUCTURAL_BREAK = "STRUCTURAL_BREAK" # Break of Structure (BOS)

@dataclass
class RallyParticle:
    """
    Represents a single atomic event in the market (e.g., 'Volume Spike detected at T-5').
    """
    type: ParticleType
    val: float              # The intensity (e.g., RSI value=25, VolRatio=3.5)
    time_offset: int        # Bars before Rally Start (e.g., -5 means 5 bars ago)
    timeframe: str          # "15m", "1h", "4h"
    description: str        # Human readable: "4h Volume 3.5x Spike"
    weight: float = 1.0     # Importance score (0.0 - 1.0)

@dataclass
class RallySequence:
    """
    An ordered chain of particles that creates a narrative (The 'DNA' Strand).
    Example: [Squeeze (T-10) -> VolSpike (T-3) -> Breakout (T-0)]
    """
    particles: List[RallyParticle]
    symbol: str
    rally_event_id: str     # ID of the rally this sequence belongs to
    total_duration_bars: int
    
    @property
    def key_signature(self) -> str:
        """
        Generates a unique string signature for matching (e.g., 'SQZ:15m>VOL:1h>BRK:15m').
        """
        sorted_p = sorted(self.particles, key=lambda x: x.time_offset)
        return ">".join([f"{p.type.value}:{p.timeframe}" for p in sorted_p])

@dataclass
class MasterCipher:
    """
    A Validated "Winning Pattern" stored in the Vault.
    This is a Sequence that has been proven to predict rallies.
    """
    name: str                       # e.g., "Supernova Type-A"
    sequence_signature: str         # The key_signature to match against
    template_sequence: RallySequence # The ideal version of this sequence
    
    # Validation Stats (The Proof)
    conquest_score: float           # 0-100 (Uniqueness + Power)
    win_rate: float                 # % of times this sequence led to a rally
    avg_gain_pct: float             # Average gain when this sequence completes
    false_positive_rate: float      # % of times it failed
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list) # ["reversal", "explosive", "rare"]

@dataclass
class SentinelAlert:
    """
    Alert generated when the Sentinel finds a match in live markets.
    """
    symbol: str
    cipher_name: str
    match_score: float              # 0.0 - 1.0 (How well it fits the MasterCipher)
    missing_particles: List[str]    # What is needed to complete the sequence?
    projected_target: float         # Ghost Projection Target Price
    detected_at: datetime = field(default_factory=datetime.now)
