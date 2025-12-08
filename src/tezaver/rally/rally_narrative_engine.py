
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

# ==============================================================================
# SCENARIO DEFINITIONS
# ==============================================================================
SCENARIO_DEFINITIONS = {
    "SCENARIO_SURF": {
        "label": "Fırtınada Sörf 🏄‍♂️",
        "desc": "Ana trend düşüşte (Ayı), ama 4 saatlikteki aşırı tepki yüzünden kısa vadeli bir sıçrama.",
        "risk": "High"
    },
    "SCENARIO_BREAKOUT": {
        "label": "Rüzgarı Arkana Al 🌬️",
        "desc": "Tüm zaman dilimleri (1G, 4S) YUKARI yönlü. Trend ile uyumlu güçlü kırılım.",
        "risk": "Low"
    },
    "SCENARIO_EXHAUSTION": {
        "label": "Yorgun Savaşçı 🥵",
        "desc": "Ana trend çok şişmiş (RSI > 70). Bu yükseliş son bir 'tahliye' (Exit Pump) olabilir.",
        "risk": "Medium"
    },
    "SCENARIO_POWER_PUMP": {
        "label": "Güç Patlaması 💥",
        "desc": "15 dakikalıkta hem RSI hem Hacim patlaması yaşandı, ancak ana trend nötr.",
        "risk": "Medium"
    },
    "SCENARIO_NEUTRAL": {
        "label": "Belirsiz Sular 🌊",
        "desc": "Net bir senaryo oluşmadı. İndikatörler karışık sinyaller veriyor.",
        "risk": "Medium"
    }
}

def analyze_scenario(row: pd.Series) -> str:
    """
    Analyzes a single row (rally event) to determine the narrative scenario.
    
    Args:
        row: Pandas Series containing multi-timeframe columns (rsi_1d, trend_soul_4h, etc.)
        
    Returns:
        Scenario ID key (e.g., "SCENARIO_SURF")
    """
    # Extract key metrics with defaults
    rsi_1d = row.get('rsi_1d', 50)
    rsi_4h = row.get('rsi_4h', 50)
    rsi_15m = row.get('rsi_15m', 50)
    
    # Trend Soul (0-100, >60 Bullish, <40 Bearish)
    trend_1d = row.get('trend_soul_1d', 50)
    trend_4h = row.get('trend_soul_4h', 50)
    
    # 1. SCENARIO_EXHAUSTION (Overbought on Daily)
    if rsi_1d > 70:
        return "SCENARIO_EXHAUSTION"
        
    # 2. SCENARIO_BREAKOUT (Trend Alignment)
    # Daily Bullish AND 4H Bullish
    if trend_1d > 60 and trend_4h > 55:
        return "SCENARIO_BREAKOUT"
        
    # 3. SCENARIO_SURF (Counter-Trend Scalp)
    # Daily Bearish BUT 4H Oversold or very low
    if trend_1d < 40 and (rsi_4h < 35 or trend_4h < 30):
        # Yet 15m is pumping (implied by this being a rally event)
        return "SCENARIO_SURF"
        
    # 4. SCENARIO_POWER_PUMP (Strong local momentum)
    if rsi_15m > 70:
         return "SCENARIO_POWER_PUMP"
         
    # Fallback
    return "SCENARIO_NEUTRAL"

def enrich_with_narratives(df_events: pd.DataFrame) -> pd.DataFrame:
    """
    Enriches the events DataFrame with scenario columns.
    
    Adds:
    - scenario_id
    - scenario_label
    - narrative_tr
    """
    if df_events.empty:
        return df_events
        
    # Apply analysis row by row
    scenario_ids = df_events.apply(analyze_scenario, axis=1)
    
    # Map results to new columns
    df_events['scenario_id'] = scenario_ids
    df_events['scenario_label'] = scenario_ids.map(lambda x: SCENARIO_DEFINITIONS[x]['label'])
    df_events['narrative_tr'] = scenario_ids.map(lambda x: SCENARIO_DEFINITIONS[x]['desc'])
    df_events['scenario_risk'] = scenario_ids.map(lambda x: SCENARIO_DEFINITIONS[x]['risk'])
    
    return df_events
