import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib

class RallyStoryBuilder:
    """
    Builds RallyStory v1.1.2 objects with Multi-Source TriggerResolver.
    MACX-2100, MACX-2110, MACX-2120
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sl_atr_k = config.get("sl_atr_k", 1.5)
        # MACX-2130: Separated counters by source
        self.total_attempts = 0
        self.source_counts = {
            "join": 0,
            "join_1h_neighbor": 0,
            "derived_15m": 0,
            "fallback": 0,
            "unresolved": 0
        }
        self.diagnostics_log = []
        self.unresolved_times = []
        
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
        Constructs a single RallyStory v1.1.2 object using TriggerResolver v1.
        """
        self.total_attempts += 1
        
        # MACX-2020: Timezone Lock
        event_time_utc = self._ensure_utc(event_row['event_time'])

        # MACX-2100: TriggerResolver v1
        trigger_info = self._resolve_trigger_v1(event_time_utc, event_row, patterns_df)
        
        # Track metrics
        src = trigger_info['trigger_source']
        if src in self.source_counts:
            if trigger_info['trigger'] == "unknown":
                self.source_counts["unresolved"] += 1
                self.unresolved_times.append(event_time_utc.isoformat())
            else:
                self.source_counts[src] += 1
        
        # Get price data
        entry_price = self._get_entry_price(event_time_utc, history_df)
        
        # Risk & Levels
        sl_data = self._calculate_risk(entry_price, event_row)
        levels_data = self._find_nearest_levels(entry_price, levels)
        
        # Stats
        p_stat = self._match_pattern_stats(trigger_info['trigger'], pattern_stats)
        family = self._match_family(event_row.get('rally_bucket'), families)
        
        # MACX-2300: Pre-Pattern Fill (Deterministic)
        pre_pattern = self._build_pre_pattern(
            event_row=event_row,
            trigger_info=trigger_info,
            regime=regime,
            shock=shock,
            levels_data=levels_data,
            sl_data=sl_data
        )

        # Story v1.1.2
        story = {
            "version": "1.1.2",
            "story_id": f"{symbol}_{event_row.get('event_tf', '15m')}_{event_time_utc.strftime('%Y%m%d_%H%M')}",
            "symbol": symbol,
            "pre_pattern": pre_pattern, # MACX-2300
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
                "resolve_confidence": trigger_info.get('resolve_confidence', 0.0), # MACX-2100
                "trigger_time_utc": trigger_info.get('trigger_time_utc'),
                "trigger_hour_key": trigger_info.get('trigger_hour_key'),
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
            "phases": [],
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

    def get_metrics_v2(self) -> Dict[str, Any]:
        """MACX-2130: Detailed source breakdown metrics."""
        total = self.total_attempts
        if total == 0: return {}
        
        resolved_count = total - self.source_counts["unresolved"]
        resolve_rate = resolved_count / total
        
        # Source breakdown percentages
        breakdown = {k: round(v / total, 4) for k, v in self.source_counts.items()}
        
        return {
            "trigger_resolve_rate": round(resolve_rate, 4),
            "trigger_resolve_rate_by_source": breakdown,
            "total_count": total,
            "resolved_count": resolved_count,
            "unresolved_count": self.source_counts["unresolved"],
            "unresolved_event_times": self.unresolved_times[:10],
            "join_coverage": breakdown.get("join", 0) # For backward compat / warn threshold
        }

    def _resolve_trigger_v1(self, event_time_utc, event_row, patterns_df) -> Dict:
        """
        MACX-2100/2110/2120: Deterministic Multi-Source Resolver.
        Order: Join Floor -> Join Ceil -> Join Prev/Next -> Derived 15m -> Fallback
        """
        evt_naive = event_time_utc.tz_localize(None)
        
        # MACX-2110: Join Discovery Keys
        keys = [
            ("join", evt_naive.floor('h')),
            ("join", evt_naive.ceil('h')),
            ("join_1h_neighbor", evt_naive.floor('h') - pd.Timedelta(hours=1)),
            ("join_1h_neighbor", evt_naive.ceil('h') + pd.Timedelta(hours=1))
        ]
        
        if 'datetime' not in patterns_df.columns and 'timestamp' in patterns_df.columns:
            patterns_df['datetime'] = pd.to_datetime(patterns_df['timestamp'], unit='ms')
        pat_dt = patterns_df['datetime'].dt.tz_localize(None)

        attempted_log = []
        for src_label, h_key in keys:
            matches = patterns_df[pat_dt == h_key]
            diff_min = abs((h_key - evt_naive).total_seconds() / 60)
            attempted_log.append({"key": h_key.isoformat(), "diff": round(diff_min, 1)})
            
            if not matches.empty:
                best_match = matches.iloc[0]
                self.diagnostics_log.append({
                    "event_time_utc": event_time_utc.isoformat(),
                    "status": "joined",
                    "source": src_label,
                    "diff_min": round(diff_min, 1),
                    "snapshot_time_utc": h_key.isoformat(),
                    "attempted": attempted_log
                })
                return {
                    "trigger": best_match['trigger'],
                    "trigger_source": src_label,
                    "resolve_confidence": round(1.0 - (diff_min/120.0), 4),
                    "trigger_time_utc": h_key.isoformat(),
                    "trigger_hour_key": h_key.isoformat()
                }

        # MACX-2120: Derived 15m Triggers
        derived_trigger = self._derive_from_15m(event_row)
        if derived_trigger:
            self.diagnostics_log.append({
                "event_time_utc": event_time_utc.isoformat(),
                "status": "derived",
                "source": "derived_15m",
                "trigger": derived_trigger,
                "attempted": attempted_log
            })
            return {
                "trigger": derived_trigger,
                "trigger_source": "derived_15m",
                "resolve_confidence": 0.85 # Strong deterministic rule
            }

        # MACX-2012: Legacy Fallback (MACD KOSU)
        if event_row.get('macd_phase_15m') == 'KOSU':
            self.diagnostics_log.append({
                "event_time_utc": event_time_utc.isoformat(),
                "status": "fallback",
                "source": "fallback",
                "trigger": "macd_bull_cross_fallback",
                "attempted": attempted_log
            })
            return {
                "trigger": "macd_bull_cross_fallback",
                "trigger_source": "fallback",
                "resolve_confidence": 0.5
            }

        # Unresolved
        self.diagnostics_log.append({
            "event_time_utc": event_time_utc.isoformat(),
            "status": "unresolved",
            "source": "unresolved",
            "attempted": attempted_log
        })
        return {
            "trigger": "unknown",
            "trigger_source": "unresolved",
            "resolve_confidence": 0.0
        }

    def _derive_from_15m(self, event_row) -> Optional[str]:
        """MACX-2120: Deterministic rules from features_15m."""
        # 1. MACD Bull Cross (Strong Signal in Mac)
        if event_row.get('macd_phase_15m') in ['KOSU', 'CROSS_BULL']:
            return "derived_macd_bull"
            
        # 2. RSI Recovery (Oversold -> Neutral)
        rsi = event_row.get('rsi_15m', 50)
        if 35 <= rsi <= 55: # Typical ralli start rsi
            return "derived_rsi_neutral_launch"
            
        # 3. Volume Spike
        rel_vol = event_row.get('volume_rel_15m', 1)
        if rel_vol > 2.0:
            return "derived_volume_spike"
            
        return None

    def _ensure_utc(self, dt) -> pd.Timestamp:
        if hasattr(dt, 'tz_localize') and dt.tzinfo is not None:
            return dt.tz_convert('UTC')
        return pd.Timestamp(dt).tz_localize('UTC')

    def _get_trigger_info(self, event_time_utc, patterns_df) -> Dict:
        """Deprecated: Use _resolve_trigger_v1 instead."""
        # This wrapper is for backward compatibility with old calls that don't pass event_row
        # It will only be able to perform join-based resolution, not derived_15m or fallback based on event_row.
        return self._resolve_trigger_v1(event_time_utc, pd.Series(), patterns_df)

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

    def _build_pre_pattern(self, event_row: pd.Series, trigger_info: Dict, regime: Dict, shock: Dict, levels_data: Dict, sl_data: Dict) -> Dict:
        """MACX-2300: Orchestrates deterministic semantic layer generation."""
        return {
            "rhythm": self._build_rhythm(event_row),
            "spirit": self._build_spirit(event_row, trigger_info, regime, shock),
            "meaning": self._build_meaning(trigger_info, regime, levels_data, sl_data)
        }

    def _build_rhythm(self, event_row: pd.Series) -> Dict:
        """MACX-2301: Temporal and phase semantics."""
        bars_total = int(event_row.get('bars_total', 0))
        bars_to_peak = int(event_row.get('bars_to_peak', 0))
        
        # Deterministic summary
        speed = "hızlı" if bars_to_peak < 10 else "istikrarlı" if bars_to_peak < 30 else "yavaş"
        summary = f"Bu ralli {bars_total} barlık bir pencerede, {bars_to_peak} barda zirveye ulaşan {speed} bir ritim sergiledi."
        
        return {
            "summary_tr": summary,
            "phase_sequence": ["Hazırlık", "Kıvılcım", "Kopuş", "Nefes", "Devam"], # Default for V1
            "tempo": {
                "summary_tr": f"Hız: {speed}",
                "bars_total": bars_total,
                "bars_to_peak": bars_to_peak
            }
        }

    def _build_spirit(self, event_row: pd.Series, trigger_info: Dict, regime: Dict, shock: Dict) -> Dict:
        """MACX-2302: Market regime and 'spirit' tags."""
        regime_val = regime.get('regime', 'UNKNOWN')
        tags = ["samimiyet", "ahenk"]
        if regime_val == "TREND":
            tags.append("güçlü_akış")
        elif regime_val == "RANGE":
            tags.append("tepki_alımı")
            
        shock_freq = shock.get('shock_freq', 0)
        risk_level = "düşük" if shock_freq < 0.05 else "orta" if shock_freq < 0.15 else "yüksek"
        
        summary = f"Piyasa şu an {regime_val} rejiminde. {risk_level} şok riski barındıran bir spirit izleniyor."
        
        return {
            "summary_tr": summary,
            "tags": tags,
            "regime_hint_tr": f"Rejim: {regime_val}, Şok Riski: {risk_level}"
        }

    def _build_meaning(self, trigger_info: Dict, regime: Dict, levels_data: Dict, sl_data: Dict) -> Dict:
        """MACX-2303: Thesis and Invalidation rules."""
        trigger = trigger_info.get('trigger', 'unknown')
        support = levels_data.get('nearest_support', 'bulunamadı')
        sl_pct = sl_data.get('stop_loss_pct', 0)
        
        thesis = f"Tetikleyici={trigger} ve rejim={regime.get('regime')} desteğiyle ralli devamı beklenir."
        invalidation = f"Ana destek ({support}) altı kapanış veya %{sl_pct:.2f} stop seviyesinin kırılması hikâyeyi bozar."
        
        return {
            "summary_tr": "Stratejik işlem tezi ve risk limitleri.",
            "thesis_tr": thesis,
            "invalidation_tr": invalidation
        }

    def _match_pattern_stats(self, trigger: str, pattern_stats: List[Dict]) -> Optional[Dict]:
        return next((p for p in pattern_stats if p['trigger'] in trigger or trigger in p['trigger']), None)

    def _match_family(self, bucket: str, families: List[Dict]) -> Optional[Dict]:
        if not bucket: return None
        # Match '5p_10p' with 'rally_5p' etc.
        p_val = bucket.split('p_')[0] + 'p' # '5' -> '5p'
        return next((f for f in families if p_val in f['rally_label']), None)
