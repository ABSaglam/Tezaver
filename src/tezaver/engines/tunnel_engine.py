import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
from tezaver.core.config import COIN_CELLS_DIR

class TunnelEngine:
    """
    Ayaş Tüneli (Tunnel Vision) Motoru - V16 Full Spec + Report Viewer
    """

    def __init__(self):
        self.cells_dir = COIN_CELLS_DIR
        self.golden_keys_dir = "/Users/alisaglam/TezaverMac/data/golden_keys"

    def check_permission(self, symbol, date):
        try:
            key_path = os.path.join(self.golden_keys_dir, f"{symbol}_key.json")
            if not os.path.exists(key_path): return False, "NO_KEY", "neutral"

            with open(key_path, "r") as f:
                key_data = json.load(f)
                golden_dna_list = set(key_data.get('golden_dna_list', []))

            # Load Data
            path_w = os.path.join(self.cells_dir, symbol, "data", "history_1w.parquet")
            path_d = os.path.join(self.cells_dir, symbol, "data", "history_1d.parquet")
            path_h4 = os.path.join(self.cells_dir, symbol, "data", "history_4h.parquet")
            path_h1 = os.path.join(self.cells_dir, symbol, "data", "history_1h.parquet")
            
            df_w = pd.read_parquet(path_w)
            df_d = pd.read_parquet(path_d)
            df_h4 = pd.read_parquet(path_h4)
            df_h1 = pd.read_parquet(path_h1)
            
            for df in [df_w, df_d, df_h4, df_h1]:
                df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('dt', inplace=True)
                df.sort_index(inplace=True)
            
            df_d['ema21'] = df_d['close'].ewm(span=21, adjust=False).mean()
            df_h4['ema21'] = df_h4['close'].ewm(span=21, adjust=False).mean()
            df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
            df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
            df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()

            target_date = pd.Timestamp(date)
            # GOLD Script Uyumu: Hedef günün kendisi için DNA kontrolü (kaydırma yok)
            dna = self._get_profile_simple(target_date, df_w, df_h1, df_d, df_h4)
            
            if dna in golden_dna_list:
                return True, "GRANTED", dna
            else:
                return False, "DENIED", dna

        except Exception as e:
            return False, f"ERROR: {str(e)}", "neutral"

    def scan_tunnel_day(self, date_str):
        # Live Scan Logic (Fallback)
        symbols = [d for d in os.listdir(self.cells_dir) if os.path.isdir(os.path.join(self.cells_dir, d))]
        report_rows = []
        target_date = pd.Timestamp(date_str)
        symbols.sort()

        coin_counter = 0

        for symbol in symbols:
            # 1. PERMISSION
            has_perm, status, dna = self.check_permission(symbol, date_str)
            if not has_perm: continue

            # 2. TRIGGER SCAN (15m)
            try:
                path_15m = os.path.join(self.cells_dir, symbol, "data", "history_15m.parquet")
                if not os.path.exists(path_15m): continue
                
                df_15m = pd.read_parquet(path_15m)
                df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
                df_15m.set_index('dt', inplace=True)
                df_15m.sort_index(inplace=True)
                df_15m.sort_index(inplace=True)
                
                # CRITICAL: Calculate indicators ON FULL HISTORY first
                self._calculate_indicators(df_15m)
                
                day_mask = (df_15m.index.normalize() == target_date)
                day_data = df_15m[day_mask].copy()

                if day_data.empty: continue

                triggers = self._find_triggers(day_data)

                if triggers:
                    coin_counter += 1
                    for idx, t in enumerate(triggers):
                        is_first = (idx == 0)
                        row = {
                            "NO": str(coin_counter) if is_first else "",
                            "SYM": symbol if is_first else "",
                            "MAX": f"+{((day_data['high'].max()/day_data.iloc[0]['open'])-1)*100:.1f}%" if is_first else "",
                            "CLOSE": f"+{((day_data.iloc[-1]['close']/day_data.iloc[0]['open'])-1)*100:.1f}%" if is_first else "",
                            "TIME": t['time'].strftime('%H:%M'),
                            "SIG": "🚀" if t.get('is_rocket') else "",
                            "TREND": t['trend_icon'],
                            "POS": t['pos_icon'],
                            "ANG": t['angle_val'],
                            "VAL": t['val_icon'],
                            "P": f"+{t['p_change']:.1f}%",
                            "P-21": t['p21_change'],
                            "BAR": t['bar_wait'],
                            "NEXT": t['next_move'],
                            "R-Rib": t['ribbon_btn'],
                            "Vrsi": t['v_rsi'],
                            "V100": f"{t['v_100']:.1f}",
                            "V21": f"{t['v_21']:.1f}",
                            "V-Mom": f"{t['v_mom']:.1f}",
                            "VBoy": t['v_boy'],
                            "V-Ch": t['v_ch'],
                            "V-Avg": t['v_avg'],
                            "DNA": dna,
                            "RAW": t,
                            # Helper for selection
                            "_SYM_REAL": symbol
                        }
                        report_rows.append(row)
            except Exception as e:
                continue
        return pd.DataFrame(report_rows)
    
    def parse_static_report(self, date_str):
        """
        refined_global_report_v16.md dosyasını okur ve tabloyu döner.
        """
        report_path = "/Users/alisaglam/TezaverMac/refined_global_report_v16.md"
        if not os.path.exists(report_path): return pd.DataFrame()

        # Tarih formatı: "26 Ocak 2026"
        month_map = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}
        dt = pd.Timestamp(date_str)
        search_header = f"{dt.day} {month_map[dt.month]} {dt.year}"
        
        rows = []
        capture = False
        headers = []
        
        try:
            with open(report_path, "r") as f:
                lines = f.readlines()
                
            for line in lines:
                line = line.strip()
                if "## 📅" in line:
                    if search_header in line:
                        capture = True
                    else:
                        capture = False
                    continue
                
                if capture:
                    if line.startswith("| NO"):
                        headers = [h.strip() for h in line.split('|') if h.strip()]
                        continue
                    if line.startswith("|---") or not line.startswith("|"):
                        continue
                        
                    parts = [p.strip() for p in line.split('|')[1:-1]]
                    if len(parts) < 2: continue
                    
                    row_dict = {}
                    cleaned_parts = []
                    for p in parts:
                        clean_p = p.replace("<font color='green'>", "").replace("</font>", "").replace("<font color='red'>", "").replace("<font color='blue'>", "").replace("<font color='orange'>", "").replace("<font color='#00FF00'>", "").replace("<font color='#888888'>", "").replace("**", "").strip()
                        cleaned_parts.append(clean_p)
                        
                    if not headers: headers = ["NO","SYM","MAX","CLOSE","TIME","SIG","TREND","POS","ANG","VAL","P","P-21","BAR","NEXT","R-Rib","Vrsi","V100","V21","V-Mom","VBoy","V-Ch","V-Avg"]
                    
                    for i, h in enumerate(headers):
                        if i < len(cleaned_parts):
                            row_dict[h] = cleaned_parts[i]
                    
                    # Cerrahi için SYM bulma
                    if row_dict.get("SYM", "") == "":
                         prev_row = rows[-1] if rows else None
                         if prev_row:
                             row_dict['_SYM_REAL'] = prev_row.get('_SYM_REAL', prev_row.get('SYM'))
                    else:
                         row_dict['_SYM_REAL'] = row_dict.get("SYM")

                    # DNA Placeholder (to be fetched on click)
                    row_dict["DNA"] = "Analiz|İçin|Seçiniz|...|...|..."
                    rows.append(row_dict)
                    
            return pd.DataFrame(rows)
        except: return pd.DataFrame()

    def _get_profile_simple(self, day, df_w, df_h1, df_d, df_h4):
        try:
            sub_w = df_w[df_w.index <= day].tail(30)
            if sub_w.empty: return "neutral"
            delta = sub_w['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
            rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
            faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
            sub_h1_24 = df_h1[df_h1.index <= day].tail(24)
            if sub_h1_24.empty or 'ema9' not in sub_h1_24: return "neutral"
            comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
            min_c = comp.min()
            acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
            sub_d = df_d[df_d.index <= day]
            sub_h4 = df_h4[df_h4.index <= day]
            sub_h1_sub = df_h1[df_h1.index <= day]
            if sub_d.empty or sub_h4.empty or sub_h1_sub.empty: return "neutral"
            s = int(sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21']) + int(sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21']) + int(sub_h1_sub.iloc[-1]['close']>sub_h1_sub.iloc[-1]['ema21'])
            harm = f"harmony_L{s}"
            sub_d_tail = sub_d.tail(10)
            vol_p = sub_d.iloc[-1]['volume'] / (sub_d_tail['volume'].mean()+1)
            ritim = "ignited" if vol_p > 2.0 else "active" if vol_p > 1.0 else "sleeping"
            v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
            enerji = "building_energy" if v_trend else "depleting_energy"
            yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
            retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
            ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"
            return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
        except: return "neutral"

    def _calculate_indicators(self, df):
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))
        df['ema10'] = df['close'].ewm(span=10, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema55'] = df['close'].ewm(span=55, adjust=False).mean()
        df['vol_ma21'] = df['volume'].rolling(window=21).mean()
        df['vol_ma100'] = df['volume'].rolling(window=100).mean()

    def _find_triggers(self, df):
        triggers = []
        rsi_vals = df['rsi'].values
        trigger_indices = np.where((rsi_vals[:-1] <= 70) & (rsi_vals[1:] > 70))[0] + 1
        for i in trigger_indices:
            row = df.iloc[i]
            angle_val = 0
            if i > 5:
                y = df['ema21'].values[i-5:i]
                x = np.arange(len(y))
                if len(y) > 0:
                    slope, _ = np.polyfit(x, y, 1)
                    angle_val = slope * 100 / row['close']
            
            c, e10, e21, e55 = row['close'], row['ema10'], row['ema21'], row['ema55']
            if c > e10 and e10 > e21: trend = "🟢🟢"
            elif c > e21: trend = "🟢"
            elif c < e21: trend = "🔴"
            else: trend = "⚪"
            
            pos = "🟡"
            if row['rsi'] > 80: pos = "💣"
            elif row['rsi'] < 30: pos = "🧊"
            elif row['rsi'] > 60: pos = "☀️"
             
            val_icon = "❤️" if e21 > e55 else "💚"
            v = row['volume']
            v21 = row['vol_ma21'] if row['vol_ma21']>0 else 1
            v100 = row['vol_ma100'] if row['vol_ma100']>0 else 1
            v_ratio_21 = v / v21
            v_ratio_100 = v / v100
            
            v_mom = 0.0
            if i > 1:
                prev_v21 = df.iloc[i-1]['vol_ma21']
                if prev_v21 > 0:
                    v_mom = (v21 - prev_v21) / prev_v21 * 100

            triggers.append({
                "time": row.name,
                "is_rocket": angle_val > 0.05,
                "trend_icon": trend,
                "pos_icon": pos,
                "angle_val": f"{angle_val:.2f}",
                "val_icon": val_icon,
                "p_change": ((row['close'] - row['open'])/row['open'])*100,
                "p21_change": f"{((c - e21)/e21)*100:.1f}%",
                "bar_wait": 0,
                "next_move": "-",
                "ribbon_btn": "🟢" if c > e21 else "🔴",
                "v_rsi": f"{row['rsi']:.1f}",
                "v_100": v_ratio_100,
                "v_21": v_ratio_21,
                "v_mom": v_mom,
                "v_boy": "🐳" if v_ratio_100 > 5 else "🐟" if v_ratio_100 > 2 else "🦐",
                "v_ch": f"+{((v - v21)/v21)*100:.0f}%",
                "v_avg": f"{v21:.0f}"
            })
        return triggers
