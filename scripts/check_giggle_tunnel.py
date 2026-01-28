import pandas as pd
import json
import os

symbol = "GIGGLEUSDT"
target_day = pd.Timestamp("2025-12-01")

# Load Macro Data
df_1d = pd.read_parquet(f"coin_cells/{symbol}/data/history_1d.parquet")
df_1d['dt'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
df_1d.set_index('dt', inplace=True)
df_1d['ema21'] = df_1d['close'].ewm(span=21, adjust=False).mean()

df_1w = pd.read_parquet(f"coin_cells/{symbol}/data/history_1w.parquet")
df_1w['dt'] = pd.to_datetime(df_1w['timestamp'], unit='ms')
df_1w.set_index('dt', inplace=True)

df_4h = pd.read_parquet(f"coin_cells/{symbol}/data/history_4h.parquet")
df_4h['dt'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
df_4h.set_index('dt', inplace=True)
df_4h['ema21'] = df_4h['close'].ewm(span=21, adjust=False).mean()

df_1h = pd.read_parquet(f"coin_cells/{symbol}/data/history_1h.parquet")
df_1h['dt'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
df_1h.set_index('dt', inplace=True)
df_1h['ema9'] = df_1h['close'].ewm(span=9, adjust=False).mean()
df_1h['ema21'] = df_1h['close'].ewm(span=21, adjust=False).mean()
df_1h['ema50'] = df_1h['close'].ewm(span=50, adjust=False).mean()

def get_profile_simple(day, df_w, df_h1, df_d, df_h4):
    try:
        sub_w = df_w[df_w.index <= day].tail(30)
        delta = sub_w['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.001)
        rsi_val = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        faz = "derin_dip" if rsi_val < 40 else "birikim_fazi" if rsi_val < 60 else "yukselis_fazi" if rsi_val < 75 else "asiri_alim"
        sub_h1_24 = df_h1[df_h1.index <= day].tail(24)
        comp = (sub_h1_24[['ema9','ema21','ema50']].max(axis=1) / sub_h1_24[['ema9','ema21','ema50']].min(axis=1) - 1)*100
        min_c = comp.min()
        acc = "micro_squeeze" if min_c < 0.4 else "tight_squeeze" if min_c < 0.8 else "coiling" if min_c < 1.5 else "loose"
        sub_d = df_d[df_d.index <= day]
        sub_h4 = df_h4[df_h4.index <= day]
        sub_h1_sub = df_h1[df_h1.index <= day]
        s = int(sub_d.iloc[-1]['close']>sub_d.iloc[-1]['ema21']) + int(sub_h4.iloc[-1]['close']>sub_h4.iloc[-1]['ema21']) + int(sub_h1_sub.iloc[-1]['close']>sub_h1_sub.iloc[-1]['ema21'])
        harm = f"harmony_L{s}"
        sub_d_tail = sub_d.tail(10)
        vol_pulse = sub_d.iloc[-1]['volume'] / (sub_d_tail['volume'].mean()+1)
        ritim = "ignited" if vol_pulse > 2.0 else "active" if vol_pulse > 1.0 else "sleeping"
        v_trend = sub_d_tail['volume'].tail(3).mean() > sub_d_tail['volume'].head(7).mean()
        enerji = "building_energy" if v_trend else "depleting_energy"
        yr_high = sub_d.tail(365)['high'].max()
        retr = (sub_d.iloc[-1]['close']/yr_high - 1)*100
        ctx = "recovery_high" if retr > -20 else "deep_valley" if retr < -50 else "mid_zone"
        return f"{faz}|{acc}|{harm}|{ritim}|{ctx}|{enerji}"
    except: return "error"

dna = get_profile_simple(target_day, df_1w, df_1h, df_1d, df_4h)
with open(f"data/golden_keys/{symbol}_key.json", "r") as f:
    keys = json.load(f).get('golden_dna_list', [])

print(f"SYMBOL: {symbol}")
print(f"DNA on Dec 1st: {dna}")
print(f"IS IN GOLDEN KEY: {dna in keys}")

df_15m = pd.read_parquet(f"coin_cells/{symbol}/data/history_15m.parquet")
df_15m['dt'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
df_15m.set_index('dt', inplace=True)
day_data = df_15m[df_15m.index.normalize() == target_day]
o = day_data.iloc[0]['open']
h = day_data['high'].max()
rally = (h/o - 1)*100
print(f"Açılış: {o}, Günlük Max: {h}")
print(f"Hesaplanan Yeni Ralli (H/Open-1): %{rally:.2f}")
