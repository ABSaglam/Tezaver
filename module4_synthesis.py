import json
from module1_profiler import CoinProfilingSystem
from module2_transition import TransitionEngine
from module3_energy import EnergyEngine
import pandas as pd
from datetime import datetime

class DiamondSynthesisEngine:
    """
    DIAMOND DISCOVERY ENGINE (CONSTITUTION COMPLIANT)
    Rule: No signals, no entry/exit, no predictions.
    Purpose: Reveal rare Diamond conditions for future strategy ground.
    """
    def __init__(self):
        self.profiler = CoinProfilingSystem()
        self.transition_engine = TransitionEngine()

    def run_discovery(self, symbol):
        df_dict = {tf: self.profiler.load_data(symbol, tf) for tf in ["15m", "1h", "4h", "1d"]}
        if any(v is None for v in df_dict.values()): return None

        profile = self.profiler.build_profile(symbol)
        
        # Module 2: Transition
        trans_report = self.transition_engine.detect_transition(symbol, df_dict)
        
        # Module 3: Energy Paradox
        energy_engine = EnergyEngine(profile)
        is_paradox = energy_engine.detect_paradox(df_dict)

        # Module 4: Hard Exclusions & Synthesis
        if trans_report['is_transition'] and is_paradox:
            if not self.is_excluded(symbol, df_dict):
                return self.generate_event(symbol, profile, trans_report, is_paradox)
        return None

    def is_excluded(self, symbol, df_dict):
        """Apply global hard filters."""
        # Check for volatility spike (Hard Exclusion)
        df_15m = df_dict['15m']
        last_range = df_15m.iloc[-1]['high'] - df_15m.iloc[-1]['low']
        avg_range = (df_15m.tail(20)['high'] - df_15m.tail(20)['low']).mean()
        if last_range > (3.0 * avg_range): return True # Spike excluded
        
        return False

    def generate_event(self, symbol, profile, trans_report, is_paradox):
        """Formats the DIAMOND_EVENT (STRICT FORMAT)."""
        event = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "involved_timeframes": [tf for tf, res in trans_report['tf_results'].items() if res],
            "character_deviations": "Fast drift anomaly relative to stable slow character profile.",
            "transition_explanation": "Narrative Alignment confirmed: 1D neutral with 4H boundary transition.",
            "energy_paradox_explanation": "Simultaneous Silence (vol) and Tension (pressure) detected.",
            "contextual_confidence": "HIGH" if trans_report['confidence_flags'] == 4 else "MEDIUM"
        }
        return event

if __name__ == "__main__":
    engine = DiamondSynthesisEngine()
    result = engine.run_discovery("BTCUSDT")
    if result:
        print("DIAMOND_EVENT DISCOVERED!")
        print(json.dumps(result, indent=4))
    else:
        print("No Diamond event found. System discipline maintained.")
