"""
Coin DNA Analyzer - Character-Based Classification
===================================================
Analyzes historical behavior of each coin to assign a "character type".
Uses metrics like: ATR%, Trend Duration, Spike Frequency, BTC Correlation.

Character Types:
- ATLAS: Stable giants, slow but steady
- ROKET: Explosive pumps, fast crashes
- TAKIPCI: Follows BTC closely
- ISYANKAR: Independent movement from BTC
- UYUYAN: Long dormancy, sudden awakening
- HAYALET: Low liquidity, unpredictable
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from tezaver.core import config, coin_cell_paths
import json


@dataclass
class CoinDNA:
    """DNA profile for a single coin."""
    symbol: str
    
    # Volatility Profile
    avg_atr_pct: float        # Average daily ATR as % of price
    max_daily_move: float     # Largest single-day move ever
    spike_frequency: int      # Days with >10% move in history
    
    # Trend Profile
    avg_trend_duration: float # Average days a trend lasts
    trend_consistency: float  # % of time in clear trend vs ranging
    
    # Correlation Profile
    btc_correlation: float    # Pearson correlation with BTC daily returns
    
    # Volume Profile
    avg_volume_stability: float # Coefficient of variation (std/mean)
    volume_spike_frequency: int # Days with volume > 5x average
    
    # Recovery Profile
    avg_recovery_days: float  # Average days to recover from -20% drop
    
    # Classification
    character: str            # Assigned character type
    

class CoinDNAAnalyzer:
    """Analyzes coin behavior and assigns character types."""
    
    def __init__(self):
        self.coins = config.DEFAULT_COINS
        self.btc_returns = None
        self._load_btc_data()
        
    def _load_btc_data(self):
        """Load BTC data for correlation calculation."""
        btc_path = coin_cell_paths.get_history_file("BTCUSDT", "1d")
        if btc_path.exists():
            df = pd.read_parquet(btc_path)
            df['returns'] = df['close'].pct_change()
            self.btc_returns = df['returns'].values
            
    def analyze_coin(self, symbol: str) -> Optional[CoinDNA]:
        """Analyze a single coin and return its DNA profile."""
        try:
            path = coin_cell_paths.get_history_file(symbol, "1d")
            if not path.exists():
                return None
            
            df = pd.read_parquet(path)
            if len(df) < 100:
                return None
                
            # Calculate daily returns
            df['returns'] = df['close'].pct_change()
            df['daily_move'] = (df['high'] - df['low']) / df['open']
            
            # ATR%
            df['tr'] = np.maximum(
                df['high'] - df['low'],
                np.maximum(
                    abs(df['high'] - df['close'].shift(1)),
                    abs(df['low'] - df['close'].shift(1))
                )
            )
            df['atr'] = df['tr'].rolling(14).mean()
            df['atr_pct'] = (df['atr'] / df['close']) * 100
            avg_atr_pct = df['atr_pct'].mean()
            
            # Max daily move
            max_daily_move = df['daily_move'].max() * 100
            
            # Spike frequency (>10% daily move)
            spike_frequency = (df['daily_move'] > 0.10).sum()
            
            # Trend analysis (using EMA20 vs EMA50)
            df['ema20'] = df['close'].ewm(span=20).mean()
            df['ema50'] = df['close'].ewm(span=50).mean()
            df['trend'] = np.where(df['ema20'] > df['ema50'], 1, -1)
            df['trend_change'] = df['trend'] != df['trend'].shift(1)
            
            # Average trend duration
            trend_changes = df['trend_change'].sum()
            avg_trend_duration = len(df) / max(trend_changes, 1)
            
            # Trend consistency (% of time in clear trend)
            df['trend_strength'] = abs(df['ema20'] - df['ema50']) / df['close']
            trend_consistency = (df['trend_strength'] > 0.02).mean() * 100
            
            # BTC Correlation
            btc_correlation = 0.0
            if self.btc_returns is not None:
                min_len = min(len(df['returns'].dropna()), len(self.btc_returns))
                if min_len > 30:
                    coin_ret = df['returns'].dropna().values[-min_len:]
                    btc_ret = self.btc_returns[-min_len:]
                    # Handle NaN
                    mask = ~(np.isnan(coin_ret) | np.isnan(btc_ret))
                    if mask.sum() > 30:
                        btc_correlation = np.corrcoef(coin_ret[mask], btc_ret[mask])[0, 1]
                        
            # Volume stability
            vol_mean = df['volume'].mean()
            vol_std = df['volume'].std()
            avg_volume_stability = vol_std / vol_mean if vol_mean > 0 else 0
            
            # Volume spike frequency
            df['vol_sma50'] = df['volume'].rolling(50).mean()
            volume_spike_frequency = (df['volume'] > df['vol_sma50'] * 5).sum()
            
            # Recovery analysis
            df['drawdown'] = (df['close'] - df['close'].cummax()) / df['close'].cummax()
            big_drops = df[df['drawdown'] <= -0.20].index.tolist()
            recovery_days = []
            for drop_idx in big_drops[:10]:  # Sample first 10
                drop_pos = df.index.get_loc(drop_idx)
                drop_price = df.iloc[drop_pos]['close']
                # Find when it recovered
                for i in range(drop_pos + 1, min(drop_pos + 60, len(df))):
                    if df.iloc[i]['close'] >= drop_price:
                        recovery_days.append(i - drop_pos)
                        break
            avg_recovery_days = np.mean(recovery_days) if recovery_days else 60.0
            
            # Classify character
            character = self._classify_character(
                avg_atr_pct, max_daily_move, spike_frequency,
                avg_trend_duration, trend_consistency, btc_correlation,
                avg_volume_stability, volume_spike_frequency, avg_recovery_days
            )
            
            return CoinDNA(
                symbol=symbol,
                avg_atr_pct=avg_atr_pct,
                max_daily_move=max_daily_move,
                spike_frequency=spike_frequency,
                avg_trend_duration=avg_trend_duration,
                trend_consistency=trend_consistency,
                btc_correlation=btc_correlation,
                avg_volume_stability=avg_volume_stability,
                volume_spike_frequency=volume_spike_frequency,
                avg_recovery_days=avg_recovery_days,
                character=character
            )
            
        except Exception as e:
            return None
            
    def _classify_character(self, atr, max_move, spikes, trend_dur, trend_cons,
                           btc_corr, vol_stab, vol_spikes, recovery):
        """Classify coin into a character type based on metrics."""
        
        # Use a scoring system for more nuance
        scores = {
            'ATLAS': 0,      # Sakin dev (BTC-like)
            'GRINDER': 0,    # Yavaş ama istikrarlı
            'DALGACI': 0,    # Düzgün dalgalanma
            'IGNECI': 0,     # Hızlı iğne atar, geri döner
            'PATLAYICI': 0,  # Büyük patlamalar
            'TAKIPCI': 0,    # BTC'yi takip eder
            'ISYANKAR': 0,   # Bağımsız hareket
            'UYUYAN': 0,     # Uzun süre sessiz
            'HAYALET': 0,    # Düşük likidite
        }
        
        # --- ATR Based ---
        if atr < 3.0:
            scores['ATLAS'] += 3
            scores['GRINDER'] += 2
            scores['UYUYAN'] += 1
        elif atr < 5.0:
            scores['GRINDER'] += 2
            scores['DALGACI'] += 2
            scores['TAKIPCI'] += 1
        elif atr < 8.0:
            scores['DALGACI'] += 2
            scores['PATLAYICI'] += 1
            scores['TAKIPCI'] += 1
        else:
            scores['PATLAYICI'] += 3
            scores['IGNECI'] += 2
            
        # --- Spike Frequency ---
        if spikes > 50:
            scores['IGNECI'] += 3
            scores['PATLAYICI'] += 2
        elif spikes > 20:
            scores['IGNECI'] += 2
            scores['DALGACI'] += 1
        elif spikes > 5:
            scores['DALGACI'] += 2
        else:
            scores['GRINDER'] += 2
            scores['UYUYAN'] += 1
            
        # --- Max Move (Single Day) ---
        if max_move > 50:
            scores['IGNECI'] += 3
            scores['PATLAYICI'] += 2
        elif max_move > 30:
            scores['PATLAYICI'] += 2
            scores['IGNECI'] += 1
        elif max_move < 15:
            scores['GRINDER'] += 2
            scores['ATLAS'] += 1
            
        # --- Trend Duration ---
        if trend_dur > 30:
            scores['GRINDER'] += 3
            scores['ATLAS'] += 2
        elif trend_dur > 15:
            scores['DALGACI'] += 2
        else:
            scores['IGNECI'] += 2
            scores['PATLAYICI'] += 1
            
        # --- Trend Consistency ---
        if trend_cons > 60:
            scores['GRINDER'] += 2
            scores['ISYANKAR'] += 1
        elif trend_cons < 30:
            scores['IGNECI'] += 2
            scores['HAYALET'] += 1
            
        # --- BTC Correlation ---
        if btc_corr > 0.8:
            scores['TAKIPCI'] += 4
            scores['ATLAS'] += 1
        elif btc_corr > 0.6:
            scores['TAKIPCI'] += 2
        elif btc_corr < 0.3:
            scores['ISYANKAR'] += 3
            
        # --- Volume Stability ---
        if vol_stab > 3.0:
            scores['HAYALET'] += 3
            scores['IGNECI'] += 1
        elif vol_stab < 1.0:
            scores['GRINDER'] += 1
            scores['ATLAS'] += 1
            
        # --- Volume Spikes ---
        if vol_spikes > 100:
            scores['PATLAYICI'] += 2
            scores['IGNECI'] += 1
        elif vol_spikes < 20:
            scores['UYUYAN'] += 2
            
        # --- Recovery Days ---
        if recovery < 7:
            scores['IGNECI'] += 2  # Fast recoveries = needle pattern
        elif recovery > 30:
            scores['GRINDER'] += 1
            scores['UYUYAN'] += 1
            
        # Get top character
        sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
        top_char = sorted_scores[0][0]
        top_score = sorted_scores[0][1]
        second_char = sorted_scores[1][0]
        second_score = sorted_scores[1][1]
        
        # If close, create hybrid
        if top_score - second_score <= 2 and top_score > 0:
            return f"{top_char}/{second_char}"
        
        return top_char
        
    def analyze_all(self, progress_callback=None) -> List[CoinDNA]:
        """Analyze all coins and return their DNA profiles."""
        results = []
        total = len(self.coins)
        
        for i, symbol in enumerate(self.coins):
            if progress_callback:
                progress_callback(i, total, symbol)
            elif i % 10 == 0:
                print(f"Analyzing {i}/{total}: {symbol}...", end='\r')
                
            dna = self.analyze_coin(symbol)
            if dna:
                results.append(dna)
                
        return results
        
    def save_results(self, results: List[CoinDNA], filepath: str):
        """Save DNA results to JSON file."""
        data = []
        for r in results:
            data.append({
                'symbol': r.symbol,
                'character': r.character,
                'avg_atr_pct': round(float(r.avg_atr_pct), 2),
                'max_daily_move': round(float(r.max_daily_move), 2),
                'spike_frequency': int(r.spike_frequency),
                'avg_trend_duration': round(float(r.avg_trend_duration), 1),
                'trend_consistency': round(float(r.trend_consistency), 1),
                'btc_correlation': round(float(r.btc_correlation), 3),
                'avg_volume_stability': round(float(r.avg_volume_stability), 2),
                'volume_spike_frequency': int(r.volume_spike_frequency),
                'avg_recovery_days': round(float(r.avg_recovery_days), 1)
            })
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(data)} coin DNA profiles to {filepath}")


def main():
    print("=== COIN DNA ANALYZER ===")
    print("Profiling coin behavior across history...")
    
    analyzer = CoinDNAAnalyzer()
    results = analyzer.analyze_all()
    
    print(f"\n\nAnalyzed {len(results)} coins.\n")
    
    # Summary by character
    characters = {}
    for r in results:
        if r.character not in characters:
            characters[r.character] = []
        characters[r.character].append(r.symbol)
        
    print("=== CHARACTER DISTRIBUTION ===")
    for char, coins in sorted(characters.items(), key=lambda x: -len(x[1])):
        print(f"{char}: {len(coins)} coins")
        if len(coins) <= 10:
            print(f"  → {', '.join(coins)}")
        else:
            print(f"  → {', '.join(coins[:5])} ... +{len(coins)-5} more")
            
    # Save results
    output_path = "library/coin_dna_profiles.json"
    analyzer.save_results(results, output_path)
    

if __name__ == "__main__":
    main()
