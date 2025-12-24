"""
Deep Narrative Engine
=====================

Generates rich, context-aware stories for bundles by analyzing:
1. Multi-Timeframe Context (Signal TF vs Higher TF)
2. Indicator Dynamics (RSI slope, MACD evolution, Volume character)
3. EMA Structures
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional
from tezaver.core import coin_cell_paths

# Mapping Signal TF -> Higher TF
HTF_MAP = {
    "15m": "4h",
    "1h": "4h", # Or 1d, but 4h is often immediate context
    "4h": "1d"
}

class DeepNarrativeService:
    def __init__(self):
        pass

    def generate_story(self, symbol: str, timeframe: str, event_time_iso: str) -> Dict[str, Any]:
        """
        Analyzes the market state around the event time and generates a narrative.
        
        Returns:
            Dict with keys: 'label', 'desc', 'risk', 'details'
        """
        if not event_time_iso:
            return self._neutral_story("Missing Event Time")
            
        try:
            event_dt = pd.to_datetime(event_time_iso)
        except:
            return self._neutral_story("Invalid Date")

        # 1. Load Data (Signal TF)
        df = self._load_data(symbol, timeframe)
        if df.empty:
            return self._neutral_story("No History Data")
            
        # Locate Event Bar (or closest before)
        # Ensure index is datetime
        if 'open_time' in df.columns:
             df = df.set_index('open_time')
        elif df.index.name != 'open_time':
             # Try to find a time column
             if 'date' in df.columns:
                 df = df.set_index('date')
             elif 'timestamp' in df.columns:
                 df = df.set_index('timestamp')
             else:
                 # Assume index is time if it is DatetimeIndex
                 if not isinstance(df.index, pd.DatetimeIndex):
                      return self._neutral_story("No Time Index")
             
        # Find row closest to/at event_time (using 'asof' logic or exact match)
        # Since these are open times, exact match is preferred if aligned.
        try:
             # get location
             target_idx = df.index.get_indexer([event_dt], method='pad')[0]
             if target_idx == -1:
                 return self._neutral_story("Event before history")
        except:
            return self._neutral_story("Date Lookup Failed")
            
        # Slice recent history (e.g. last 20 bars relative to event)
        # We need enough bars for slope and EMA calculation if not pre-calc
        # Assume indicators are pre-calculated in history? 
        # Usually CoinCell history has indicators. If not, we compute on fly. 
        # Ideally, we assume basic columns exist: 'close', 'volume', 'rsi', 'macd', 'ema50' etc.
        # If columns missing, we can compute. For robustness, let's assume valid CoinCell history.
        
        ref_row = df.iloc[target_idx]
        recent_df = df.iloc[max(0, target_idx-5):target_idx+1] # Last 6 bars including current
        
        # 2. Analyze Indicators (Signal TF)
        
        # RSI Dynamics
        rsi_val = ref_row.get('rsi', 50)
        rsi_desc = self._analyze_rsi(recent_df)
        
        # Volume Character
        vol_desc = self._analyze_volume(df, target_idx)
        
        # MACD State
        macd_desc = self._analyze_macd(recent_df)
        
        # 3. Analyze HTF (Context)
        htf = HTF_MAP.get(timeframe)
        htf_desc = "Neutral"
        if htf:
            df_htf = self._load_data(symbol, htf)
            if not df_htf.empty:
                # Find HTF bar covering this event time
                # HTF open_time <= event_time < HTF close_time
                if df_htf.index.name != 'open_time':
                    df_htf = df_htf.set_index('open_time')
                
                try:
                    h_idx = df_htf.index.get_indexer([event_dt], method='pad')[0]
                    if h_idx != -1:
                        htf_row = df_htf.iloc[h_idx]
                        htf_desc = self._analyze_htf_trend(htf_row)
                except:
                    pass

        # 4. Synthesize Story
        # Logic to combine these into a coherent label and description
        
        story_label = f"{htf_desc} {self._get_base_label(rsi_val)}"
        
        description = (
            f"Context ({htf}): {htf_desc}. "
            f"Signal ({timeframe}): RSI is {rsi_desc} ({rsi_val:.1f}). "
            f"Volume is {vol_desc}. "
            f"MACD indicates {macd_desc}."
        )
        
        return {
            "label": story_label,
            "desc": description,
            "risk": "High" if "Bear" in htf_desc and "Bull" in story_label else "Medium", # simplistic risk
            "details": {
                "rsi_slope": rsi_desc,
                "volume": vol_desc,
                "htf_trend": htf_desc
            }
        }

    def _load_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        path = coin_cell_paths.get_history_file(symbol, timeframe)
        if path.exists():
            try:
                df = pd.read_parquet(path)
                if 'open_time' in df.columns:
                     df['open_time'] = pd.to_datetime(df['open_time'])
                return df
            except:
                return pd.DataFrame()
        return pd.DataFrame()

    def _analyze_rsi(self, recent_df: pd.DataFrame) -> str:
        if 'rsi' not in recent_df.columns:
            return "Unknown"
        
        # Basic slope
        vals = recent_df['rsi'].values
        if len(vals) < 2:
            return "Stable"
            
        change = vals[-1] - vals[0]
        if change > 5:
            return "Rising Agessively 🚀"
        elif change > 2:
            return "Rising 📈"
        elif change < -5:
            return "Diving 📉"
        elif change < -2:
            return "Falling"
        return "Flat"

    def _analyze_volume(self, full_df: pd.DataFrame, target_idx: int) -> str:
        if 'volume' not in full_df.columns:
            return "Normal"
            
        # SMA 20 Volume
        start = max(0, target_idx - 20)
        window = full_df.iloc[start:target_idx]['volume']
        if window.empty:
            return "Normal"
            
        avg_vol = window.mean()
        curr_vol = full_df.iloc[target_idx]['volume']
        
        if avg_vol == 0: return "Normal"
        
        ratio = curr_vol / avg_vol
        
        if ratio > 3.0:
            return "Explosive (3x) 💥"
        elif ratio > 1.5:
            return "High"
        elif ratio < 0.5:
            return "Dry"
        return "Normal"

    def _analyze_macd(self, recent_df: pd.DataFrame) -> str:
        # Assuming columns 'macd', 'macd_signal', 'macd_hist'
        # If not present, simplistic default
        cols = recent_df.columns
        if not all(k in cols for k in ['macd', 'macd_signal', 'macd_hist']):
            return "Unclear"
            
        hist = recent_df['macd_hist'].values
        if len(hist) < 2: return "Stable"
        
        curr = hist[-1]
        prev = hist[-2]
        
        if curr > 0 and curr > prev:
            return "Strong Bullish Momentum (Dark Green)"
        elif curr > 0 and curr < prev:
            return "Weakening Bullish (Light Green)"
        elif curr < 0 and curr < prev:
            return "Strong Bearish Momentum (Dark Red)"
        elif curr < 0 and curr > prev:
            return "Weakening Bearish (Pink)"
            
        return "Stable"

    def _analyze_htf_trend(self, row: pd.Series) -> str:
        # Use EMA or Trend Soul if available
        if 'trend_soul' in row:
            val = row['trend_soul']
            if val > 60: return "Bullish Trend"
            if val < 40: return "Bearish Trend"
            return "Neutral Trend"
            
        # Fallback to EMA alignment
        if 'ema50' in row and 'close' in row:
            if row['close'] > row['ema50']:
                return "Bullish (Above EMA50)"
            return "Bearish (Below EMA50)"
            
        return "Neutral"

    def _get_base_label(self, rsi: float) -> str:
        if rsi > 70: return "Overbought"
        if rsi < 30: return "Oversold"
        if rsi > 50: return "Bullish"
        return "Bearish"

    def _neutral_story(self, reason: str) -> Dict[str, Any]:
        return {
            "label": "Analysis Failed",
            "desc": f"Could not generate story: {reason}",
            "risk": "Unknown"
        }
