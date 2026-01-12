"""
Ayaş Sniper Pro - 15m Ultra-Fast Backtest
Simulates precision entries and exits for Ayaş Tüneli signals.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tezaver.core import config, coin_cell_paths
from tezaver.core.rally_store import RallyStore
from tezaver.features.indicator_engine import build_features_for_history_df

store = RallyStore()

# Strategy Parameters
TUNEL = {
    'TREND': {'atr_min': 15.0, 'rsi_min': 55, 'rsi_max': 70},
    'NINJA': {'atr_min': 12.0, 'rsi_min': 60, 'rsi_max': 75}
}

SNIPER_PARAMS = {
    'TRAILING_ATR_MULT': 1.5,
    'MIN_PROFIT_TO_BE': 3.0,
    'EXIT_WINDOW_HOURS': 72,
    'ENTRY_TIMEOUT_HOURS': 24 # Sinyalden sonra 24 saat içinde tetiklenmezse iptal
}

def simulate_sniper_trade(df_15m, signal_row, signal_time, mode='D-CLOSE'):
    """
    Simulates a trade with 15m resolution.
    Modes:
    - D-CLOSE: Enter at daily close price immediately.
    - HIGH-BREAK: Enter when 15m price > Daily High of signal day.
    - MACD-GREEN: Enter when 15m MACD histogram becomes green.
    """
    if df_15m.empty: return None
    
    df_trade = df_15m[df_15m['datetime'] > signal_time].copy()
    if df_trade.empty: return None
    
    entry_price = None
    entry_time = None
    daily_high = signal_row['high']
    
    # 1. Entry Phase
    for i, row in df_trade.iterrows():
        # Entry Timeout check
        if row['datetime'] > signal_time + timedelta(hours=SNIPER_PARAMS['ENTRY_TIMEOUT_HOURS']):
            break
            
        if mode == 'D-CLOSE':
            entry_price = signal_row['close']
            entry_time = signal_time
            break
        elif mode == 'HIGH-BREAK':
            if row['high'] > daily_high:
                entry_price = daily_high * 1.001 # Small offset
                entry_time = row['datetime']
                break
        elif mode == 'MACD-GREEN':
            # Indicator engine computes 'macd_hist_color' as 'green' for pos_inc
            if row.get('macd_hist_color') == 'green':
                entry_price = row['close']
                entry_time = row['datetime']
                break
    
    if entry_price is None: return None
    
    # 2. Execution Phase
    df_exec = df_trade[df_trade['datetime'] >= entry_time].copy()
    if df_exec.empty: return None
    
    current_stop = entry_price * (1 - (SNIPER_PARAMS['TRAILING_ATR_MULT'] * df_exec.iloc[0].get('atr', entry_price*0.02) / entry_price))
    max_price = entry_price
    exit_price = None
    exit_time = None
    exit_reason = None
    
    for _, row in df_exec.iterrows():
        if row['high'] > max_price:
            max_price = row['high']
            new_stop = max_price - (SNIPER_PARAMS['TRAILING_ATR_MULT'] * row['atr'])
            if new_stop > current_stop:
                current_stop = new_stop
        
        gain = (max_price - entry_price) / entry_price * 100
        if gain >= SNIPER_PARAMS['MIN_PROFIT_TO_BE']:
            if current_stop < entry_price:
                current_stop = entry_price
        
        if row['low'] <= current_stop:
            exit_price = current_stop
            exit_time = row['datetime']
            exit_reason = 'STOP'
            break
            
        if row['datetime'] > signal_time + timedelta(hours=SNIPER_PARAMS['EXIT_WINDOW_HOURS']):
            exit_price = row['close']
            exit_time = row['datetime']
            exit_reason = 'TIME'
            break
            
    if exit_price:
        pnl_pct = (exit_price - entry_price) / entry_price * 100
        return {
            'entry_mode': mode,
            'entry_price': entry_price,
            'entry_time': entry_time,
            'exit_price': exit_price,
            'exit_time': exit_time,
            'exit_reason': exit_reason,
            'max_gain': (max_price - entry_price) / entry_price * 100,
            'pnl': pnl_pct
        }
    return None

def main():
    start_date = datetime.now() - timedelta(days=90) # Start with 90 days for speed
    results = []

    print(f"Ayaş Sniper Pro simülasyonu başlıyor (Son { (datetime.now()-start_date).days } gün)...")
    
    for idx, symbol in enumerate(config.DEFAULT_COINS):
        if idx % 50 == 0:
            print(f"[{idx}/{len(config.DEFAULT_COINS)}] {symbol}")
            
        try:
            path_1d = coin_cell_paths.get_history_file(symbol, '1d')
            path_4h = coin_cell_paths.get_history_file(symbol, '4h')
            path_15m_feat = coin_cell_paths.get_coin_data_dir(symbol) / "features_15m.parquet"
            
            if not path_1d.exists() or not path_4h.exists() or not path_15m_feat.exists(): 
                continue
            
            df_1d = pd.read_parquet(path_1d)
            df_1d['datetime'] = df_1d['datetime'].dt.tz_localize(None)
            df_4h = pd.read_parquet(path_4h)
            df_4h['datetime'] = df_4h['datetime'].dt.tz_localize(None)
            df_15m = pd.read_parquet(path_15m_feat)
            df_15m['datetime'] = df_15m['datetime'].dt.tz_localize(None)
            
            if len(df_1d) < 20: continue
            
            # Simple Daily indicators (ATR/RSI)
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
                    # Test Multiple Modes
                    for mode in ['D-CLOSE', 'HIGH-BREAK', 'MACD-GREEN']:
                        trade_res = simulate_sniper_trade(df_15m, row, row['datetime'], mode=mode)
                        
                        if trade_res:
                            results.append({
                                'date': day_ts.strftime('%Y-%m-%d'),
                                'symbol': symbol.replace('USDT',''),
                                'type': 'TREND' if is_trend else 'NINJA',
                                'mode': mode,
                                'pnl': round(trade_res['pnl'], 2),
                                'max_gain': round(trade_res['max_gain'], 2),
                                'reason': trade_res['exit_reason']
                            })
        except Exception as e:
            continue

    if not results:
        print("Sinyal bulunamadı.")
        return

    df_res = pd.DataFrame(results)
    
    # Comparison Table
    summary = df_res.groupby('mode').agg({
        'pnl': ['count', 'mean', 'sum'],
        'max_gain': 'mean'
    })
    summary.columns = ['Count', 'Avg PNL %', 'Total PNL %', 'Avg Max %']
    print("\n=== STRATEJİ KARŞILAŞTIRMASI ===")
    print(summary)

    # Save summary
    report_path = 'analysis/ayas_sniper_comparison.md'
    with open(report_path, 'w') as f:
        f.write('# 🎯 AYAŞ SNIPER PRO - STRATEJİ KARŞILAŞTIRMASI\n\n')
        f.write(f'Tarih: {datetime.now().strftime("%Y-%m-%d %H:%M")}\n\n')
        f.write('## Strateji Özeti\n\n')
        f.write(summary.to_markdown())
        f.write('\n\n')
        
        f.write('## Detaylı Karşılaştırma (Son Sinyaller)\n\n')
        f.write('| Tarih | Sembol | Tip | Mod | Net PNL | Max % | Neden |\n')
        f.write('| :--- | :--- | :---: | :---: | :---: | :---: | :--- |\n')
        for _, r in df_res.sort_values('date', ascending=False).head(200).iterrows():
            f.write(f'| {r["date"]} | {r["symbol"]} | {r["type"]} | {r["mode"]} | {r["pnl"]}% | {r["max_gain"]}% | {r["reason"]} |\n')

    print(f"\nKarşılaştırmalı rapor kaydedildi: {report_path}")

if __name__ == "__main__":
    main()
