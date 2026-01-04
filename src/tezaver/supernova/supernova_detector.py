import pandas as pd
import numpy as np
from datetime import timedelta

class SuperNovaDetector:
    """
    SuperNova Event Detector - Diamond DNA v3.
    """
    def __init__(self):
        self.lookahead = 50
        self.vol_sma_period = 30
        self.rsi_period = 14
        self.bb_period = 20
        self.bb_std = 2.0

    def calculate_indicators(self, df):
        if df is None or df.empty:
            return df
            
        df = df.copy()
        
        # 1. Volume Ratio
        df['avg_vol_30'] = df['volume'].shift(1).rolling(window=self.vol_sma_period).mean()
        df['vol_ratio'] = df['volume'] / df['avg_vol_30'].replace(0, np.nan)
        
        # 2. RSI & RSI-EMA
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi_ema'] = df['rsi'].ewm(span=self.rsi_period, adjust=False).mean()
        
        # 3. Bollinger Bands
        ma = df['close'].rolling(window=self.bb_period).mean()
        std = df['close'].rolling(window=self.bb_period).std()
        df['bb_upper'] = ma + (self.bb_std * std)
        
        # 4. MACD (4-Color Histogram)
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        df['macd_hist_prev'] = df['macd_hist'].shift(1)
        
        def get_macd_color(row):
            h = row['macd_hist']
            hp = row['macd_hist_prev']
            if h > 0:
                return "YEŞİL" if h > hp else "MOR"
            else:
                return "KIRMIZI" if h < hp else "SARI"
                
        df['macd_color'] = df.apply(lambda r: get_macd_color(r), axis=1)
        
        # 5. Body Ratio
        df['body_size'] = (df['close'] - df['open']).abs()
        df['candle_size'] = (df['high'] - df['low']).replace(0, 0.000001)
        df['body_ratio'] = df['body_size'] / df['candle_size']
        
        return df

    def analyze_backtest(self, df, symbol=None, lookahead=50, df_1h=None, df_4h=None, df_1d=None):
        if df is None or df.empty:
            return []
            
        results = []
        
        # Calculate Indicators if not present
        if 'vol_ratio' not in df.columns:
            df = self.calculate_indicators(df)
            
        # Identify base 7x Green spikes
        spikes = df[ (df['vol_ratio'] >= 7.0) & (df['close'] > df['open']) ]
        
        for idx in spikes.index:
            row = df.loc[idx]
            t = row['datetime']
            
            # DNA v2 Checks (15m)
            pass_rsi = row['rsi'] > row['rsi_ema']
            pass_bb = row['close'] > row['bb_upper']
            pass_macd = row['macd_color'] != "MOR"
            pass_body = row['body_ratio'] > 0.6
            
            dna_v2_pass = pass_rsi and pass_bb and pass_macd and pass_body
            
            # Killer Blow (MTF) Checks
            killer_blow_pass = False
            if df_1h is not None and df_4h is not None and df_1d is not None:
                c1h = df_1h[df_1h['datetime'] <= t].tail(1)
                c4h = df_4h[df_4h['datetime'] <= t].tail(1)
                c1d = df_1d[df_1d['datetime'] <= t].tail(1)
                
                if not c1h.empty and not c4h.empty and not c1d.empty:
                    # 1h MACD OK
                    m1h, s1h = self._calc_quick_macd(df_1h, c1h.index[0])
                    # 4h MACD OK
                    m4h, s4h = self._calc_quick_macd(df_4h, c4h.index[0])
                    # 1d Green
                    is_1d_green = c1d.iloc[0]['close'] > c1d.iloc[0]['open']
                    
                    if m1h > s1h and m4h > s4h and is_1d_green:
                        killer_blow_pass = True
            
            # Outcome
            entry = row['close']
            window = df.iloc[idx+1 : idx+1+lookahead]
            if window.empty:
                max_gain = 0
                max_loss = 0
            else:
                max_gain = (window['high'].max() - entry) / entry * 100
                max_loss = (window['low'].min() - entry) / entry * 100
            
            tier = "IRON"
            if max_gain >= 30: tier = "DIAMOND"
            elif max_gain >= 20: tier = "GOLD"
            elif max_gain >= 10: tier = "SILVER"
            elif max_gain >= 5: tier = "BRONZE"
            
            results.append({
                'datetime': t,
                'symbol': symbol,
                'vol_ratio': row['vol_ratio'],
                'macd_color': row['macd_color'],
                'dna_v2': "✅" if dna_v2_pass else "❌",
                'killer_blow': "🔥" if killer_blow_pass else "⚪",
                'max_gain': max_gain,
                'max_loss': max_loss,
                'tier': tier
            })
            
        return results

    def _calc_quick_macd(self, df, idx):
        # We assume MACD is pre-calculated in the UTF dataframes for speed
        if 'macd' in df.columns and 'macd_signal' in df.columns:
            return df.loc[idx, 'macd'], df.loc[idx, 'macd_signal']
        
        # Fallback if not pre-calculated (slow)
        hist = df.loc[:idx]
        if len(hist) < 26: return 0, 0
        exp1 = hist['close'].ewm(span=12, adjust=False).mean().iloc[-1]
        exp2 = hist['close'].ewm(span=26, adjust=False).mean().iloc[-1]
        macd = exp1 - exp2
        return macd, 0
