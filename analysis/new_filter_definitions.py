# Yeni Filtre Tanımları (Phase 27)
# ==================================
# Analiz Sonucu:
# - Eski TREND (RSI >= 55): %12.5 başarı
# - Eski NINJA (Squeeze + Mid <= 50): %6.0 başarı
#
# Yeni Optimum Filtreler (2 yıllık backtest):
# - Yeni TREND: ATR >= 15% + RSI 55-70 → %23.9 başarı
# - Yeni NINJA: RSI 60-75 + ATR >= 12% → %22.7 başarı
#
# Bu filtreleri DailyRadarEngine'e eklemek için:

NEW_TREND_FILTER = {
    'atr_min': 15.0,      # ATR en az %15
    'rsi_min': 55,        # RSI en az 55
    'rsi_max': 70,        # RSI en fazla 70
}

NEW_NINJA_FILTER = {
    'atr_min': 12.0,      # ATR en az %12
    'rsi_min': 60,        # RSI en az 60
    'rsi_max': 75,        # RSI en fazla 75
}

# Karşılaştırma:
# Eski Filtre: ~%10 başarı oranı
# Yeni Filtre: ~%23 başarı oranı (2.3x iyileşme)
