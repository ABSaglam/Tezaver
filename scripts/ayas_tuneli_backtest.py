"""
Ayaş Tüneli 3 Aylık Backtest - 10 Tier Raporu
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tezaver.core import config, coin_cell_paths
from tezaver.core.rally_store import RallyStore

store = RallyStore()
TUNEL = {
    'TREND': {'atr_min': 15.0, 'rsi_min': 55, 'rsi_max': 70},
    'NINJA': {'atr_min': 12.0, 'rsi_min': 60, 'rsi_max': 75}
}

start_date = datetime.now() - timedelta(days=730)
results = []

print("Tarama başlıyor...")
for idx, symbol in enumerate(config.DEFAULT_COINS):
    if idx % 50 == 0:
        print(f"[{idx}/{len(config.DEFAULT_COINS)}] {symbol}")
    try:
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        path_4h = coin_cell_paths.get_history_file(symbol, '4h')
        if not path_1d.exists() or not path_4h.exists(): continue
        
        df_1d = pd.read_parquet(path_1d)
        df_1d['datetime'] = df_1d['datetime'].dt.tz_localize(None)
        df_4h = pd.read_parquet(path_4h)
        df_4h['datetime'] = df_4h['datetime'].dt.tz_localize(None)
        if len(df_1d) < 20: continue
        
        df_1d['tr'] = np.maximum(df_1d['high'] - df_1d['low'], 
                                np.maximum(abs(df_1d['high'] - df_1d['close'].shift(1)), 
                                           abs(df_1d['low'] - df_1d['close'].shift(1))))
        df_1d['atr_pct'] = (df_1d['tr'].rolling(14).mean() / df_1d['close']) * 100
        
        delta = df_4h['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df_4h['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 0.001))))
        df_4h['day'] = df_4h['datetime'].dt.floor('D')
        daily_rsi = df_4h.groupby('day')['rsi'].last()
        
        db_rallies = store.list_rallies(symbol=symbol, timeframe='15m')
        rally_map = {pd.Timestamp(r['event_time']).tz_localize(None): r.get('tier', 'SILVER') for r in db_rallies}
        
        period_data = df_1d[df_1d['datetime'] >= start_date]
        
        for _, row in period_data.iterrows():
            atr = row['atr_pct']
            day_ts = pd.Timestamp(row['datetime']).floor('D')
            rsi = daily_rsi.get(day_ts, 50)
            
            t = TUNEL['TREND']
            n = TUNEL['NINJA']
            is_trend = atr >= t['atr_min'] and t['rsi_min'] <= rsi <= t['rsi_max']
            is_ninja = atr >= n['atr_min'] and n['rsi_min'] <= rsi <= n['rsi_max']
            
            if is_trend or is_ninja:
                window_start = row['datetime']
                window_end = row['datetime'] + timedelta(hours=120)
                
                hit_tier = None
                for r_time in sorted(rally_map.keys()):
                    if window_start <= r_time <= window_end:
                        hit_tier = rally_map[r_time]
                        break
                
                df_window = df_4h[(df_4h['datetime'] >= window_start) & (df_4h['datetime'] <= window_end)]
                max_gain = 0
                max_loss = 0
                if not df_window.empty:
                    signal_price = row['close']
                    max_price = df_window['high'].max()
                    min_price = df_window['low'].min()
                    max_gain = (max_price - signal_price) / signal_price * 100
                    max_loss = (min_price - signal_price) / signal_price * 100
                
                if hit_tier:
                    full_tier = hit_tier
                else:
                    dd = max_loss
                    if dd >= -5: full_tier = '-IRON'
                    elif dd >= -10: full_tier = '-BRONZE'
                    elif dd >= -20: full_tier = '-SILVER'
                    elif dd >= -30: full_tier = '-GOLD'
                    else: full_tier = '-DIAMOND'
                
                results.append({
                    'date': day_ts.strftime('%Y-%m-%d'),
                    'symbol': symbol.replace('USDT',''),
                    'tier': full_tier,
                    'gain': round(max_gain, 1),
                    'loss': round(max_loss, 1)
                })
    except:
        continue

print(f"\nToplam sinyal: {len(results)}")

df_res = pd.DataFrame(results)
total = len(df_res)

# 10 Tier Summary
tier_order = ['DIAMOND', 'GOLD', 'SILVER', 'BRONZE', 'IRON', '-IRON', '-BRONZE', '-SILVER', '-GOLD', '-DIAMOND']

output = []
output.append('# 🚇 AYAŞ TÜNELİ - 2 SENELİK BACKTEST RAPORU (120h Penceresi)')
output.append(f'Tarih: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
output.append('')
output.append('## Özet')
output.append('')
output.append('| Tier | Sayı | Oran |')
output.append('| :--- | :---: | :---: |')

for t in tier_order:
    count = len(df_res[df_res['tier'] == t])
    pct = count/total*100 if total > 0 else 0
    output.append(f'| {t} | {count} | {pct:.1f}% |')

# Grouped
d = len(df_res[df_res['tier'] == 'DIAMOND'])
g = len(df_res[df_res['tier'] == 'GOLD'])
s = len(df_res[df_res['tier'] == 'SILVER'])
b = len(df_res[df_res['tier'] == 'BRONZE'])
i = len(df_res[df_res['tier'] == 'IRON'])
neg_count = total - d - g - s - b - i

output.append('')
output.append(f'**Ralli (D+G+S):** {d+g+s} ({(d+g+s)/total*100:.1f}%)')
output.append(f'**Nötr (Bronze+Iron):** {b+i} ({(b+i)/total*100:.1f}%)')
output.append(f'**Kayıp (-tierlar):** {neg_count} ({neg_count/total*100:.1f}%)')
output.append('')

# Daily breakdown
output.append('## Günlük Detay')
output.append('')

dates = sorted(df_res['date'].unique())
all_coins = set()

for date in dates:
    day_data = df_res[df_res['date'] == date]
    n = len(day_data)
    
    counts = {t: len(day_data[day_data['tier'] == t]) for t in tier_order}
    positive = counts['DIAMOND'] + counts['GOLD'] + counts['SILVER']
    hit_pct = positive/n*100 if n > 0 else 0
    
    coins = []
    for _, r in day_data.iterrows():
        all_coins.add(r['symbol'])
        if r['tier'] in ['DIAMOND', 'GOLD', 'SILVER']:
            coins.append(f"{r['symbol']}({r['tier'][0]}+{r['gain']:.0f}%)")
        else:
            coins.append(f"{r['symbol']}({r['tier']}:{r['loss']:.0f}%)")
    
    coins_str = ', '.join(coins[:4])
    if len(coins) > 4: coins_str += f' +{len(coins)-4}'
    
    neg = sum(counts[t] for t in ['-IRON', '-BRONZE', '-SILVER', '-GOLD', '-DIAMOND'])
    tier_str = f"💎{counts['DIAMOND']} 🥇{counts['GOLD']} 🥈{counts['SILVER']} 🥉{counts['BRONZE']} 🔩{counts['IRON']} ❌{neg}"
    
    output.append(f'**{date}** | {n} sin | {tier_str} | {hit_pct:.0f}% | {coins_str}')

output.append('')
output.append(f'## Koinler ({len(all_coins)} adet)')
output.append(', '.join(sorted(all_coins)))

with open('analysis/ayas_tuneli_2y_120h_rapor.md', 'w') as f:
    f.write('\n'.join(output))

print(f"\nRapor kaydedildi: analysis/ayas_tuneli_1y_rapor.md")
print(f"Ralli: {d+g+s} ({(d+g+s)/total*100:.1f}%), Nötr: {b+i} ({(b+i)/total*100:.1f}%), Kayıp: {neg_count} ({neg_count/total*100:.1f}%)")
