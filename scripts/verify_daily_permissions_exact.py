import pandas as pd
import numpy as np
import json
import os
import sys

def check_permissions_exact():
    whitelist_path = "data/spot_whitelist_437.json"
    if not os.path.exists(whitelist_path):
        print("❌ Whitelist not found.")
        return

    with open(whitelist_path, "r") as f:
        all_coins = json.load(f)
        
    # User wants permissions that were VALID FOR Jan 26 and Jan 27.
    # In v4 System:
    # DNA for Date T is generated from T's Daily Close.
    # If Match -> Permission is granted for T+1.
    #
    # SO: 
    # To have permission FOR Jan 26 (Trading Day), we check DNA of Jan 25.
    # To have permission FOR Jan 27 (Trading Day), we check DNA of Jan 26.
    
    targets = [
        {"trading_day": "2026-01-26", "dna_source_day": "2026-01-25"},
        {"trading_day": "2026-01-27", "dna_source_day": "2026-01-26"}
    ]
    
    results = {
        "2026-01-26": [],
        "2026-01-27": []
    }
    
    print(f"🔍 Checking Golden Key Permissions (v4 Logic) for {len(all_coins)} coins...")
    
    for symbol in all_coins:
        try:
            # 1. Load Golden Key (The Authority)
            key_path = f"data/golden_keys/{symbol}_key.json"
            if not os.path.exists(key_path):
                continue
                
            with open(key_path, "r") as f:
                key_data = json.load(f)
            
            allowed_families = set(key_data.get('golden_dna_list', []))
            if not allowed_families:
                continue

            # 2. Load Data for DNA Calc
            try:
                df_w = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
                df_d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
                df_h4 = pd.read_parquet(f"coin_cells/{symbol}/data/history_4h.parquet")
                df_h1 = pd.read_parquet(f"coin_cells/{symbol}/data/history_1h.parquet")
            except:
                continue

            # Pre-calc columns (Same as forge_golden_key.py)
            for df in [df_w, df_d, df_h4, df_h1]:
                df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('dt', inplace=True)
                df.sort_index(inplace=True)
                df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
                df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
                df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()

            # 3. DNA Logic (Exact Copy/Paste)
            def get_profile(day):
                day = pd.Timestamp(day)
                
                # PHASE
                sub_w = df_w[df_w.index <= day]
                if sub_w.empty: return "neutral"
                delta = sub_w['close'].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
                rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                
                faz = "neutral"
                if rsi < 40: faz = "derin_dip"
                elif rsi < 60: faz = "birikim_fazi"
                elif rsi < 75: faz = "yukselis_fazi"
                else: faz = "asiri_alim"
                
                # ACCUMULATION (H1) - Last 24h
                sub_h1 = df_h1[df_h1.index <= day].tail(24)
                if sub_h1.empty: return "neutral"
                comp = (sub_h1[['ema9','ema21','ema50']].max(axis=1) / sub_h1[['ema9','ema21','ema50']].min(axis=1) - 1)*100
                min_c = comp.min()
                acc = "loose"
                if min_c < 0.4: acc = "micro_squeeze"
                elif min_c < 0.8: acc = "tight_squeeze"
                elif min_c < 1.5: acc = "coiling"
                
                # HARMONY
                sub_d = df_d[df_d.index <= day]
                sub_h4 = df_h4[df_h4.index <= day]
                if sub_d.empty or sub_h4.empty: return "neutral"
                s = sum([sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21'], 
                         sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21'], 
                         sub_h1.iloc[-1]['close']>sub_h1.iloc[-1]['ema21']])
                harm = f"harmony_L{s}"
                
                # RHYTHM & ENERGY
                sub_d_tail = sub_d.tail(10)
                if len(sub_d_tail) == 0: return "neutral"
                
                vol_pulse = sub_d_tail['volume'].iloc[-1] / (sub_d_tail['volume'].mean()+1)
                ritim = "active" if vol_pulse > 1.0 else "sleeping"
                if vol_pulse > 2.0: ritim = "ignited"
                
                v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
                enerji = "building_energy" if v_trend else "depleting_energy"
                
                # CONTEXT
                yr_high = sub_d.tail(365)['high'].max() if len(sub_d)>0 else 1
                retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
                ctx = "mid_zone"
                if retr > -20: ctx = "recovery_high"
                elif retr < -50: ctx = "deep_valley"
                
                return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"

            # 4. Check for Each Target Day
            for t in targets:
                trading_day = t['trading_day']
                source_day = t['dna_source_day'] # The day 'forge' logic looks at to predict tomorrow
                
                # Ensure we actually have data for source_day
                if pd.Timestamp(source_day) > df_d.index[-1]:
                    continue # Future data not available yet or strict cutoff
                
                dna = get_profile(source_day)
                
                if dna in allowed_families:
                    results[trading_day].append(symbol)

        except Exception as e:
            # print(f"Error {symbol}: {e}")
            pass

    # SAVE Artifact
    md = "# 🛡️ TÜNEL GİRİŞ İZİNLERİ (GOLDEN KEY CHECK)\n\n"
    md += "Bu liste, Tünel Sinyali (15m) üretsin ya da üretmesin, o gün **DNA'sı onaylı** olan (Tünele giriş hakkı kazanan) tüm coinleri listeler.\n\n"
    
    for date in sorted(results.keys()):
        coins = sorted(results[date])
        md += f"## 📅 {date} (İzinli: {len(coins)})\n"
        md += f"`{', '.join(coins)}`\n\n"
        
    out_path = "JAN_26_27_AUTHORITY_CHECK.md"
    with open(out_path, "w") as f:
        f.write(md)
    print(f"✅ Authority Check Complete based on v4 Golden Keys. Saved to {out_path}")

if __name__ == "__main__":
    check_permissions_exact()
