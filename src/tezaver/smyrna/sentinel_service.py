
import logging
import pandas as pd
from typing import List, Dict, Optional
from datetime import  datetime

from tezaver.core.cipher_types import MasterCipher, SentinelAlert, RallySequence
from tezaver.smyrna.alchemist_engine import AlchemistEngine

logger = logging.getLogger(__name__)

class SentinelService:
    """
    The Auto-Hunter.
    Scans live markets for matches against known 'Master Ciphers'.
    """
    
    def __init__(self, engine: AlchemistEngine):
        self.engine = engine
        self.active_ciphers: Dict[str, MasterCipher] = {} # {name: cipher}
        self.alerts: List[SentinelAlert] = []
        
        # Match threshold (0.0 - 1.0)
        # If sequence similarity > 0.75, trigger warning.
        self.alert_threshold = 0.75

    def arm_sentinel(self, ciphers: List[MasterCipher]):
        """
        Loads the Sentinels with specific targets.
        """
        self.active_ciphers = {c.name: c for c in ciphers}
        logger.info(f"Sentinel armed with {len(ciphers)} Ciphers: {list(self.active_ciphers.keys())}")

    def scan_market(self, symbol: str, df_live: pd.DataFrame) -> List[SentinelAlert]:
        """
        Checks a single symbol against ALL active ciphers.
        """
        current_alerts = []
        
        # 1. Extract Current DNA from live data
        # We assume the 'live' data window is sufficient context (e.g. last 100 bars)
        live_sequence = self.engine.extract_sequence(
            df_context=df_live, 
            rally_event_id="live_scan",
            symbol=symbol
        )
        
        # 2. Compare against each Master Cipher
        for name, cipher in self.active_ciphers.items():
            match_score, missing = self._compare_sequences(live_sequence, cipher.template_sequence)
            
            if match_score >= self.alert_threshold:
                alert = SentinelAlert(
                    symbol=symbol,
                    cipher_name=name,
                    match_score=match_score,
                    missing_particles=missing,
                    projected_target=self._calculate_target(df_live, cipher)
                )
                self.alerts.append(alert)
                current_alerts.append(alert)
                
        return current_alerts

    def _compare_sequences(self, live: RallySequence, target: RallySequence) -> float: # (score, missing)
        """
        Calculates similarity between live DNA and target DNA.
        Naive Jaccard-ish implementation for now.
        """
        # Convert to sets of signatures (Type:Timeframe)
        live_sigs = set([f"{p.type.value}:{p.timeframe}" for p in live.particles])
        target_sigs = set([f"{p.type.value}:{p.timeframe}" for p in target.particles])
        
        if not target_sigs:
            return 0.0, []
            
        common = live_sigs.intersection(target_sigs)
        score = len(common) / len(target_sigs)
        
        missing = list(target_sigs - live_sigs)
        return score, missing

    def _calculate_target(self, df, cipher):
        current_price = df['close'].iloc[-1]
        target = current_price * (1 + cipher.avg_gain_pct/100)
        return round(target, 4)
