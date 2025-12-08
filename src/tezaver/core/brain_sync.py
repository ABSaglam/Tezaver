"""
CoinState Brain Sync Module (M7).
Synchronizes "wisdom" (pattern stats, volatility) into the central CoinState model.

Tezaver Philosophy:
- "CoinState, Tezaver Mac'in bilinç yüzeyi, wisdom JSON'ları ise bilinçaltıdır."
- "Bu katman, arka plandaki bilgelik ile ön yüz panelini senkronize eder."
"""

import json
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import sys

# Adjust path to allow imports if run directly or as module
from tezaver.core import state_store
from tezaver.core.models import CoinState, DataState
from tezaver.core import coin_cell_paths
from tezaver.wisdom.pattern_stats import (
    get_coin_profile_dir,
    get_pattern_stats_file,
    get_trustworthy_patterns_file,
    get_betrayal_patterns_file,
    get_volatility_signature_file,
)
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

# --- Helpers ---

def load_json_if_exists(path: Path) -> Any | None:
    """Loads JSON file if it exists, otherwise returns None."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {path}: {e}", exc_info=True)
        return None

def get_latest_feature_timestamp(symbol: str, timeframes: List[str]) -> Optional[datetime]:
    """
    Finds the latest timestamp across all feature files for a symbol.
    """
    latest_dt = None
    data_dir = coin_cell_paths.get_coin_data_dir(symbol)
    
    for tf in timeframes:
        feature_file = data_dir / f"features_{tf}.parquet"
        if not feature_file.exists():
            continue
            
        try:
            # Read only columns needed to find max time
            # If pyarrow is used, we can read metadata or just the column
            # For simplicity with pandas read_parquet:
            df = pd.read_parquet(feature_file, columns=["timestamp", "datetime"])
            
            current_max = None
            if "datetime" in df.columns and not df["datetime"].empty:
                # Assuming datetime column is datetime objects or strings
                current_max = pd.to_datetime(df["datetime"]).max()
            elif "timestamp" in df.columns and not df["timestamp"].empty:
                # Timestamp is usually ms epoch
                current_max = pd.to_datetime(df["timestamp"].max(), unit="ms")
                
            if current_max is not None:
                # Ensure timezone awareness if possible, or naive. 
                # CoinState usually expects naive or consistent UTC.
                # If current_max is tz-aware, convert to UTC then naive or keep as is.
                # Let's keep it simple: if latest_dt is None or current > latest
                if latest_dt is None or current_max > latest_dt:
                    latest_dt = current_max
                    
        except Exception as e:
            logger.error(f"Error reading features for {symbol} {tf}: {e}", exc_info=True)
            continue
            
    return latest_dt


# --- Score Computation ---

def compute_scores_from_wisdom(symbol: str, timeframes: List[str]) -> Dict[str, Any]:
    """
    Reads wisdom files and computes summary scores for CoinState.

    Güncellenmiş mantık:
    - trend_soul_score: En iyi trigger'ların güven skoruna bakar (0-100).
    - harmony_score: Güvenilir trigger oranını temsil eder (0-100).
    - opportunity_score:
        * Artık sadece trend_soul_score'a değil, aynı zamanda harmony_score'a da dayanır.
        * base_opp = 0.7 * trend_soul_score + 0.3 * harmony_score
        * Sonra vol_factor ve risk_penalty ile ayarlanır.
    """
    # Load Wisdom
    pattern_stats = load_json_if_exists(get_pattern_stats_file(symbol)) or []
    trustworthy = load_json_if_exists(get_trustworthy_patterns_file(symbol)) or []
    betrayal = load_json_if_exists(get_betrayal_patterns_file(symbol)) or []
    vol_sig = load_json_if_exists(get_volatility_signature_file(symbol)) or {}
    
    # M15: Load regime and shock profiles
    profile_dir = get_coin_profile_dir(symbol)
    regime_profile = load_json_if_exists(profile_dir / "regime_profile.json") or {}
    shock_profile = load_json_if_exists(profile_dir / "shock_profile.json") or {}
    
    # Defaults
    sample_count_total = 0
    avg_trust_score = 0.0
    best_trust_score = 0.0
    trustworthy_ratio = 0.0
    betrayal_ratio = 0.0
    
    if pattern_stats:
        df_stats = pd.DataFrame(pattern_stats)
        if not df_stats.empty:
            sample_count_total = df_stats["sample_count"].sum()
            avg_trust_score = df_stats["trust_score"].mean()
            best_trust_score = df_stats["trust_score"].max()
            
            total_patterns = len(pattern_stats)
            trustworthy_ratio = len(trustworthy) / max(1, total_patterns)
            betrayal_ratio = len(betrayal) / max(1, total_patterns)
            
    # Volatility
    volatility_class = vol_sig.get("volatility_class", "unknown")
    vol_spike_freq = vol_sig.get("vol_spike_freq", None)
    vol_dry_freq = vol_sig.get("vol_dry_freq", None)
    
    # --- Calculate Scores ---
    
    # Trend Soul Score (0-100)
    trend_soul_score = int(round(best_trust_score * 100))
    
    # Harmony Score (0-100) -> Güvenilir trigger oranı
    harmony_score = int(round(trustworthy_ratio * 100))
    
    # Betrayal Score (0-100) -> İhanetkâr trigger oranı
    betrayal_score = int(round(betrayal_ratio * 100))
    
    # Volume Trust (0-100)
    volume_trust = 0
    if vol_spike_freq is not None and vol_dry_freq is not None:
        # Daha sık spike, daha az dry => daha yüksek samimiyet
        raw_vol = 0.6 * vol_spike_freq + 0.4 * (1.0 - vol_dry_freq)
        volume_trust = int(round(raw_vol * 100))
        
    # Risk Level
    risk_level = "medium"
    if volatility_class == "Extreme":
        risk_level = "high"
    elif volatility_class == "High":
        risk_level = "high" if betrayal_score > 50 else "medium"
    elif volatility_class == "Medium":
        risk_level = "medium"
    elif volatility_class in ["Low", "unknown"]:
        risk_level = "medium" if betrayal_score > 30 else "low"
        
    # Pattern Status
    if sample_count_total == 0:
        pattern_status = "none"
    elif sample_count_total < 200:
        pattern_status = "basic"
    else:
        pattern_status = "trained"
        
    # Opportunity Score (0-100)
    # Eski: base_opp = trend_soul_score
    # Yeni: trend ruhu + ahenk karışımı
    base_opp = 0.7 * float(trend_soul_score) + 0.3 * float(harmony_score)
    
    # Volatilite faktörü (oynaklık, fırsatı da getirir riski de)
    vol_factor = 1.0
    if volatility_class == "Low":
        vol_factor = 0.7
    elif volatility_class == "Medium":
        vol_factor = 1.0
    elif volatility_class == "High":
        vol_factor = 1.1
    elif volatility_class == "Extreme":
        vol_factor = 1.2
    
    # Risk cezası (risk yüksekse fırsatı bir miktar kıs)
    risk_penalty = 1.0
    if risk_level == "high":
        risk_penalty = 0.8
    elif risk_level == "medium":
        risk_penalty = 1.0
    elif risk_level == "low":
        risk_penalty = 1.1
    
    raw_opp = (base_opp * vol_factor * risk_penalty) / 1.2
    opportunity_score = int(max(0, min(100, round(raw_opp))))
    
    # Self Trust Score
    self_trust_score = int(round(avg_trust_score * 100))
    
    # Persona Summary
    persona_summary = []
    
    # Volatility Tag
    if volatility_class == "Low":
        persona_summary.append("Sakin")
    elif volatility_class == "Medium":
        persona_summary.append("Dengeli")
    elif volatility_class == "High":
        persona_summary.append("Dalgalı")
    elif volatility_class == "Extreme":
        persona_summary.append("Fırtınalı")
    
    # Pattern Tags
    if trustworthy_ratio > 0.5:
        persona_summary.append("Güvenilir Triggerlar")
    if betrayal_ratio > 0.5:
        persona_summary.append("İhanetkâr Triggerlar")
    
    # Soul Tags
    if trend_soul_score > 70:
        persona_summary.append("Trend Dostu")
    if trend_soul_score < 30:
        persona_summary.append("Kararsız Ruh")
    
    # M15: Regime and Shock Risk
    regime = regime_profile.get("regime", "unknown")
    shock_freq = shock_profile.get("shock_freq", 0.0)
    # Scale shock_freq to 0-100 (assume >0.2 is very high risk)
    shock_risk = int(round(max(0.0, min(1.0, shock_freq * 5.0)) * 100))
    
    return {
        "trend_soul_score": trend_soul_score,
        "harmony_score": harmony_score,
        "betrayal_score": betrayal_score,
        "volume_trust": volume_trust,
        "risk_level": risk_level,
        "pattern_status": pattern_status,
        "opportunity_score": opportunity_score,
        "self_trust_score": self_trust_score,
        "persona_summary": persona_summary,
        "regime": regime,
        "shock_risk": shock_risk,
    }


# --- Sync Logic ---

def sync_coinstate_for_symbol(symbol: str, timeframes: List[str]) -> None:
    """
    Updates the CoinState for a single symbol using wisdom data.
    """
    # 1. Load State
    coin_states = state_store.load_coin_states()
    state = state_store.find_coin_state(coin_states, symbol)
    
    if not state:
        state = CoinState(symbol=symbol)
        coin_states.append(state)
        
    # 2. Check Data Freshness
    last_update = get_latest_feature_timestamp(symbol, timeframes)
    
    if last_update is None:
        state.data_state = DataState.MISSING
        state.indicators_ready = False
        # Save and exit
        state_store.save_coin_states(coin_states)
        return
        
    # 3. Compute Scores
    scores = compute_scores_from_wisdom(symbol, timeframes)
    
    # 4. Update State
    state.last_update = last_update
    state.data_state = DataState.FRESH # Assuming fresh if we have data
    state.indicators_ready = True
    
    state.trend_soul_score = scores["trend_soul_score"]
    state.harmony_score = scores["harmony_score"]
    state.betrayal_score = scores["betrayal_score"]
    state.volume_trust = scores["volume_trust"]
    state.risk_level = scores["risk_level"]
    state.pattern_status = scores["pattern_status"]
    state.opportunity_score = scores["opportunity_score"]
    state.self_trust_score = scores["self_trust_score"]
    state.persona_summary = scores["persona_summary"]
    
    # M15: Regime and Shock Risk
    state.regime = scores.get("regime", "unknown")
    state.shock_risk = scores.get("shock_risk", 0)
    
    # 5. Export Ready Check
    # Ready if data exists and wisdom files exist (implied by non-zero scores or just file existence)
    # Let's check file existence explicitly for robustness
    has_wisdom = (
        get_pattern_stats_file(symbol).exists() and 
        get_volatility_signature_file(symbol).exists()
    )
    state.export_ready = (last_update is not None) and has_wisdom
    
    # 6. Save
    state_store.save_coin_states(coin_states)


def sync_all_coinstates(symbols: List[str], timeframes: List[str]) -> None:
    """
    Syncs CoinStates for all symbols.
    """
    # We load and save inside the loop (inefficient but safe) or load once, update all, save once.
    # The helper sync_coinstate_for_symbol does load/save.
    # To be more efficient, we could refactor, but for now let's just call the helper.
    # It's safer to ensure persistence after each coin.
    
    for symbol in symbols:
        print(f"Syncing brain for {symbol}...")
        try:
            sync_coinstate_for_symbol(symbol, timeframes)
        except Exception as e:
            print(f"Failed to sync {symbol}: {e}")
            continue
