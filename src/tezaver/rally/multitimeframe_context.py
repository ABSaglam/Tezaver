# src/tezaver/rally/multitimeframe_context.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
#  MTC v1 – Sabitler
# ---------------------------------------------------------------------------

# MTC v1'de desteklenen ana zaman dilimleri
DEFAULT_TIMEFRAMES: Tuple[str, ...] = ("15m", "1h", "4h", "1d")

#: Her event için zorunlu metadata kolonları
EVENT_METADATA_COLUMNS: Tuple[str, ...] = (
    "symbol",               # Coin sembolü, örn: "BTCUSDT"
    "event_time",           # Event timestamp (UTC datetime)
    "event_tf",             # Event'in oluştuğu timeframe, örn: "15m", "1h"
    "rally_bucket",         # 5p_10p / 10p_20p / 20p_30p / 30p_plus
    "future_max_gain_pct",  # Entry'den peak'e max kazanç (0.12 = %12)
    "bars_to_peak",         # Peak'e kadar bar sayısı (1–10)
)

#: Rally v2 kalite metrikleri – MTC açısından "opsiyonel zorunlu" sayılabilir.
QUALITY_COLUMNS_OPTIONAL: Tuple[str, ...] = (
    "rally_shape",              # clean / spike / choppy / weak / unknown
    "quality_score",            # 0–100
    "pre_peak_drawdown_pct",    # Peak öncesi max DD (negatif değer)
    "trend_efficiency",         # Net / brüt yol oranı
    "retention_3_pct",          # 3 bar sonra kalan kazanç
    "retention_10_pct",         # 10 bar sonra kalan kazanç
)

#: Her timeframe için takip edilen temel gösterge isimleri.
#: Kolon ismi = <field>_<tf> (ör: rsi_15m, macd_phase_4h)
BASE_SNAPSHOT_FIELDS: Tuple[str, ...] = (
    "rsi",
    "rsi_ema",
    "macd_line",
    "macd_signal",
    "macd_hist",
    "macd_phase",
    "volume_rel",   # vol_rel'den türetilmiş relatif hacim
    "atr_pct",      # atr / close * 100
    "trend_soul",
    "regime",
)


# ---------------------------------------------------------------------------
#  Yardımcı Fonksiyonlar
# ---------------------------------------------------------------------------


def build_snapshot_columns(
    timeframes: Sequence[str] = DEFAULT_TIMEFRAMES,
    base_fields: Sequence[str] = BASE_SNAPSHOT_FIELDS,
) -> List[str]:
    """
    Verilen base_fields ve timeframes seti için snapshot kolon isimlerini üretir.

    Örnek:
        timeframes = ["15m", "1h"]
        base_fields = ["rsi", "macd_phase"]

        -> ["rsi_15m", "rsi_1h", "macd_phase_15m", "macd_phase_1h"]
    """
    cols: List[str] = []
    for tf in timeframes:
        for field in base_fields:
            cols.append(f"{field}_{tf}")
    return cols


def get_required_columns(
    timeframes: Sequence[str] = DEFAULT_TIMEFRAMES,
    include_quality: bool = True,
) -> List[str]:
    """
    MTC v1 için “zorunlu” sayılan kolon listesini üretir.

    - Event metadata kolonları
    - Multi-timeframe snapshot kolonları
    - (Opsiyonel) Rally v2 kalite kolonları
    """
    required: List[str] = list(EVENT_METADATA_COLUMNS)
    required.extend(build_snapshot_columns(timeframes=timeframes))

    if include_quality:
        required.extend(list(QUALITY_COLUMNS_OPTIONAL))

    return required


# ---------------------------------------------------------------------------
#  Ana API – ensure_mtc_columns & validate_mtc_schema
# ---------------------------------------------------------------------------


def ensure_mtc_columns(
    df: pd.DataFrame,
    timeframes: Optional[Sequence[str]] = None,
    include_quality: bool = True,
) -> pd.DataFrame:
    """
    Verilen DataFrame'e MTC v1 şemasına göre eksik kolonları ekler.

    - Eksik kolonları NaN ile doldurur.
    - Kolonları kanonik sıraya göre yeniden sıralar
      (önce required, sonra DF'de ekstra olanlar).

    NOT:
        Bu fonksiyon DF'nin bir kopyası üzerinde çalışır ve
        yeni bir DataFrame döndürür; orijinali inplace değişmez.
    """
    if timeframes is None:
        timeframes = DEFAULT_TIMEFRAMES

    df = df.copy()

    required_cols = get_required_columns(
        timeframes=timeframes,
        include_quality=include_quality,
    )

    # Eksik kolonları ekle
    for col in required_cols:
        if col not in df.columns:
            df[col] = np.nan

    # Kanonik sıralama: önce required, sonra diğer kolonlar
    other_cols = [c for c in df.columns if c not in required_cols]
    ordered_cols = required_cols + other_cols

    # Sadece gerçekten DF'de olan kolonları seç (koruyucu davranış)
    ordered_cols = [c for c in ordered_cols if c in df.columns]

    df = df[ordered_cols]
    return df


@dataclass
class MTCSchemaValidationResult:
    """
    validate_mtc_schema fonksiyonunun sonucunu temsil eder.
    """

    ok: bool
    missing_columns: List[str]


def validate_mtc_schema(
    df: pd.DataFrame,
    timeframes: Optional[Sequence[str]] = None,
    include_quality: bool = True,
    strict: bool = False,
) -> bool:
    """
    DataFrame'in MTC v1 şemasına uyup uymadığını kontrol eder.

    Args:
        df:
            Kontrol edilecek DataFrame.
        timeframes:
            Beklenen timeframeler. None ise DEFAULT_TIMEFRAMES kullanılır.
        include_quality:
            True ise kalite kolonları da zorunlu setin parçası sayılır.
        strict:
            True ise eksik kolon varsa ValueError fırlatır.
            False ise sadece False döner ve log yazar.

    Returns:
        bool: Şema uygun ise True, değilse False.
    """
    if timeframes is None:
        timeframes = DEFAULT_TIMEFRAMES

    required_cols = set(
        get_required_columns(timeframes=timeframes, include_quality=include_quality)
    )
    existing_cols = set(df.columns)

    missing = sorted(required_cols - existing_cols)

    if missing:
        logger.warning(
            "MTC schema validation failed: %d missing columns: %s",
            len(missing),
            ", ".join(missing),
        )
        if strict:
            raise ValueError(
                f"MTC schema validation failed; missing columns: {', '.join(missing)}"
            )
        return False

    # Opsiyonel: bazı hafif tip kontrolleri
    if "event_time" in df.columns and not np.issubdtype(
        df["event_time"].dtype, np.datetime64
    ):
        logger.debug(
            "MTC warning: 'event_time' column is not datetime64 (dtype=%s)",
            df["event_time"].dtype,
        )

    if "event_tf" in df.columns:
        invalid_tf = set(df["event_tf"].dropna().unique()) - set(DEFAULT_TIMEFRAMES)
        if invalid_tf:
            logger.debug(
                "MTC warning: 'event_tf' contains unexpected values: %s",
                ", ".join(map(str, invalid_tf)),
            )

    return True
