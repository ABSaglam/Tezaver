
import pandas as pd
import numpy as np
import logging
from typing import List, Optional, Tuple
from datetime import timedelta

from tezaver.core.cipher_types import (
    RallyParticle, 
    RallySequence, 
    ParticleType, 
    MasterCipher,
    SentinelAlert
)

logger = logging.getLogger(__name__)

class AlchemistEngine:
    """
    The Alchemist's Engine.
    Responsibility: 
    1. Extract DNA (Particles) from raw market data.
    2. Sequence them into a Causal Chain.
    3. Validate chains against history (The Crucible).
    """

    def __init__(self):
        # Configuration for "Atomic" thresholds
        self.rsi_oversold_threshold = 30
        self.rsi_breakout_levels = [50, 70]
        self.vol_spike_ratio = 2.5
        self.squeeze_bandwidth_percent = 0.10 # 10% BB Width

    def extract_sequence(
        self, 
        df_context: pd.DataFrame, 
        rally_event_id: str = "temp_id",
        symbol: str = "UNKNOWN"
    ) -> RallySequence:
        """
        Analyzes the context (lookback window) of a rally to find the causal clues.
        
        Args:
            df_context: DataFrame containing bars LEADING UP TO the rally. 
                        Target rally start should be at or near the end.
                        Must have: 'close', 'high', 'low', 'volume', 'rsi', 'bb_width' etc.
        """
        if df_context.empty:
            return RallySequence([], symbol, rally_event_id, 0)

        particles = self._scan_for_particles(df_context)
        
        # Sort by time (oldest first)
        particles.sort(key=lambda x: x.time_offset)
        
        total_duration = abs(particles[0].time_offset) if particles else 0
        
        return RallySequence(
            particles=particles, 
            symbol=symbol, 
            rally_event_id=rally_event_id,
            total_duration_bars=total_duration
        )

    def _scan_for_particles(self, df: pd.DataFrame) -> List[RallyParticle]:
        """
        The Mining Process. Scans the dataframe for atomic events.
        """
        particles = []
        # We process from T-N to T-0.
        # Reference index is the last bar (T-0, Rally Start).
        reference_idx = df.index[-1]
        
        # 1. RSI Particles
        if 'rsi' in df.columns:
            self._mine_rsi_particles(df, particles, reference_idx)

        # 2. Volume Particles
        if 'volume' in df.columns:
            self._mine_volume_particles(df, particles, reference_idx)

        # 3. Price Squeeze (BB Width)
        if 'bb_width' in df.columns:
            self._mine_squeeze_particles(df, particles, reference_idx)

        return particles

    def _mine_rsi_particles(self, df, particles, ref_idx):
        # Look for Deep Oversold (<30)
        oversold_mask = df['rsi'] < self.rsi_oversold_threshold
        if oversold_mask.any():
            # Find the *deepest* point or the *last* point? 
            # Let's take the first significant dip in the window.
            idx = df[oversold_mask].index[-1] # closest to rally
            val = df.loc[idx, 'rsi']
            offset = int(idx - ref_idx) # Negative offset
            
            p = RallyParticle(
                type=ParticleType.RSI_OVERSOLD,
                val=round(val, 2),
                time_offset=offset,
                timeframe="15m", # Defaulting for now, context should provide this
                description=f"RSI Dip to {val:.1f}",
                weight=0.8
            )
            particles.append(p)

        # Look for Momentum Breakout (Crossing 50 strongly)
        # Simple logic: Was <50, Now >55
        # (This is simplified, a real implementation would check crossovers)
        pass

    def _mine_volume_particles(self, df, particles, ref_idx):
        # Calculate Rolling Average Volume if not present
        if 'vol_ma' not in df.columns:
            vol_ma = df['volume'].rolling(20).mean()
        else:
            vol_ma = df['vol_ma']
            
        # Spike Detection
        spike_mask = df['volume'] > (vol_ma * self.vol_spike_ratio)
        if spike_mask.any():
            # Get the biggest spike
            spike_rows = df[spike_mask]
            best_idx = spike_rows['volume'].idxmax()
            ratio = df.loc[best_idx, 'volume'] / vol_ma.loc[best_idx]
            offset = int(best_idx - ref_idx)
            
            p = RallyParticle(
                type=ParticleType.VOL_SPIKE,
                val=round(ratio, 2),
                time_offset=offset,
                timeframe="15m",
                description=f"Vol Spike {ratio:.1f}x",
                weight=0.9
            )
            particles.append(p)

    def _mine_squeeze_particles(self, df, particles, ref_idx):
        mask = df['bb_width'] < self.squeeze_bandwidth_percent
        if mask.any():
            # Consecutiveness matters for squeeze, but let's just mark the "Tightest Point"
            min_width_idx = df[mask]['bb_width'].idxmin()
            val = df.loc[min_width_idx, 'bb_width']
            offset = int(min_width_idx - ref_idx)
            
            p = RallyParticle(
                type=ParticleType.PRICE_SQUEEZE,
                val=round(val, 4),
                time_offset=offset,
                timeframe="15m",
                description=f"Squeeze {val*100:.1f}%",
                weight=0.7
            )
            particles.append(p)

    def validate_sequence(self, sequence: RallySequence, history_df: pd.DataFrame) -> MasterCipher:
        """
        Backtests the sequence signature against historical data.
        Returns a MasterCipher with 'Proof' stats.
        """
        sig = sequence.key_signature
        
        # TODO: Implement actual historical scanning logic.
        # For now, we return a "Forged" MasterCipher based on the input sequence.
        
        return MasterCipher(
            name=f"Cipher-{sig[:10]}",
            sequence_signature=sig,
            template_sequence=sequence,
            conquest_score=85.5, # Mock score
            win_rate=0.72,
            avg_gain_pct=12.4,
            false_positive_rate=0.15,
            tags=["simulated", "prototype"]
        )

    def project_ghost(self, cipher: MasterCipher, current_price: float) -> List[float]:
        """
        Returns a time-series of price levels representing the 'Ghost' path.
        """
        # Linear projection based on avg_gain (Naive Ghost)
        target = current_price * (1 + cipher.avg_gain_pct/100)
        return [current_price, (current_price+target)/2, target]

    def save_master_cipher(self, cipher: MasterCipher, filename: str = None) -> str:
        """
        Persists a MasterCipher to disk (JSON).
        """
        from dataclasses import asdict
        import json
        from tezaver.core.coin_cell_paths import get_ciphers_dir
        
        c_dir = get_ciphers_dir()
        if not filename:
            # Sanitize name
            safe_name = "".join([c if c.isalnum() else "_" for c in cipher.name])
            filename = f"{safe_name}.json"
            
        file_path = c_dir / filename
        
        data = asdict(cipher)
        # Handle datetime serialization
        data['created_at'] = cipher.created_at.isoformat()
        # Handle enum serialization inside particles
        if 'template_sequence' in data and 'particles' in data['template_sequence']:
             for p in data['template_sequence']['particles']:
                 if 'type' in p and hasattr(p['type'], 'name'):
                     p['type'] = p['type'].name # Enum to string
                 # In case it's already string (if asdict treated it so? usually not for Enums)
                 
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, default=str)
            
        return str(file_path)

    def load_master_ciphers(self) -> List[MasterCipher]:
        """
        Loads all Master Ciphers from the Vault.
        """
        import json
        from tezaver.core.coin_cell_paths import get_ciphers_dir
        from tezaver.core.cipher_types import ParticleType
        
        c_dir = get_ciphers_dir()
        ciphers = []
        
        if not c_dir.exists(): return []
        
        for f_path in c_dir.glob("*.json"):
            try:
                with open(f_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Reconstruct Objects (Manual Deserialization)
                # 1. Particles
                particles = []
                raw_seq = data.get('template_sequence', {})
                for p_data in raw_seq.get('particles', []):
                    # Convert type string back to Enum
                    t_str = p_data.get('type')
                    if isinstance(t_str, str):
                        try:
                            # Handle potential format changes (ParticleType.RSI_OVERSOLD vs "RSI_OVERSOLD")
                            if "." in t_str: t_str = t_str.split(".")[-1]
                            p_type = ParticleType[t_str]
                        except:
                            p_type = ParticleType.RSI_OVERSOLD # Fallback
                    else:
                        p_type = ParticleType.RSI_OVERSOLD

                    p = RallyParticle(
                        type=p_type,
                        val=p_data.get('val', 0),
                        time_offset=p_data.get('time_offset', 0),
                        timeframe=p_data.get('timeframe', '15m'),
                        description=p_data.get('description', ''),
                        weight=p_data.get('weight', 1.0)
                    )
                    particles.append(p)
                
                # 2. Sequence
                seq = RallySequence(
                    particles=particles,
                    symbol=raw_seq.get('symbol', 'UNKNOWN'),
                    rally_event_id=raw_seq.get('rally_event_id', 'unknown'),
                    total_duration_bars=raw_seq.get('total_duration_bars', 0)
                )
                
                # 3. MasterCipher
                mc = MasterCipher(
                    name=data.get('name', 'Unnamed'),
                    sequence_signature=data.get('sequence_signature', ''),
                    template_sequence=seq,
                    conquest_score=data.get('conquest_score', 0),
                    win_rate=data.get('win_rate', 0),
                    avg_gain_pct=data.get('avg_gain_pct', 0),
                    false_positive_rate=data.get('false_positive_rate', 0),
                    tags=data.get('tags', []),
                    created_at=datetime.fromisoformat(data.get('created_at')) if data.get('created_at') else datetime.now()
                )
                ciphers.append(mc)
            except Exception as e:
                logger.error(f"Failed to load cipher {f_path}: {e}")
                
        return ciphers
