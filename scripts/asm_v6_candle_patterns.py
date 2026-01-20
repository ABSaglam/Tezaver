#!/usr/bin/env python3
"""
ASM v6 - Phase 3: Candle Pattern Detector

Detects bearish reversal patterns for enhanced exit logic
"""

class CandlePatternDetector:
    """Detects candle patterns for exit signals"""
    
    @staticmethod
    def is_bearish_engulfing(prev_candle, current_candle):
        """
        Bearish Engulfing: Red candle fully engulfs previous green candle
        
        Conditions:
        - Previous candle is green (close > open)
        - Current candle is red (close < open)
        - Current open > previous close
        - Current close < previous open
        """
        prev_green = prev_candle['close'] > prev_candle['open']
        curr_red = current_candle['close'] < current_candle['open']
        
        if not (prev_green and curr_red):
            return False
        
        # Full engulfment
        engulfed = (current_candle['open'] > prev_candle['close'] and
                   current_candle['close'] < prev_candle['open'])
        
        return engulfed
    
    @staticmethod
    def is_upper_wick_rejection(candle, wick_to_body_ratio=2.0):
        """
        Upper Wick Rejection: Long upper wick indicates selling pressure
        
        Conditions:
        - Upper wick is at least 2x the body size
        - Indicates failed attempt to push higher
        """
        body = abs(candle['close'] - candle['open'])
        upper_wick = candle['high'] - max(candle['close'], candle['open'])
        
        # Avoid division by zero
        if body < 0.0001:
            return False
        
        is_rejection = upper_wick > body * wick_to_body_ratio
        
        return is_rejection
    
    @staticmethod
    def is_shooting_star(candle, wick_to_body_ratio=3.0, lower_wick_max_ratio=0.3):
        """
        Shooting Star: Strong bearish reversal
        
        Conditions:
        - Long upper wick (3x body)
        - Small or no lower wick
        - Body near the low
        """
        body = abs(candle['close'] - candle['open'])
        upper_wick = candle['high'] - max(candle['close'], candle['open'])
        lower_wick = min(candle['close'], candle['open']) - candle['low']
        
        if body < 0.0001:
            return False
        
        has_long_upper = upper_wick > body * wick_to_body_ratio
        has_small_lower = lower_wick < body * lower_wick_max_ratio
        
        return has_long_upper and has_small_lower
    
    @staticmethod
    def is_doji(candle, body_to_range_ratio=0.1):
        """
        Doji: Indecision candle, small body relative to range
        
        Conditions:
        - Body is less than 10% of total range
        - Indicates indecision / potential reversal
        """
        body = abs(candle['close'] - candle['open'])
        range_size = candle['high'] - candle['low']
        
        if range_size < 0.0001:
            return False
        
        is_doji = (body / range_size) < body_to_range_ratio
        
        return is_doji
    
    @staticmethod
    def detect_all_patterns(prev_candle, current_candle):
        """
        Detect all patterns and return list of detected patterns
        
        Returns:
            list of pattern names detected
        """
        patterns = []
        
        if CandlePatternDetector.is_bearish_engulfing(prev_candle, current_candle):
            patterns.append("BEARISH_ENGULFING")
        
        if CandlePatternDetector.is_upper_wick_rejection(current_candle):
            patterns.append("UPPER_WICK_REJECTION")
        
        if CandlePatternDetector.is_shooting_star(current_candle):
            patterns.append("SHOOTING_STAR")
        
        if CandlePatternDetector.is_doji(current_candle):
            patterns.append("DOJI")
        
        return patterns

def test_pattern_detector():
    """Test pattern detection with sample candles"""
    print("🧪 Testing Candle Pattern Detector")
    print("="*80)
    
    # Test 1: Bearish Engulfing
    prev = {'open': 100, 'high': 105, 'low': 99, 'close': 104}  # Green
    curr = {'open': 106, 'high': 107, 'low': 97, 'close': 98}   # Red, engulfs
    
    print("\n📊 Test 1: Bearish Engulfing")
    print(f"  Previous: {prev}")
    print(f"  Current: {curr}")
    patterns = CandlePatternDetector.detect_all_patterns(prev, curr)
    print(f"  Detected: {patterns}")
    
    # Test 2: Upper Wick Rejection
    candle = {'open': 100, 'high': 110, 'low': 99, 'close': 101}  # Long upper wick
    
    print("\n📊 Test 2: Upper Wick Rejection")
    print(f"  Candle: {candle}")
    patterns = CandlePatternDetector.detect_all_patterns(prev, candle)
    print(f"  Detected: {patterns}")
    
    # Test 3: Shooting Star
    candle = {'open': 100, 'high': 115, 'low': 99.5, 'close': 100.5}  # Classic shooting star
    
    print("\n📊 Test 3: Shooting Star")
    print(f"  Candle: {candle}")
    patterns = CandlePatternDetector.detect_all_patterns(prev, candle)
    print(f"  Detected: {patterns}")
    
    # Test 4: Doji
    candle = {'open': 100, 'high': 105, 'low': 95, 'close': 100.5}  # Small body, large range
    
    print("\n📊 Test 4: Doji")
    print(f"  Candle: {candle}")
    patterns = CandlePatternDetector.detect_all_patterns(prev, candle)
    print(f"  Detected: {patterns}")

if __name__ == "__main__":
    test_pattern_detector()
    print("\n✅ Phase 3 Complete!")
