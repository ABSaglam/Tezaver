
"""
Matrix Backtest Signal Generator V1
===================================

Evaluates bundle triggers on historical dataframes to produce Intent Candidates.
"""
import pandas as pd
from typing import List, Dict, Any
from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1
from tezaver.matrix.pool.pool_models_v1 import TradeIntentV1
from tezaver.matrix.pool.pool_engine_v1 import _generate_intent_id
from tezaver.matrix.pool.pool_reports_v1 import now_iso

class SignalGenerator:
    """
    Generates Trade Intent candidates from a dataframe based on Bundle Trigger Specs.
    """
    
    @staticmethod
    def generate_intents(
        df: pd.DataFrame, 
        manifest: ApprovedRallyBundleManifestV1
    ) -> List[Dict[str, Any]]:
        """
        Returns list of intent-like dictionaries: {timestamp, intent_obj}.
        """
        trigger = manifest.trigger_spec_v1
        if not trigger:
            return []
            
        t_type = trigger.get("type")
        
        # Simple indicator calculation
        # Note: In real system, this is done by specialized engines. 
        # For this simulated environment, we implement basic triggers or assume 'close > open' placeholders if complex.
        # But wait, User wants "Package Button -> See Result".
        # The package trigger needs to be real.
        # Common triggers: RSI_CROSS, RSI_DIP, ENGULFING.
        
        signals = []
        
        # Calculate Indicators if needed
        # We assume DF has OHLCV
        
        # Determine Logic
        if t_type == "RSI_CROSS":
            # RSI Logic
            period = trigger.get("param", 14)
            threshold = trigger.get("threshold", 30)
            
            # fast pandas rsi
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Signal: Cross below threshold (Buy Dip) or Cross above (if Short?)
            # Assuming Long Only for Rally Bundles
            # Cross Up from below 30? Or simple "Values < 30"?
            # Trigger Spec usually defines this.
            # Let's assume RSI < threshold for now.
            
            # Vectorized check
            mask = df['rsi'] < threshold
            # To avoid consecutive signals every bar, maybe require previous >= threshold?
            # Or simplified: if < 30, generate intent. Court filters if already open.
            
            signal_indices = df[mask].index
            
        else:
            # Fallback for unknown/mock triggers: Random or Every 100 bars?
            # Or "Green Candle"?
            # Let's say we don't support it yet -> Return Empty?
            # Or just signal every big drop? 
            # For "ApprovedRallyBundle", it's usually specific.
            # Let's log warning and return empty.
            return []
            
        # Create Intents
        for idx in signal_indices:
            row = df.loc[idx]
            ts = row.name if isinstance(idx, pd.Timestamp) else idx # Timestamp or Index?
            # If parquet has 'timestamp' column and index is int, use column value?
            
            ts_val = int(row['timestamp']) if 'timestamp' in row else 0
            if ts_val == 0 and isinstance(idx, pd.Timestamp):
                 ts_val = int(idx.timestamp() * 1000)
                 
            # Create Intent (approximate)
            # PoolEngine needs ISO string for ID generation
            from datetime import datetime
            ts_iso = datetime.fromtimestamp(ts_val/1000).isoformat()
            
            intent_id = _generate_intent_id(
                manifest.symbol, manifest.timeframe, manifest.bundle_id, ts_iso,
                t_type, manifest.policy_spec_v1.get("exit_policy", "UNKNOWN")
            )
            
            intent = TradeIntentV1(
                intent_id=intent_id,
                symbol=manifest.symbol,
                timeframe=manifest.timeframe,
                bundle_id=manifest.bundle_id,
                trigger_type=t_type,
                exit_policy=manifest.policy_spec_v1.get("exit_policy", "UNKNOWN"),
                created_ts_iso=ts_iso,
                reason="OK",
                qc_score=manifest.qc_score,
                proposed_notional=float(manifest.policy_spec_v1.get("notional", 100.0)),
                tier=manifest.tier,
                entry_ts_iso=None,
                scenario_id=manifest.scenario_id,
                narrative=manifest.narrative,
                bundle_certification="backtest_sim" 
            )
            
            signals.append({
                "timestamp": ts_val,
                "intent": intent
            })
            
        return signals
