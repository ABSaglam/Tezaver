import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path

from tezaver.core import config, coin_cell_paths
from tezaver.mining.daily_radar_engine import DailyRadarEngine
from tezaver.core.rally_store import RallyStore

class DBRadarBacktester:
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.engine = DailyRadarEngine()
        self.store = RallyStore()
        
    def run(self, days_back: int = 730):
        summary = {
            "total_signals": 0,
            "categories": {"AMBUSH": 0, "TREND": 0, "NINJA": 0, "BREAKOUT": 0},
            "total_rallies_in_db": 0,
            "rallies_predicted": 0,
            "signal_details": []
        }
        
        total_coins = len(self.symbols)
        for i, symbol in enumerate(self.symbols):
            if i % 20 == 0:
                print(f"[{i}/{total_coins}] Analysing {symbol} (Hits & Drawdowns)...")
            self.backtest_symbol_v4(symbol, days_back, summary)
            
        return summary

    def backtest_symbol_v4(self, symbol: str, days_back: int, summary: Dict):
        # 1. Load 15m Rallies for this coin (Ground Truth)
        db_rallies = self.store.list_rallies(symbol=symbol, timeframe='15m')
        
        rally_map = {} # time -> {tier, archetype}
        for r in db_rallies:
            t = pd.Timestamp(r['event_time']).tz_localize(None)
            archetype = (r.get('molder_data') or {}).get('archetype', 'UNKNOWN')
            rally_map[t] = {"tier": r.get('tier', 'C'), "archetype": archetype}
        
        summary["total_rallies_in_db"] += len(db_rallies)
        rally_times = sorted(rally_map.keys())
        
        # 2. Load OHLCV to simulate radar signals
        path_1d = coin_cell_paths.get_history_file(symbol, "1d")
        path_4h = coin_cell_paths.get_history_file(symbol, "4h")
        if not path_1d.exists() or not path_4h.exists(): return
        
        try:
            df_1d = pd.read_parquet(path_1d)
            df_1d['datetime'] = df_1d['datetime'].dt.tz_localize(None)
            df_4h = pd.read_parquet(path_4h).copy()
            df_4h['datetime'] = df_4h['datetime'].dt.tz_localize(None)
        except: return
        
        if len(df_1d) < 30: return

        # 3. Vectorized Indicators
        df_1d['tr'] = np.maximum(df_1d['high'] - df_1d['low'], 
                                np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), 
                                           abs(df_1d['low'] - df_1d['close'].shift(1))))
        df_1d['atr_pct'] = (df_1d['tr'].rolling(14).mean() / df_1d['close']) * 100
        df_1d['high_5d'] = df_1d['high'].rolling(5).max()
        df_1d['low_5d'] = df_1d['low'].rolling(5).min()
        df_1d['mid_pct'] = (df_1d['close'] - df_1d['low_5d']) / (df_1d['high_5d'] - df_1d['low_5d']) * 100
        df_1d['bb_width'] = (df_1d['close'].rolling(20).std() * 4) / df_1d['close'].rolling(20).mean() * 100
        df_1d['bb_squeeze'] = df_1d['bb_width'] <= df_1d['bb_width'].rolling(20).min() * 1.1
        
        def calculate_rsi(series, period=14):
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            return 100 - (100 / (1 + (gain / loss.replace(0, 0.001))))

        df_4h['rsi_4h'] = calculate_rsi(df_4h['close'])
        
        # Safe aggregation for merge
        df_4h_daily = df_4h.copy()
        df_4h_daily['day_ts'] = df_4h_daily['datetime'].dt.floor('D')
        df_4h_daily = df_4h_daily.groupby('day_ts')['rsi_4h'].last().reset_index()
        
        df_merged = df_1d.merge(df_4h_daily, left_on='datetime', right_on='day_ts', how='inner')
        test_start = df_merged['datetime'].max() - timedelta(days=days_back)
        df_test = df_merged[df_merged['datetime'] >= test_start].copy()
        
        dna = self.engine.dna_profiles.get(symbol, {"tier": "C"})
        coin_tier = dna.get('tier', 'C')
        tier_rank = {'S': 5, 'A': 4, 'B+': 3, 'B': 2, 'B-': 1, 'C+': 0, 'C': -1}
        has_min_dna = tier_rank.get(coin_tier, -10) >= tier_rank.get('B', 0)

        rallies_caught_at = set()

        for idx, row in df_test.iterrows():
            # Use rsi_4h from merge
            is_ambush = has_min_dna and row['bb_squeeze'] and (15 <= row['mid_pct'] <= 55) and (40 <= row['rsi_4h'] <= 60)
            is_trend = has_min_dna and (row['atr_pct'] > 5) and (row['mid_pct'] > 70) and (row['rsi_4h'] > 60)
            is_ninja = (row['atr_pct'] > 10) and (row['mid_pct'] < 30) and row['bb_squeeze'] and (row['rsi_4h'] < 40)
            
            cat = "NINJA" if is_ninja else "TREND" if is_trend else "AMBUSH" if is_ambush else None
            
            if cat:
                summary["total_signals"] += 1
                summary["categories"][cat] += 1
                
                window_start = row['datetime']
                window_end = row['datetime'] + timedelta(hours=72)
                
                # Check for Success (DB Rally)
                found_rally = None
                for r_time in rally_times:
                    if window_start <= r_time <= window_end:
                        found_rally = rally_map[r_time]
                        rallies_caught_at.add(r_time)
                        break
                
                # Check for Failure (Drawdown in 4H data for precision)
                df_fail_window = df_4h[(df_4h['datetime'] >= window_start) & (df_4h['datetime'] <= window_end)]
                max_dd = 0
                if not df_fail_window.empty:
                    signal_price = row['close']
                    min_price = df_fail_window['low'].min()
                    max_dd = (min_price - signal_price) / signal_price * 100
                
                # Assign Negative Tier if not a hit
                neg_tier = None
                if found_rally is None:
                    if max_dd <= -30: neg_tier = "-DIAMOND"
                    elif max_dd <= -20: neg_tier = "-GOLD"
                    elif max_dd <= -10: neg_tier = "-SILVER"
                    elif max_dd <= -5: neg_tier = "-BRONZE"
                    else: neg_tier = "-IRON"

                summary["signal_details"].append({
                    "symbol": symbol,
                    "date": row['datetime'],
                    "coin_tier": coin_tier,
                    "cat": cat,
                    "is_hit": found_rally is not None,
                    "rally_tier": found_rally['tier'] if found_rally else None,
                    "neg_tier": neg_tier,
                    "max_dd": max_dd
                })
        
        summary["rallies_predicted"] += len(rallies_caught_at)

if __name__ == "__main__":
    from tezaver.core.config import DEFAULT_COINS
    tester = DBRadarBacktester(DEFAULT_COINS)
    results = tester.run(days_back=730)
    
    df_res = pd.DataFrame(results['signal_details'])
    if not df_res.empty:
        print("\n" + "="*110)
        print("🧬 DNA TIER PERFORMANCE & RISK BREAKDOWN (SUCCESS vs LOSS TIERS)")
        print("="*110)
        print(f"{'Tier':<6} | {'Signals':<8} | {'Win%':<6} | {'💎':<4} {'🥇':<4} {'🥈':<4} | {'-💎':<4} {'-🥇':<4} {'-🥈':<4} {'-🥉':<4} {'-🔩':<4}")
        print("-" * 110)

        full_tiers = ['S', 'A', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D']
        for t in full_tiers:
            t_data = df_res[df_res['coin_tier'] == t]
            if t_data.empty: continue
            
            total = len(t_data)
            hits = t_data[t_data['is_hit'] == True]
            fails = t_data[t_data['is_hit'] == False]
            win_rate = (len(hits) / total * 100)
            
            # Positive Tiers
            d_p = len(hits[hits['rally_tier'] == 'DIAMOND'])
            g_p = len(hits[hits['rally_tier'] == 'GOLD'])
            s_p = len(hits[hits['rally_tier'] == 'SILVER'])
            
            # Negative Tiers
            d_n = len(fails[fails['neg_tier'] == '-DIAMOND'])
            g_n = len(fails[fails['neg_tier'] == '-GOLD'])
            s_n = len(fails[fails['neg_tier'] == '-SILVER'])
            b_n = len(fails[fails['neg_tier'] == '-BRONZE'])
            i_n = len(fails[fails['neg_tier'] == '-IRON'])
            
            print(f"{t:<6} | {total:<8} | {win_rate:>5.1f}% | {d_p:<4} {g_p:<4} {s_p:<4} | {d_n:<4} {g_n:<4} {s_n:<4} {b_n:<4} {i_n:<4}")
        print("-" * 110)
