#!/usr/bin/env python3
"""
🔬 RALLY DNA EXTRACTOR — 26 Rallinin Parmak İzi Çıkarımı

Her rallinin benzersiz karakterini çıkarır:
- Momentum karakteri (hızlı/yavaş start)
- Volume profili (spike/consistent)
- EMA dance pattern (erken/geç alignment)
- Peak journey (doğrudan/pullback'li)
- Exhaustion pattern (ani/kademeli)
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime

class RallyDNAExtractor:
    """Extracts unique fingerprint for each rally"""
    
    def __init__(self, rally_data_path):
        with open(rally_data_path, 'r') as f:
            self.rally_data = json.load(f)
    
    def extract_momentum_character(self, candles):
        """
        Momentum karakteri - İlk 10 mumda nasıl hareket etti?
        
        Returns:
            - start_type: 'EXPLOSIVE', 'AGGRESSIVE', 'GRADUAL', 'SLOW'
            - first_momentum: İlk 5 mumun ortalama body yüzdesi
            - momentum_acceleration: Momentum artış hızı
        """
        if len(candles) < 10:
            return None
        
        first_5 = candles[:5]
        first_10 = candles[:10]
        
        # İlk 5 mumun body ortalaması
        bodies_first5 = [abs(c['close'] - c['open']) / c['open'] * 100 for c in first_5]
        avg_body_first5 = np.mean(bodies_first5)
        
        # İlk 10 mumun body ortalaması
        bodies_first10 = [abs(c['close'] - c['open']) / c['open'] * 100 for c in first_10]
        avg_body_first10 = np.mean(bodies_first10)
        
        # Momentum acceleration (5-10 arası artış)
        second_5 = candles[5:10]
        bodies_second5 = [abs(c['close'] - c['open']) / c['open'] * 100 for c in second_5]
        avg_body_second5 = np.mean(bodies_second5)
        
        acceleration = avg_body_second5 - avg_body_first5
        
        # Start type classification
        if avg_body_first5 > 1.5:
            start_type = 'EXPLOSIVE'
        elif avg_body_first5 > 1.0:
            start_type = 'AGGRESSIVE'
        elif avg_body_first5 > 0.5:
            start_type = 'GRADUAL'
        else:
            start_type = 'SLOW'
        
        return {
            'start_type': start_type,
            'first_momentum': round(avg_body_first5, 3),
            'momentum_acceleration': round(acceleration, 3),
            'avg_body_first10': round(avg_body_first10, 3)
        }
    
    def extract_volume_profile(self, candles):
        """
        Volume profili - Hacim nasıl gelişti?
        
        Returns:
            - profile_type: 'SPIKE', 'STEADY_HIGH', 'BUILDING', 'IRREGULAR'
            - peak_volume_candle: En yüksek hacim hangi mumda?
            - volume_consistency: Hacim ne kadar tutarlı?
        """
        if len(candles) < 10:
            return None
        
        vol_ratios = [c['vol_ratio'] for c in candles[:20] if c['vol_ratio'] is not None]
        
        if not vol_ratios:
            return None
        
        # Peak volume location
        peak_vol_idx = vol_ratios.index(max(vol_ratios))
        
        # Volume consistency (std dev)
        vol_std = np.std(vol_ratios)
        vol_mean = np.mean(vol_ratios)
        
        # Profile type
        if max(vol_ratios) > 4.0 and peak_vol_idx < 5:
            profile_type = 'SPIKE'
        elif vol_std < 0.5:
            profile_type = 'STEADY_HIGH'
        elif peak_vol_idx > len(vol_ratios) / 2:
            profile_type = 'BUILDING'
        else:
            profile_type = 'IRREGULAR'
        
        return {
            'profile_type': profile_type,
            'peak_volume_candle': peak_vol_idx,
            'volume_mean': round(vol_mean, 2),
            'volume_std': round(vol_std, 2),
            'volume_max': round(max(vol_ratios), 2)
        }
    
    def extract_ema_dance(self, candles):
        """
        EMA dance pattern - EMA'lar nasıl hizalandı?
        
        Returns:
            - alignment_speed: Kaç mumda tam hizalanma oldu?
            - reclaim_pattern: EMA9 kaç kez kırıldı/geri alındı?
            - alignment_stability: Hizalanma ne kadar stabil?
        """
        if len(candles) < 10:
            return None
        
        # İlk tam hizalanma (EMA9 > EMA21 > EMA50)
        alignment_candle = None
        for i, c in enumerate(candles):
            if c.get('ema9') and c.get('ema21') and c.get('ema50'):
                if c['ema9'] > c['ema21'] > c['ema50']:
                    alignment_candle = i
                    break
        
        # EMA9 reclaim count (geri alınma sayısı)
        reclaim_count = 0
        below_ema9 = False
        
        for c in candles[:20]:
            if c.get('ema9') and c.get('close'):
                if c['close'] < c['ema9']:
                    below_ema9 = True
                elif below_ema9 and c['close'] > c['ema9']:
                    reclaim_count += 1
                    below_ema9 = False
        
        # Alignment stability (ilk 20 mumda kaç tanesinde aligned)
        aligned_count = 0
        for c in candles[:20]:
            if c.get('ema9') and c.get('ema21') and c.get('ema50'):
                if c['ema9'] > c['ema21'] > c['ema50']:
                    aligned_count += 1
        
        stability = aligned_count / min(20, len(candles))
        
        return {
            'alignment_speed': alignment_candle if alignment_candle is not None else 99,
            'reclaim_count': reclaim_count,
            'alignment_stability': round(stability, 2)
        }
    
    def extract_peak_journey(self, candles):
        """
        Peak journey - Peak'e nasıl ulaşıldı?
        
        Returns:
            - journey_type: 'DIRECT', 'PULLBACK_ONCE', 'ZIGZAG', 'GRIND'
            - time_to_peak: Kaç mumda peak'e ulaşıldı?
            - pullback_count: Kaç kez geri çekilme oldu?
            - max_pullback_depth: En derin geri çekilme yüzdesi
        """
        if len(candles) < 5:
            return None
        
        # Find peak
        highs = [c['high'] for c in candles]
        peak_idx = highs.index(max(highs))
        
        # Pullback detection
        pullbacks = []
        local_high = candles[0]['high']
        
        for i in range(1, peak_idx + 1):
            c = candles[i]
            if c['high'] > local_high:
                local_high = c['high']
            elif c['low'] < local_high * 0.98:  # 2% pullback
                pullback_depth = (c['low'] / local_high - 1) * 100
                pullbacks.append(pullback_depth)
        
        # Journey type
        if len(pullbacks) == 0:
            journey_type = 'DIRECT'
        elif len(pullbacks) == 1:
            journey_type = 'PULLBACK_ONCE'
        elif len(pullbacks) >= 3:
            journey_type = 'ZIGZAG'
        else:
            journey_type = 'GRIND'
        
        return {
            'journey_type': journey_type,
            'time_to_peak': peak_idx,
            'pullback_count': len(pullbacks),
            'max_pullback_depth': round(min(pullbacks), 2) if pullbacks else 0.0
        }
    
    def extract_exhaustion_pattern(self, candles):
        """
        Exhaustion pattern - Yorgunluk nasıl gelişti?
        
        Returns:
            - exhaustion_type: 'SUDDEN', 'GRADUAL', 'SPIKE_CRASH'
            - peak_to_end_speed: Peak'ten sona kaç mum?
            - exit_volatility: Çıkış sırasında volatilite
        """
        if len(candles) < 10:
            return None
        
        # Find peak
        highs = [c['high'] for c in candles]
        peak_idx = highs.index(max(highs))
        peak_high = max(highs)
        
        # End (son mum)
        end_close = candles[-1]['close']
        
        # Peak to end
        peak_to_end = len(candles) - peak_idx
        
        # Decline from peak
        decline = (end_close / peak_high - 1) * 100
        
        # Post-peak volatility
        if peak_idx < len(candles) - 1:
            post_peak_candles = candles[peak_idx+1:]
            post_peak_ranges = [(c['high'] - c['low']) / c['low'] * 100 for c in post_peak_candles]
            avg_volatility = np.mean(post_peak_ranges) if post_peak_ranges else 0
        else:
            avg_volatility = 0
        
        # Exhaustion type
        if peak_to_end <= 3:
            exhaustion_type = 'SUDDEN'
        elif avg_volatility > 2.0:
            exhaustion_type = 'SPIKE_CRASH'
        else:
            exhaustion_type = 'GRADUAL'
        
        return {
            'exhaustion_type': exhaustion_type,
            'peak_to_end_candles': peak_to_end,
            'decline_pct': round(decline, 2),
            'exit_volatility': round(avg_volatility, 2)
        }
    
    def extract_rally_dna(self, rally):
        """Extract complete DNA fingerprint for a rally"""
        candles = rally['15m_data']
        
        dna = {
            'date': rally['date'],
            'tier': rally['tier'],
            'rally_pct': rally['rally_pct'],
            'total_candles': len(candles),
            
            # Extract all features
            'momentum': self.extract_momentum_character(candles),
            'volume': self.extract_volume_profile(candles),
            'ema_dance': self.extract_ema_dance(candles),
            'peak_journey': self.extract_peak_journey(candles),
            'exhaustion': self.extract_exhaustion_pattern(candles)
        }
        
        return dna
    
    def extract_all_dna(self):
        """Extract DNA for all 26 rallies"""
        print("🔬 Extracting DNA fingerprints for 26 rallies...")
        print("="*80)
        
        all_dna = []
        
        for rally in self.rally_data:
            print(f"\n📅 {rally['date']} ({rally['tier']}, {rally['rally_pct']:+.1f}%)")
            
            dna = self.extract_rally_dna(rally)
            all_dna.append(dna)
            
            # Print summary
            if dna['momentum']:
                print(f"   Momentum: {dna['momentum']['start_type']}")
            if dna['volume']:
                print(f"   Volume: {dna['volume']['profile_type']}")
            if dna['peak_journey']:
                print(f"   Journey: {dna['peak_journey']['journey_type']}")
            if dna['exhaustion']:
                print(f"   Exhaustion: {dna['exhaustion']['exhaustion_type']}")
        
        return all_dna

def main():
    rally_data_path = "/Users/alisaglam/TezaverMac/data/algo_rally_days_15m.json"
    
    extractor = RallyDNAExtractor(rally_data_path)
    all_dna = extractor.extract_all_dna()
    
    # Save DNA
    output_path = "/Users/alisaglam/TezaverMac/data/algo_rally_dna.json"
    with open(output_path, 'w') as f:
        json.dump(all_dna, f, indent=2)
    
    print("\n" + "="*80)
    print(f"✅ DNA extraction complete!")
    print(f"📁 Saved to: {output_path}")
    print(f"📊 Total rallies analyzed: {len(all_dna)}")

if __name__ == "__main__":
    main()
