"""
Bootstrap Coin Distributions Script

Tüm coinler için rally distribution'ları hesaplar ve kaydeder.
İlk kurulum veya periyodik güncelleme için kullanılır.

Usage:
    # Tüm coinler
    python scripts/bootstrap_coin_distributions.py --all-symbols
    
    # Tek coin
    python scripts/bootstrap_coin_distributions.py --symbol BTCUSDT
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import argparse
import pandas as pd
from tezaver.core.config import DEFAULT_COINS
from tezaver.core.logging_utils import get_logger
from tezaver.core.coin_cell_paths import get_coin_profile_dir, get_fast15_rallies_path, get_coin_data_dir
from tezaver.rally.coin_distribution import CoinDistributionAnalyzer
from tezaver.rally.rally_start_detector import find_true_rally_start


logger = get_logger(__name__)


def bootstrap_symbol(symbol: str, recompute_rally_start: bool = False):
    """
    Bir coin için distribution hesapla ve kaydet.
    
    Args:
        symbol: Coin symbolu
        recompute_rally_start: Rally start'ları yeniden hesapla (daha doğru gain için)
    """
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing {symbol}...")
    logger.info(f"{'='*60}")
    
    # Rally dosyasını yükle
    rally_file = get_fast15_rallies_path(symbol)
    
    if not rally_file.exists():
        logger.warning(f"❌ {symbol}: Rally dosyası bulunamadı: {rally_file}")
        return False
    
    try:
        rallies_df = pd.read_parquet(rally_file)
        logger.info(f"✓ {symbol}: {len(rallies_df)} rally yüklendi")
    except Exception as e:
        logger.error(f"❌ {symbol}: Rally dosyası okunamadı: {e}")
        return False
    
    # Rally start'ları yeniden hesapla (opsiyonel)
    if recompute_rally_start:
        logger.info(f"Rally start'ları yeniden hesaplanıyor...")
        rallies_df = _recompute_rally_starts(symbol, rallies_df)
    
    # Distribution hesapla
    analyzer = CoinDistributionAnalyzer()
    distribution = analyzer.compute_distribution(symbol, rallies_df)
    
    # Kaydet
    output_path = analyzer.save_distribution(symbol, distribution)
    
    # Özet
    logger.info(f"\n{symbol} Distribution Özeti:")
    logger.info(f"  Toplam Rally: {distribution['total_rallies']}")
    logger.info(f"  Diamond Eşiği (p99): {distribution['gain_percentiles']['p99']*100:.1f}%")
    logger.info(f"  Gold Eşiği (p90): {distribution['gain_percentiles']['p90']*100:.1f}%")
    logger.info(f"  Silver Eşiği (p70): {distribution['gain_percentiles']['p70']*100:.1f}%")
    logger.info(f"  Median Kazanç (p50): {distribution['gain_percentiles']['p50']*100:.1f}%")
    logger.info(f"  Tipik Pullback: {distribution['volatility_profile']['typical_pullback']*100:.1f}%")
    logger.info(f"  Kaydedildi: {output_path}")
    
    return True


def _recompute_rally_starts(symbol: str, rallies_df: pd.DataFrame) -> pd.DataFrame:
    """
    Rally start'ları yeniden hesapla (optional, daha doğru gain için).
    
    NOT: Bu features/15m datayı gerektirir, yoksa skip eder.
    """
    
    # Load 15m data
    features_dir = get_coin_data_dir(symbol) / 'features'
    features_file = features_dir / "features_15m.parquet"
    
    if not features_file.exists():
        logger.warning(f"Features 15m bulunamadı, rally start yeniden hesaplanamıyor")
        return rallies_df
    
    try:
        df_15m = pd.read_parquet(features_file)
        df_15m = df_15m.sort_values('timestamp').reset_index(drop=True)
    except Exception as e:
        logger.error(f"Features yüklenemedi: {e}")
        return rallies_df
    
    # Her rally için start'ı yeniden hesapla
    updated_rallies = []
    
    for idx, rally in rallies_df.iterrows():
        # Peak bilgileri
        peak_time = rally['peak_time']
        peak_price = rally['peak_price']
        
        # Peak index'ini bul
        peak_idx = df_15m[df_15m['timestamp'] == peak_time].index
        
        if len(peak_idx) == 0:
            # Peak bulunamadı, skip
            updated_rallies.append(rally.to_dict())
            continue
        
        peak_idx = peak_idx[0]
        
        # Rally start bul
        start_info = find_true_rally_start(df_15m, peak_idx, peak_price)
        
        # Rally dict'i güncelle
        rally_dict = rally.to_dict()
        rally_dict['rally_start_idx'] = start_info['rally_start_idx']
        rally_dict['rally_start_price'] = start_info['rally_start_price']
        rally_dict['rally_start_time'] = start_info['rally_start_time']
        rally_dict['true_gain_pct'] = start_info['true_gain_pct']
        rally_dict['bars_duration'] = start_info['bars_duration']
        rally_dict['rally_start_method'] = start_info['method']
        rally_dict['rally_start_confidence'] = start_info['confidence']
        
        updated_rallies.append(rally_dict)
    
    logger.info(f"Rally start'ları yeniden hesaplandı ({len(updated_rallies)} rally)")
    return pd.DataFrame(updated_rallies)


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap Coin Distributions - Her coin için rally distribution hesapla"
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--symbol",
        type=str,
        help="Tek coin (örn: BTCUSDT)"
    )
    group.add_argument(
        "--all-symbols",
        action="store_true",
        help="Tüm coinler (DEFAULT_COINS)"
    )
    
    parser.add_argument(
        "--recompute-rally-start",
        action="store_true",
        help="Rally start'ları yeniden hesapla (daha doğru gain, ama yavaş)"
    )
    
    args = parser.parse_args()
    
    if args.symbol:
        symbols = [args.symbol]
    else:
        symbols = DEFAULT_COINS
    
    logger.info("="*60)
    logger.info("BOOTSTRAP COIN DISTRIBUTIONS")
    logger.info("="*60)
    logger.info(f"Coin sayısı: {len(symbols)}")
    logger.info(f"Rally start yeniden hesaplansın mı: {args.recompute_rally_start}")
    logger.info("")
    
    success_count = 0
    failed = []
    
    for symbol in symbols:
        try:
            success = bootstrap_symbol(symbol, args.recompute_rally_start)
            if success:
                success_count += 1
            else:
                failed.append(symbol)
        except Exception as e:
            logger.error(f"❌ {symbol}: Hata: {e}", exc_info=True)
            failed.append(symbol)
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("BOOTSTRAP TAMAMLANDI")
    logger.info("="*60)
    logger.info(f"Başarılı: {success_count}/{len(symbols)}")
    
    if failed:
        logger.warning(f"Başarısız: {len(failed)}")
        logger.warning(f"  {', '.join(failed)}")
    else:
        logger.info("✓ Tüm coinler başarıyla işlendi!")
    
    logger.info("\nDistribution dosyaları:")
    logger.info("  data/coin_profiles/{SYMBOL}/rally_distribution.json")


if __name__ == "__main__":
    main()
