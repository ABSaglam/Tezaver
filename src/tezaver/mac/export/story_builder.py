import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib

class RallyStoryBuilder:
    """
    Builds RallyStory v1.1.1 objects by joining multi-source data.
    MACX-2011, MACX-2012
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sl_atr_k = config.get("sl_atr_k", 1.5)
        # MACX-2011/2012: Counter breakdown
        self.total_attempts = 0
        self.join_matched_count = 0
        self.fallback_used_count = 0
        self.diagnostics_log = [] # List of {event_time, status, diff_min, snapshot_time}
        
    def build_story(self, 
                    symbol: str,
                    event_row: pd.Series, 
                    history_df: pd.DataFrame,
                    patterns_df: pd.DataFrame,
                    levels: List[Dict],
                    regime: Dict,
                    shock: Dict,
                    pattern_stats: List[Dict],
                    families: List[Dict]) -> Dict[str, Any]:
        """
        Constructs a single RallyStory v1.1 object with diagnostic info.
        """
        self.total_attempts += 1
        
        # MACX-2020: Timezone Lock - Ensure everything is UTC or naive but treated as UTC
        event_time = event_row['event_time']
        if hasattr(event_time, 'tz_localize') and event_time.tzinfo is not None:
            event_time_utc = event_time.tz_convert('UTC')
        else:
            event_time_utc = pd.Timestamp(event_time).tz_localize('UTC')

        # MACX-2011: Event -> Trigger Join Alignment
        trigger_info = self._get_trigger_info(event_time_utc, patterns_df)
        
        # MACX-2012: Update metrics based on meaningful resolution
        if trigger_info['trigger_source'] == "join":
            self.join_matched_count += 1
        elif trigger_info['trigger_source'] == "fallback":
            # Check if we have a valid fallback reason
            if event_row.get('macd_phase_15m') == 'KOSU':
                trigger_info['trigger'] = "macd_bull_cross_fallback"
                self.fallback_used_count += 1 # Meaningful fallback
            else:
                trigger_info['trigger'] = "unknown"
                # Do NOT increment fallback_used_count for unknown
        
        # Get price data at event
        entry_price = self._get_entry_price(event_time, history_df)
        
        # MACX-1040: SL Calculation
        sl_data = self._calculate_risk(entry_price, event_row)
        
        # Find levels
        levels_data = self._find_nearest_levels(entry_price, levels)
        
        # Match pattern stats for trust score
        p_stat = self._match_pattern_stats(trigger_info['trigger'], pattern_stats)
        
        # Match family
        family = self._match_family(event_row.get('rally_bucket'), families)
        
        # MACX-2030: Expanded v1.1 Story
        story = {
            "version": "1.1.1",
            "story_id": f"{symbol}_{event_row.get('event_tf', '15m')}_{event_time_utc.strftime('%Y%m%d_%H%M')}",
            "symbol": symbol,
            "context": {
                "timeframe": event_row.get('event_tf', '15m'),
                "regime": regime.get('regime'),
                "shock_risk": shock.get('shock_freq'),
                "trendiness_score": regime.get('trendiness_score'),
                "chop_score": regime.get('chop_score'),
                "scenario_id": event_row.get('scenario_id'),
                "scenario_risk": event_row.get('scenario_risk')
            },
            "entry": {
                "event_time_utc": event_time_utc.isoformat(),
                "entry_price": entry_price,
                "trigger": trigger_info['trigger'],
                "trigger_source": trigger_info['trigger_source'],
                "trigger_time_utc": trigger_info.get('trigger_time_utc'),
                "trigger_hour_key": trigger_info.get('trigger_hour_key'), # MACX-2011 Debug
                "rsi_15m": round(event_row.get('rsi_15m', 0), 2),
                "macd_phase_15m": event_row.get('macd_phase_15m'),
                "volume_rel_15m": round(event_row.get('volume_rel_15m', 0), 2),
                "trust_score": p_stat.get('trust_score') if p_stat else None,
                "levels": levels_data
            },
            "target": {
                "expected_gain_pct": p_stat.get('avg_future_max_gain_pct') if p_stat else event_row.get('future_max_gain_pct'),
                "hit_5p_rate": p_stat.get('hit_5p_rate') if p_stat else None,
                "hit_10p_rate": p_stat.get('hit_10p_rate') if p_stat else None,
                "bars_to_peak": int(event_row.get('bars_to_peak', 0))
            },
            "risk": sl_data,
            "family": {
                "family_id": family.get('rally_family_id') if family else None,
                "historical_success": family.get('trust_score') if family else None,
                "sample_count": family.get('sample_count') if family else None,
                "avg_win_rate": family.get('avg_win_rate') if family else None
            },
            "quality": {
                "quality_score": event_row.get('quality_score'),
                "rally_shape": event_row.get('rally_shape'),
                "trend_efficiency": round(event_row.get('trend_efficiency', 0), 4) if pd.notna(event_row.get('trend_efficiency')) else None,
                "narrative_tr": event_row.get('narrative_tr')
            },
            "phases": [], # MACX-2030 placeholder
            "evidence": {
                "source_event": {
                    "symbol": event_row.get('symbol'),
                    "event_time": event_row['event_time'].isoformat(),
                    "rally_bucket": event_row.get('rally_bucket'),
                    "future_max_gain_pct": round(event_row.get('future_max_gain_pct', 0), 4)
                },
                "event_row_hash": hashlib.sha256(str(event_row.to_dict()).encode()).hexdigest(),
                "source_tf": event_row.get('event_tf', '15m')
            }
        }
        return story

    def get_metrics(self) -> Dict[str, Any]:
        """MACX-2012: Separated metrics."""
        total = self.total_attempts
        join_cov = self.join_matched_count / total if total > 0 else 0
        resolve_rate = (self.join_matched_count + self.fallback_used_count) / total if total > 0 else 0
        
        return {
            "join_coverage": round(join_cov, 4),
            "join_total_attempts": total,
            "join_matched_count": self.join_matched_count,
            "fallback_used_count": self.fallback_used_count,
            "trigger_resolve_rate": round(resolve_rate, 4),
            "join_unmatched_count": total - self.join_matched_count
        }

    def _get_trigger_info(self, event_time_utc, patterns_df) -> Dict:
        """MACX-2011: Join Alignment (Strict Nearest within 30m)."""
        evt_naive = event_time_utc.tz_localize(None)
        
        if 'datetime' not in patterns_df.columns and 'timestamp' in patterns_df.columns:
            patterns_df['datetime'] = pd.to_datetime(patterns_df['timestamp'], unit='ms')
        
        pat_dt = patterns_df['datetime'].dt.tz_localize(None)
        
        # Find closest snapshot in the entire patterns_df
        diff_min = 0
        snapshot_time = None
        status = "unmatched"
        matches = pd.DataFrame()

        if not patterns_df.empty:
            diffs = (pat_dt - evt_naive).abs()
            min_diff_idx = diffs.idxmin()
            min_diff = diffs[min_diff_idx]
            
            diff_min = min_diff.total_seconds() / 60
            snapshot_time = pat_dt.iloc[min_diff_idx]

            if min_diff <= pd.Timedelta(minutes=30):
                matches = patterns_df.iloc[[min_diff_idx]]
                status = "joined"
            else:
                status = "unmatched"

        # Log diagnostics
        self.diagnostics_log.append({
            "event_time_utc": event_time_utc.isoformat(),
            "status": status,
            "diff_min": round(diff_min, 1),
            "snapshot_time_utc": snapshot_time.isoformat() if snapshot_time else None,
            "hour_key": evt_naive.round('h').isoformat() # Best hour guess for debug
        })

        if not matches.empty:
            best_match = matches.iloc[0]
            trig_dt = best_match['datetime']
            trig_utc = trig_dt.tz_localize('UTC').isoformat() if trig_dt.tzinfo is None else trig_dt.tz_convert('UTC').isoformat()

            return {
                "trigger": best_match['trigger'],
                "trigger_source": "join",
                "trigger_time_utc": trig_utc,
                "trigger_hour_key": snapshot_time.isoformat()
            }
            
        return {
            "trigger": "unknown",
            "trigger_source": "fallback",
            "trigger_hour_key": evt_naive.round('h').isoformat()
        }

    def _get_entry_price(self, event_time, history_df) -> float:
        evt_naive = event_time.tz_localize(None)
        
        if 'datetime' not in history_df.columns and 'timestamp' in history_df.columns:
            history_df['datetime'] = pd.to_datetime(history_df['timestamp'], unit='ms')
            
        hist_dt = history_df['datetime'].dt.tz_localize(None)
        row = history_df[hist_dt == evt_naive]
        if not row.empty:
            return float(row.iloc[0]['close'])
        return 0.0

    def _calculate_risk(self, entry_price: float, event_row: pd.Series) -> Dict:
        atr_pct = event_row.get('atr_pct_15m', 0)
        sl_pct = self.sl_atr_k * atr_pct
        sl_price = entry_price * (1 - sl_pct / 100)
        
        return {
            "stop_loss_price": round(sl_price, 2),
            "stop_loss_pct": round(sl_pct, 4),
            "atr_pct_15m": round(atr_pct, 4),
            "sl_k_multiplier": self.sl_atr_k,
            "pre_peak_drawdown_pct": round(event_row.get('pre_peak_drawdown_pct', 0), 4) if pd.notna(event_row.get('pre_peak_drawdown_pct')) else None
        }

    def _find_nearest_levels(self, entry_price: float, levels: List[Dict]) -> Dict:
        supports = [l for l in levels if l['type'] == 'support' and l['level_price'] < entry_price]
        supports.sort(key=lambda x: x['level_price'], reverse=True)
        
        resistances = [l for l in levels if l['type'] == 'resistance' and l['level_price'] > entry_price]
        resistances.sort(key=lambda x: x['level_price'])
        
        return {
            "nearest_support": supports[0]['level_price'] if supports else None,
            "support_strength": supports[0]['strength_score'] if supports else None,
            "nearest_resistance": resistances[0]['level_price'] if resistances else None,
            "resistance_strength": resistances[0]['strength_score'] if resistances else None
        }

    def _match_pattern_stats(self, trigger: str, pattern_stats: List[Dict]) -> Optional[Dict]:
        return next((p for p in pattern_stats if p['trigger'] in trigger or trigger in p['trigger']), None)

    def _match_family(self, bucket: str, families: List[Dict]) -> Optional[Dict]:
        if not bucket: return None
        # Match '5p_10p' with 'rally_5p' etc.
        p_val = bucket.split('p_')[0] + 'p' # '5' -> '5p'
        return next((f for f in families if p_val in f['rally_label']), None)
