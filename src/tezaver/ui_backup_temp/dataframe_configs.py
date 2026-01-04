"""
Streamlit dataframe column configurations.
Reusable configs to avoid code duplication.
"""

import streamlit as st
from tezaver.ui.i18n_tr import COLUMN_LABELS, METRIC_TOOLTIPS


def get_pattern_column_config() -> dict:
    """
    Standard column config for pattern dataframes.
    Used in trustworthy and betrayal pattern tables.
    
    Returns:
        Dictionary of column configurations for Streamlit dataframe
    """
    return {
        "trigger": st.column_config.TextColumn(
            COLUMN_LABELS.get("trigger", "Tetikleyici"),
            help=METRIC_TOOLTIPS.get("trigger", ""),
        ),
        "timeframe": st.column_config.TextColumn(
            COLUMN_LABELS.get("timeframe", "Zaman Dilimi"),
            help=METRIC_TOOLTIPS.get("timeframe", ""),
        ),
        "sample_count": st.column_config.NumberColumn(
            COLUMN_LABELS.get("sample_count", "Örnek Sayısı"),
            help=METRIC_TOOLTIPS.get("sample_count", ""),
        ),
        "hit_5p_rate": st.column_config.NumberColumn(
            COLUMN_LABELS.get("hit_5p_rate", "≥ %5 Başarı"),
            help=METRIC_TOOLTIPS.get("hit_5p_rate", ""),
            format="%.2f",
        ),
        "hit_10p_rate": st.column_config.NumberColumn(
            COLUMN_LABELS.get("hit_10p_rate", "≥ %10 Başarı"),
            help=METRIC_TOOLTIPS.get("hit_10p_rate", ""),
            format="%.2f",
        ),
        "hit_20p_rate": st.column_config.NumberColumn(
            COLUMN_LABELS.get("hit_20p_rate", "≥ %20 Başarı"),
            help=METRIC_TOOLTIPS.get("hit_20p_rate", ""),
            format="%.2f",
        ),
        "trust_score": st.column_config.ProgressColumn(
            COLUMN_LABELS.get("trust_score", "Güven Skoru"),
            help=METRIC_TOOLTIPS.get("trust_score", ""),
            format="%.2f",
            min_value=0,
            max_value=1,
        ),
    }


def get_rally_family_column_config() -> dict:
    """
    Column config for rally family dataframes.
    
    Returns:
        Dictionary of column configurations for Streamlit dataframe
    """
    return {
        "base_timeframe": st.column_config.TextColumn(
            COLUMN_LABELS["base_timeframe"],
            help=METRIC_TOOLTIPS["base_timeframe"],
        ),
        "rally_class": st.column_config.TextColumn(
            COLUMN_LABELS["rally_class"],
            help=METRIC_TOOLTIPS["rally_class"],
        ),
        "family_id": st.column_config.TextColumn(
            COLUMN_LABELS["family_id"],
            help=METRIC_TOOLTIPS["family_id"],
        ),
        "sample_count": st.column_config.NumberColumn(
            COLUMN_LABELS["sample_count"],
            help=METRIC_TOOLTIPS["sample_count"],
        ),
        "trust_score": st.column_config.ProgressColumn(
            COLUMN_LABELS["trust_score"],
            help=METRIC_TOOLTIPS["trust_score"],
            format="%.2f",
            min_value=0,
            max_value=1,
        ),
        "hit_5p_rate": st.column_config.NumberColumn(
            COLUMN_LABELS["hit_5p_rate"],
            help=METRIC_TOOLTIPS["hit_5p_rate"],
            format="%.2f"
        ),
        "hit_10p_rate": st.column_config.NumberColumn(
            COLUMN_LABELS["hit_10p_rate"],
            help=METRIC_TOOLTIPS["hit_10p_rate"],
            format="%.2f"
        ),
        "hit_20p_rate": st.column_config.NumberColumn(
            COLUMN_LABELS["hit_20p_rate"],
            help=METRIC_TOOLTIPS["hit_20p_rate"],
            format="%.2f"
        ),
    }


def get_recent_rally_column_config() -> dict:
    """
    Column config for recent rally listing tables.
    
    Returns:
        Dictionary of column configurations for Streamlit dataframe
    """
    return {
        "timestamp": st.column_config.DatetimeColumn(
            COLUMN_LABELS["timestamp"],
            help=METRIC_TOOLTIPS["timestamp"],
            format="D MMM YYYY, HH:mm"
        ),
        "trigger": st.column_config.TextColumn(
            COLUMN_LABELS["trigger"],
            help=METRIC_TOOLTIPS["trigger"],
        ),
        "rally_label": st.column_config.TextColumn(
            COLUMN_LABELS["rally_label"],
            help=METRIC_TOOLTIPS["rally_label"],
        ),
        "future_max_gain_pct": st.column_config.NumberColumn(
            COLUMN_LABELS["future_max_gain_pct"],
            help=METRIC_TOOLTIPS["future_max_gain_pct"],
            format="%.2f"
        ),
        "future_max_loss_pct": st.column_config.NumberColumn(
            COLUMN_LABELS["future_max_loss_pct"],
            help=METRIC_TOOLTIPS["future_max_loss_pct"],
            format="%.2f"
        ),
    }
