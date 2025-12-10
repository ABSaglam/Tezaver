"""
Rally Context Analysis
======================

BTCUSDT 15 Dakika rally dataset'i üzerinde Rally Context Score v1 
hesaplama ve analiz fonksiyonları.

Kullanım:
    python -m tezaver.rally.rally_context_analysis
"""

import json
from pathlib import Path
from typing import Dict, Any
import pandas as pd

from tezaver.rally.rally_memory_engine import (
    DEFAULT_BTCUSDT_15M_SWEET_SPOTS,
    add_rally_context_score_v1_column,
)


# =============================================================================
# VERİ YÜKLEME VE KAYDETME
# =============================================================================

def load_btc_15m_rallies() -> pd.DataFrame:
    """BTCUSDT 15 Dakika rally dataset'ini yükler."""
    path = Path("library/fast15_rallies/BTCUSDT/fast15_rallies.parquet")
    if not path.exists():
        raise FileNotFoundError(f"Rally dataset bulunamadı: {path}")
    return pd.read_parquet(path)


def compute_btc_15m_context_scores(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame'e rally_context_score_v1 kolonu ekler."""
    return add_rally_context_score_v1_column(
        df=df,
        config=DEFAULT_BTCUSDT_15M_SWEET_SPOTS,
        column_name="rally_context_score_v1",
    )


def save_btc_15m_with_context(df: pd.DataFrame) -> str:
    """Zenginleştirilmiş dataset'i yeni bir parquet dosyasına yazar."""
    out_path = Path("library/fast15_rallies/BTCUSDT/fast15_rallies_with_context_v1.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return str(out_path)


# =============================================================================
# ANALİZ VE RAPOR ÜRETİMİ
# =============================================================================

def compute_segment_stats(df: pd.DataFrame, score_column: str = "rally_context_score_v1") -> Dict[str, Any]:
    """
    Bir segment için istatistikleri hesaplar.
    
    Returns:
        count, min, max, mean, median, p25, p75, buckets
    """
    if df.empty:
        return {
            "count": 0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "p25": 0.0,
            "p75": 0.0,
            "buckets": {
                "ge_80": 0,
                "between_50_80": 0,
                "lt_50": 0
            }
        }
    
    scores = df[score_column].dropna()
    
    return {
        "count": int(len(scores)),
        "min": round(float(scores.min()), 2),
        "max": round(float(scores.max()), 2),
        "mean": round(float(scores.mean()), 2),
        "median": round(float(scores.median()), 2),
        "p25": round(float(scores.quantile(0.25)), 2),
        "p75": round(float(scores.quantile(0.75)), 2),
        "buckets": {
            "ge_80": int((scores >= 80).sum()),
            "between_50_80": int(((scores >= 50) & (scores < 80)).sum()),
            "lt_50": int((scores < 50).sum())
        }
    }


def build_btc_15m_rally_context_report(df: pd.DataFrame) -> Dict[str, Any]:
    """
    BTCUSDT 15m rally dataset'i için analiz raporu oluşturur.
    
    Args:
        df: rally_context_score_v1 kolonu eklenmiş DataFrame
        
    Returns:
        JSON uyumlu rapor dictionary
    """
    # Segmentleri ayır
    good_filter = (df["quality_score"] >= 70) | (df["future_max_gain_pct"] >= 0.10)
    df_good = df[good_filter]
    df_other = df[~good_filter]
    
    # İstatistikleri hesapla
    stats_all = compute_segment_stats(df)
    stats_good = compute_segment_stats(df_good)
    stats_other = compute_segment_stats(df_other)
    
    # Filter açıklaması ekle
    stats_good["filter"] = "quality_score >= 70 or future_max_gain_pct >= 0.10"
    
    report = {
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "source_dataset": "library/fast15_rallies/BTCUSDT/fast15_rallies.parquet",
        "output_dataset": "library/fast15_rallies/BTCUSDT/fast15_rallies_with_context_v1.parquet",
        "score_column": "rally_context_score_v1",
        "stats": {
            "all": stats_all,
            "good_rallies": stats_good,
            "other_rallies": stats_other
        }
    }
    
    return report


def save_btc_15m_rally_context_report(report: Dict[str, Any]) -> str:
    """Analiz raporunu JSON dosyasına yazar."""
    out_path = Path("data/coin_profiles/BTCUSDT/15m/rally_context_score_report_v1.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return str(out_path)


# =============================================================================
# ANA ÇALIŞTIRMA
# =============================================================================

def run_btc_15m_rally_context_analysis() -> Dict[str, Any]:
    """
    Tam analiz pipeline'ını çalıştırır.
    
    Returns:
        Analiz raporu
    """
    print("📊 BTCUSDT 15m Rally Context Score v1 Analizi")
    print("=" * 50)
    
    # 1. Veri yükle
    print("\n1. Veri yükleniyor...")
    df = load_btc_15m_rallies()
    print(f"   Toplam rally: {len(df)}")
    
    # 2. Skor hesapla
    print("\n2. Rally Context Score v1 hesaplanıyor...")
    df_scored = compute_btc_15m_context_scores(df)
    print(f"   Skor kolonu eklendi: rally_context_score_v1")
    
    # 3. Zenginleştirilmiş dataset'i kaydet
    print("\n3. Dataset kaydediliyor...")
    out_data_path = save_btc_15m_with_context(df_scored)
    print(f"   Kaydedildi: {out_data_path}")
    
    # 4. Rapor oluştur
    print("\n4. Analiz raporu oluşturuluyor...")
    report = build_btc_15m_rally_context_report(df_scored)
    
    # 5. Raporu kaydet
    out_report_path = save_btc_15m_rally_context_report(report)
    print(f"   Kaydedildi: {out_report_path}")
    
    # 6. Özet yazdır
    print("\n" + "=" * 50)
    print("📈 ÖZET İSTATİSTİKLER")
    print("=" * 50)
    
    stats = report["stats"]
    
    print(f"\n🔹 TÜM RALLY'LER ({stats['all']['count']} adet):")
    print(f"   Mean: {stats['all']['mean']:.1f}, Median: {stats['all']['median']:.1f}")
    print(f"   [p25: {stats['all']['p25']:.1f}, p75: {stats['all']['p75']:.1f}]")
    print(f"   Buckets: >=80: {stats['all']['buckets']['ge_80']}, 50-80: {stats['all']['buckets']['between_50_80']}, <50: {stats['all']['buckets']['lt_50']}")
    
    print(f"\n🔹 İYİ RALLY'LER ({stats['good_rallies']['count']} adet):")
    print(f"   Mean: {stats['good_rallies']['mean']:.1f}, Median: {stats['good_rallies']['median']:.1f}")
    print(f"   [p25: {stats['good_rallies']['p25']:.1f}, p75: {stats['good_rallies']['p75']:.1f}]")
    print(f"   Buckets: >=80: {stats['good_rallies']['buckets']['ge_80']}, 50-80: {stats['good_rallies']['buckets']['between_50_80']}, <50: {stats['good_rallies']['buckets']['lt_50']}")
    
    print(f"\n🔹 DİĞER RALLY'LER ({stats['other_rallies']['count']} adet):")
    print(f"   Mean: {stats['other_rallies']['mean']:.1f}, Median: {stats['other_rallies']['median']:.1f}")
    print(f"   [p25: {stats['other_rallies']['p25']:.1f}, p75: {stats['other_rallies']['p75']:.1f}]")
    print(f"   Buckets: >=80: {stats['other_rallies']['buckets']['ge_80']}, 50-80: {stats['other_rallies']['buckets']['between_50_80']}, <50: {stats['other_rallies']['buckets']['lt_50']}")
    
    print("\n✅ Analiz tamamlandı!")
    
    return report


if __name__ == "__main__":
    run_btc_15m_rally_context_analysis()
