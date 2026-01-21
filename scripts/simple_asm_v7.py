#!/usr/bin/env python3
"""
⚡ SIMPLE ASM v7 — EARLY ENTRY, LATE EXIT

Gerçek verilerden öğrenilen basit strateji:
- Entry: İlk 5 candle, minimal koşullar
- Exit: Peak'e yakın (LOWER_HIGH ama daha toleranslı)

Test: 26 rally, optimal +154% hedef
"""

import json

class SimpleASM_v7:
    """Basit ama etkili - gerçek veriye dayalı"""
    
    def __init__(self, rally_data):
        self.candles = rally_data['15m_data']
        self.date = rally_data['date']
        self.tier = rally_data['tier']
        self.rally_pct = rally_data['rally_pct']
    
    def check_early_entry(self, idx):
        """
        İlk 5 candle için basit entry koşulları
        
        Öğrendiğimiz: Signal quality ortalama 0.5-0.8
        Yani çok sıkı olmaya gerek yok
        """
        if idx > 5:  # Sadece ilk 5 candle
            return False
        
        c = self.candles[idx]
        
        # Minimum koşullar
        if not all(c.get(k) for k in ['vol_ratio', 'ema9', 'ema21']):
            return False
        
        # 1. Volume artışı
        vol_ok = c['vol_ratio'] > 1.3
        
        # 2. EMA9 > EMA21
        ema_ok = c['ema9'] > c['ema21']
        
        # Both conditions must be met
        return vol_ok and ema_ok
    
    def check_late_exit(self, entry_idx, current_idx):
        """
        Geç exit - peak'e yakın çık
        
        Öğrendiğimiz: Optimal exit candle 70-90 arası
        LOWER_HIGH kullan ama çok agresif olma
        """
        if current_idx <= entry_idx + 2:
            return False, None
        
        c = self.candles[current_idx]
        
        # Candles since entry
        candles_held = current_idx - entry_idx
        
        # Track max high since entry
        max_high = max(self.candles[i]['high'] for i in range(entry_idx, current_idx))
        
        # CONDITION 1: LOWER HIGH (ama toleranslı - 0.5% değil 1%)
        if current_idx > entry_idx + 5:  # En az 5 candle hold
            if c['high'] < max_high * 0.99:  # 1% threshold (daha toleranslı)
                pnl = (c['close'] / self.candles[entry_idx]['close'] - 1) * 100
                return True, f"LOWER_HIGH (PnL: {pnl:+.2f}%)"
        
        # CONDITION 2: Çok uzun tutma (100 candle = ~25 saat)
        if candles_held >= 100:
            pnl = (c['close'] / self.candles[entry_idx]['close'] - 1) * 100
            return True, f"TIME_LIMIT (PnL: {pnl:+.2f}%)"
        
        # CONDITION 3: Büyük kayıp (-5%)
        pnl = (c['close'] / self.candles[entry_idx]['close'] - 1) * 100
        if pnl < -5.0:
            return True, f"STOP_LOSS (PnL: {pnl:+.2f}%)"
        
        return False, None
    
    def run(self):
        """ASM v7'yi bir rally gününde çalıştır"""
        try:
            # Find entry
            entry_idx = None
            for idx in range(min(6, len(self.candles))):
                if self.check_early_entry(idx):
                    entry_idx = idx
                    break
            
            if entry_idx is None:
                return {
                    'date': self.date,
                    'tier': self.tier,
                    'rally_pct': self.rally_pct,
                    'entry': None,
                    'reason': 'No entry signal in first 5 candles'
                }
            
            entry = self.candles[entry_idx]
            
            # Find exit
            exit_idx = None
            exit_reason = None
            
            for idx in range(entry_idx + 1, len(self.candles)):
                should_exit, reason = self.check_late_exit(entry_idx, idx)
                if should_exit:
                    exit_idx = idx
                    exit_reason = reason
                    break
            
            # If no exit found, exit at end of day
            if exit_idx is None:
                exit_idx = len(self.candles) - 1
                pnl = (self.candles[exit_idx]['close'] / entry['close'] - 1) * 100
                exit_reason = f"EOD (PnL: {pnl:+.2f}%)"
            
            exit_candle = self.candles[exit_idx]
            
            # Calculate results
            pnl = (exit_candle['close'] / entry['close'] - 1) * 100
            
            # Max DD
            trade_candles = self.candles[entry_idx:exit_idx+1]
            max_dd = min((c['low'] / entry['close'] - 1) * 100 for c in trade_candles)
            
            return {
                'date': self.date,
                'tier': self.tier,
                'rally_pct': self.rally_pct,
                'entry_idx': entry_idx,
                'entry_time': entry['timestamp'],
                'entry_price': entry['close'],
                'exit_idx': exit_idx,
                'exit_time': exit_candle['timestamp'],
                'exit_price': exit_candle['close'],
                'exit_reason': exit_reason,
                'pnl': round(pnl, 2),
                'max_dd': round(max_dd, 2),
                'candles_held': exit_idx - entry_idx
            }
        except Exception as e:
            import traceback
            return {
                'date': self.date,
                'tier': self.tier,
                'rally_pct': self.rally_pct,
                'entry': None,
                'reason': f'ERROR: {str(e)[:100]} - {traceback.format_exc()[:200]}'
            }

def test_v7_on_all_rallies():
    """26 rally üzerinde test"""
    rally_data_path = "/Users/alisaglam/TezaverMac/data/algo_rally_days_15m.json"
    
    with open(rally_data_path, 'r') as f:
        rally_data = json.load(f)
    
    print("⚡ SIMPLE ASM v7 — EARLY ENTRY, LATE EXIT")
    print("="*80)
    
    results = []
    
    for rally in rally_data:
        asm = SimpleASM_v7(rally)
        result = asm.run()
        results.append(result)
        
        if result.get('entry_idx') is not None:
            status = "✅" if result['pnl'] > 0 else "❌"
            print(f"\n{status} {result['date']} ({result['tier']}, {result['rally_pct']:+.1f}%)")
            print(f"   Entry: Candle {result['entry_idx']} @ {result['entry_price']:.4f}")
            print(f"   Exit: Candle {result['exit_idx']} @ {result['exit_price']:.4f}")
            print(f"   PnL: {result['pnl']:+.2f}% | Max DD: {result['max_dd']:.2f}%")
            print(f"   Held: {result['candles_held']} candles | Reason: {result['exit_reason']}")
        else:
            print(f"\n⚪ {result['date']}: {result.get('reason', 'Unknown')}")
    
    # FINAL REPORT
    trades = [r for r in results if r.get('entry_idx') is not None]
    
    print("\n" + "="*80)
    print("📊 ASM v7 FINAL REPORT")
    print("="*80)
    
    if trades:
        total_trades = len(trades)
        winners = sum(1 for t in trades if t['pnl'] > 0)
        total_pnl = sum(t['pnl'] for t in trades)
        
        print(f"\nTotal Rallies: 26")
        print(f"Trades Executed: {total_trades}/26 ({total_trades/26*100:.1f}%)")
        print(f"Win Rate: {winners/total_trades*100:.1f}% ({winners}/{total_trades})")
        print(f"Total PnL: {total_pnl:+.2f}%")
        print(f"Avg PnL per Trade: {total_pnl/total_trades:+.2f}%")
        print(f"Worst Max DD: {min(t['max_dd'] for t in trades):.2f}%")
        
        # Compare to optimal
        print(f"\n📊 COMPARISON:")
        print(f"  Optimal (target): 25 trades, +154.32% total")
        print(f"  ASM v7: {total_trades} trades, {total_pnl:+.2f}% total")
        print(f"  Achievement: {(total_pnl/154.32)*100:.1f}% of optimal")
        
        # Save
        output_path = "/Users/alisaglam/TezaverMac/data/asm_v7_results.json"
        with open(output_path, 'w') as f:
            json.dump({
                'summary': {
                    'trades': total_trades,
                    'coverage': total_trades/26*100,
                    'win_rate': winners/total_trades*100,
                    'total_pnl': total_pnl,
                    'avg_pnl': total_pnl/total_trades,
                    'vs_optimal': (total_pnl/154.32)*100
                },
                'trades': trades
            }, f, indent=2)
        
        print(f"\n📁 Results saved: {output_path}")
    else:
        print("\n❌ No trades executed")

if __name__ == "__main__":
    test_v7_on_all_rallies()
