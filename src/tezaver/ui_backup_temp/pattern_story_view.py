"""
Pattern Story View - Interactive historical pattern/rally viewer.

Shows historical examples of patterns and rally families with:
- Candlestick charts highlighting event times
- Turkish narrative explaining pattern performance
- Multiple example scenarios (best/median/worst)

Purely visualization layer - no trade logic.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import streamlit as st
import pandas as pd
import numpy as np
import json
import logging

from tezaver.wisdom.pattern_stats import get_coin_profile_dir
from tezaver.core.logging_utils import get_logger
from tezaver.ui.explanation_cards import TRIGGER_LABELS_TR

logger = get_logger(__name__)


# ===== Translation Maps =====

TIMEFRAME_TR = {
    "15m": "15 dakika",
    "1h": "1 saat",
    "4h": "4 saat",
    "1d": "1 gün",
    "1w": "1 hafta"
}

RALLY_CLASS_TR = {
    "rally_5p": "%5-10",
    "rally_10p": "%10-20",
    "rally_20p": "%20+"
}


# ===== Data Structures =====

@dataclass
class PatternStoryKey:
    """Key identifying a specific pattern."""
    symbol: str
    trigger: str           # e.g., "rsi_overbought", "vol_spike"
    timeframe: str         # e.g., "1h", "4h", "1d"


@dataclass
class RallyFamilyStoryKey:
    """Key identifying a specific rally family."""
    symbol: str
    rally_class: str       # "rally_5p", "rally_10p", "rally_20p"
    family_id: int
    base_timeframe: str    # "1h", "4h", "1d"


@dataclass
class ExampleEvent:
    """Single example event from pattern/rally history."""
    event_time: pd.Timestamp
    future_max_gain_pct: float
    bars_to_peak: int
    bucket_label: str      # e.g., "%10-20", "%20+"
    # Optional extra fields
    rsi: Optional[float] = None
    volume_rel: Optional[float] = None
    
    @classmethod
    def from_row(cls, row: pd.Series, bucket_label: str = "") -> 'ExampleEvent':
        """Create ExampleEvent from DataFrame row."""
        # Handle timestamp (might be int64 ms)
        event_time = row.get('timestamp', row.get('event_time', row.get('datetime')))
        if pd.notna(event_time):
            event_time = pd.to_datetime(event_time, unit='ms' if isinstance(event_time, (int, np.integer)) else None)
        else:
            event_time = pd.Timestamp.now()
        
        # Calculate bars_to_peak if missing
        bars_to_peak = row.get('bars_to_peak', 5)  # Default estimate
        
        return cls(
            event_time=event_time,
            future_max_gain_pct=row.get('future_max_gain_pct', 0.0),
            bars_to_peak=int(bars_to_peak) if pd.notna(bars_to_peak) else 5,
            bucket_label=bucket_label,
            rsi=row.get('rsi'),
            volume_rel=row.get('vol_rel', row.get('volume_rel'))
        )


@dataclass
class PatternStoryContext:
    """Context for pattern story with stats and examples."""
    key: PatternStoryKey
    stats_row: Dict[str, Any]             # From export_bulut.patterns
    examples: List[ExampleEvent]          # Historical examples


@dataclass
class RallyFamilyStoryContext:
    """Context for rally family story with stats and examples."""
    key: RallyFamilyStoryKey
    stats_row: Dict[str, Any]             # From export_bulut.rally_families
    examples: List[ExampleEvent]          # Historical examples


# ===== Context Loading =====

def load_pattern_story_context(
    key: PatternStoryKey,
    max_examples: int = 3
) -> Optional[PatternStoryContext]:
    """
    Load pattern story context from export and snapshot files.
    
    Args:
        key: Pattern identifier
        max_examples: Maximum number of examples to load
    
    Returns:
        PatternStoryContext or None if no data found
    """
    try:
        profile_dir = get_coin_profile_dir(key.symbol)
        export_path = profile_dir / "export_bulut.json"
        
        if not export_path.exists():
            logger.debug(f"export_bulut.json not found for {key.symbol}")
            return None
        
        # Load export data
        with open(export_path, 'r', encoding='utf-8') as f:
            export_data = json.load(f)
        
        # Find pattern stats row
        patterns = export_data.get("patterns", {})
        all_patterns = patterns.get("all_stats", []) or patterns.get("trustworthy", []) or []
        
        stats_row = None
        for pattern in all_patterns:
            if pattern.get("trigger") == key.trigger and pattern.get("timeframe") == key.timeframe:
                stats_row = pattern
                break
        
        if not stats_row:
            logger.debug(f"Pattern {key.trigger}/{key.timeframe} not found in export")
            return None
        
        # Load snapshot file
        snapshot_path = Path("library/patterns") / key.symbol / f"snapshots_labeled_{key.timeframe}.parquet"
        
        if not snapshot_path.exists():
            logger.debug(f"Snapshot file not found: {snapshot_path}")
            return None
        
        df = pd.read_parquet(snapshot_path)
        
        # Filter by trigger
        df_trigger = df[df['trigger'] == key.trigger].copy()
        
        if df_trigger.empty:
            logger.debug(f"No examples found for trigger {key.trigger}")
            return None
        
        # Select representative examples
        examples = _select_representative_examples(df_trigger, max_examples)
        
        return PatternStoryContext(
            key=key,
            stats_row=stats_row,
            examples=examples
        )
    
    except Exception as e:
        logger.warning(f"Error loading pattern story context: {e}")
        return None


def load_rally_family_story_context(
    key: RallyFamilyStoryKey,
    max_examples: int = 3
) -> Optional[RallyFamilyStoryContext]:
    """
    Load rally family story context from export and snapshot files.
    
    Args:
        key: Rally family identifier
        max_examples: Maximum number of examples to load
    
    Returns:
        RallyFamilyStoryContext or None if no data found
    """
    try:
        profile_dir = get_coin_profile_dir(key.symbol)
        export_path = profile_dir / "export_bulut.json"
        
        if not export_path.exists():
            logger.debug(f"export_bulut.json not found for {key.symbol}")
            return None
        
        # Load export data
        with open(export_path, 'r', encoding='utf-8') as f:
            export_data = json.load(f)
        
        # Find rally family stats row
        rally_families = export_data.get("rally_families", {})
        all_families = rally_families.get("all", []) or rally_families.get("preferred", []) or []
        
        stats_row = None
        for family in all_families:
            if (family.get("rally_class") == key.rally_class and
                family.get("family_id") == key.family_id and
                family.get("base_timeframe") == key.base_timeframe):
                stats_row = family
                break
        
        if not stats_row:
            logger.debug(f"Rally family {key.rally_class}/{key.family_id}/{key.base_timeframe} not found")
            return None
        
        # Load snapshot file
        snapshot_path = Path("library/patterns") / key.symbol / f"snapshots_multi_{key.base_timeframe}_families.parquet"
        
        if not snapshot_path.exists():
            logger.debug(f"Snapshot file not found: {snapshot_path}")
            return None
        
        df = pd.read_parquet(snapshot_path)
        
        # Filter by rally_class and family_id
        df_family = df[
            (df['rally_class'] == key.rally_class) &
            (df['family_id'] == key.family_id)
        ].copy()
        
        if df_family.empty:
            logger.debug(f"No examples found for family {key.family_id}")
            return None
        
        # Select representative examples
        examples = _select_representative_examples(df_family, max_examples)
        
        return RallyFamilyStoryContext(
            key=key,
            stats_row=stats_row,
            examples=examples
        )
    
    except Exception as e:
        logger.warning(f"Error loading rally family story context: {e}")
        return None


def _select_representative_examples(
    events_df: pd.DataFrame,
    max_examples: int = 3
) -> List[ExampleEvent]:
    """
    Select diverse representative examples (best/median/worst).
    
    Args:
        events_df: DataFrame of events
        max_examples: Maximum number to select
    
    Returns:
        List of ExampleEvent objects
    """
    if events_df.empty:
        return []
    
    sorted_df = events_df.sort_values('future_max_gain_pct', ascending=False).reset_index(drop=True)
    examples = []
    
    # Best example
    bucket_label = _get_bucket_label(sorted_df.iloc[0]['future_max_gain_pct'])
    examples.append(ExampleEvent.from_row(sorted_df.iloc[0], bucket_label))
    
    # Median example (if enough data)
    if len(sorted_df) >= 3 and max_examples >= 2:
        mid_idx = len(sorted_df) // 2
        bucket_label = _get_bucket_label(sorted_df.iloc[mid_idx]['future_max_gain_pct'])
        examples.append(ExampleEvent.from_row(sorted_df.iloc[mid_idx], bucket_label))
    
    # Worst example (if enough data)
    if len(sorted_df) >= 5 and max_examples >= 3:
        bucket_label = _get_bucket_label(sorted_df.iloc[-1]['future_max_gain_pct'])
        examples.append(ExampleEvent.from_row(sorted_df.iloc[-1], bucket_label))
    
    return examples


def _get_bucket_label(gain_pct: float) -> str:
    """Get bucket label for gain percentage."""
    gain_pct_abs = gain_pct * 100
    
    if gain_pct_abs >= 30:
        return "%30+"
    elif gain_pct_abs >= 20:
        return "%20-30"
    elif gain_pct_abs >= 10:
        return "%10-20"
    elif gain_pct_abs >= 5:
        return "%5-10"
    else:
        return "<%5"


# ===== Turkish Narrative Generation =====

def build_pattern_story_tr(ctx: PatternStoryContext) -> str:
    """
    Generate Turkish narrative for pattern story.
    
    Args:
        ctx: Pattern story context
    
    Returns:
        3-5 sentence Turkish narrative
    """
    try:
        key = ctx.key
        stats = ctx.stats_row
        examples = ctx.examples
        
        # Get trigger name in Turkish
        trigger_tr = TRIGGER_LABELS_TR.get(key.trigger, key.trigger)
        timeframe_tr = TIMEFRAME_TR.get(key.timeframe, key.timeframe)
        
        # Build narrative
        lines = []
        
        # Intro with stats
        sample_count = stats.get('sample_count', 0)
        avg_gain = stats.get('avg_future_max_gain_pct', 0) * 100
        
        lines.append(
            f"{key.symbol}, **{timeframe_tr}** grafiğindeki **{trigger_tr}** paterninde "
            f"toplam **{sample_count} örnek** görülmüş."
        )
        
        # Performance stats
        hit_10p = stats.get('hit_10p_rate', 0) * 100
        hit_20p = stats.get('hit_20p_rate', 0) * 100
        
        lines.append(
            f"Bu tetikten sonra ortalama en yüksek yükseliş **%{avg_gain:.1f}** olmuş. "
            f"Örneklerin **%{hit_10p:.0f}'ında** en az %10, "
            f"**%{hit_20p:.0f}'ında** ise %20+ rally gerçekleşmiş."
        )
        
        # Example scenarios
        if examples:
            best = examples[0]
            best_date = best.event_time.strftime('%d.%m.%Y')
            best_gain = best.future_max_gain_pct * 100
            best_bars = best.bars_to_peak
            
            lines.append(
                f"En iyi örnekte **{best_date}** tarihinde tetik sonrası "
                f"**%{best_gain:.1f}** yükseliş **{best_bars} mum** içinde tamamlanmış."
            )
            
            if len(examples) >= 2:
                med = examples[1]
                med_date = med.event_time.strftime('%d.%m.%Y')
                med_gain = med.future_max_gain_pct * 100
                
                lines.append(
                    f"Ortalama senaryoda ise **{med_date}** tarihli örnekte "
                    f"**%{med_gain:.1f}** yükseliş görülmüş."
                )
        
        # Warning if low hit rate
        if hit_10p < 50:
            lines.append(
                "⚠️ **Dikkat:** Bu tetik her zaman çalışmamış. "
                "Bazı örneklerde beklenen rally gerçekleşmemiş."
            )
        
        return "\n\n".join(lines)
    
    except Exception as e:
        logger.warning(f"Error building pattern story: {e}")
        return "Bu patern için hikâye oluşturulamadı."


def build_rally_family_story_tr(ctx: RallyFamilyStoryContext) -> str:
    """
    Generate Turkish narrative for rally family story.
    
    Args:
        ctx: Rally family story context
    
    Returns:
        3-5 sentence Turkish narrative
    """
    try:
        key = ctx.key
        stats = ctx.stats_row
        examples = ctx.examples
        
        # Get labels
        rally_label = RALLY_CLASS_TR.get(key.rally_class, key.rally_class)
        timeframe_tr = TIMEFRAME_TR.get(key.base_timeframe, key.base_timeframe)
        
        # Build narrative
        lines = []
        
        # Intro
        sample_count = stats.get('sample_count', 0)
        avg_gain = stats.get('avg_future_max_gain_pct', 0) * 100
        
        lines.append(
            f"{key.symbol}, **{timeframe_tr}** grafiğinde **{rally_label}** kategorisindeki "
            f"**Aile #{key.family_id}** için toplam **{sample_count} örnek** bulunmuş."
        )
        
        # Performance
        hit_5p = stats.get('hit_5p_rate', 0) * 100
        hit_10p = stats.get('hit_10p_rate', 0) * 100
        
        lines.append(
            f"Bu ailede ortalama en yüksek yükseliş **%{avg_gain:.1f}**. "
            f"Örneklerin **%{hit_5p:.0f}'ında** en az %5, "
            f"**%{hit_10p:.0f}'ında** ise %10+ rally görülmüş."
        )
        
        # Examples
        if examples:
            best = examples[0]
            best_date = best.event_time.strftime('%d.%m.%Y')
            best_gain = best.future_max_gain_pct * 100
            best_bars = best.bars_to_peak
            
            lines.append(
                f"En iyi örnekte **{best_date}** tarihinde "
                f"**%{best_gain:.1f}** yükseliş **{best_bars} mum** içinde gerçekleşmiş."
            )
            
            if len(examples) >= 2:
                med = examples[1]
                med_date = med.event_time.strftime('%d.%m.%Y')
                med_gain = med.future_max_gain_pct * 100
                
                lines.append(
                    f"Tipik örneklerde ise **{med_date}** tarihindeki gibi "
                    f"**%{med_gain:.1f}** civarında yükseliş yaşanmış."
                )
        
        # Trust score note
        trust_score = stats.get('trust_score', 0) * 100
        if trust_score >= 70:
            lines.append(f"✅ Bu aile **%{trust_score:.0f}** güven skoru ile öne çıkıyor.")
        
        return "\n\n".join(lines)
    
    except Exception as e:
        logger.warning(f"Error building rally family story: {e}")
        return "Bu rally ailesi için hikâye oluşturulamadı."


# ===== UI Rendering =====

def render_pattern_story_panel(
    symbol: str,
    pattern_key: Optional[PatternStoryKey],
    rally_family_key: Optional[RallyFamilyStoryKey],
    key_suffix: str = ""
) -> None:
    """
    Render pattern/rally family story panel.
    
    Shows chart (left) and narrative (right) for historical examples.
    
    Args:
        symbol: Coin symbol
        pattern_key: Pattern identifier (if viewing pattern)
        rally_family_key: Rally family identifier (if viewing rally)
        key_suffix: Optional suffix for Streamlit keys to avoid duplicates
    """
    # Lazy import to avoid circular dependency
    from tezaver.ui.chart_area import (
        render_pattern_example_chart,
        render_rally_family_example_chart
    )
    
    # Determine which type
    if pattern_key:
        ctx = load_pattern_story_context(pattern_key)
        if ctx:
            trigger_tr = TRIGGER_LABELS_TR.get(pattern_key.trigger, pattern_key.trigger)
            timeframe_tr = TIMEFRAME_TR.get(pattern_key.timeframe, pattern_key.timeframe)
            title = f"📖 Patern Hikâyesi – {symbol} / {trigger_tr} ({timeframe_tr})"
        else:
            title = f"Patern Hikâyesi – {symbol}"
    elif rally_family_key:
        ctx = load_rally_family_story_context(rally_family_key)
        if ctx:
            rally_label = RALLY_CLASS_TR.get(rally_family_key.rally_class, rally_family_key.rally_class)
            timeframe_tr = TIMEFRAME_TR.get(rally_family_key.base_timeframe, rally_family_key.base_timeframe)
            title = f"📖 Rally Ailesi Hikâyesi – {symbol} / {rally_label} Aile #{rally_family_key.family_id} ({timeframe_tr})"
        else:
            title = f"Rally Ailesi Hikâyesi – {symbol}"
    else:
        st.warning("Patern veya rally ailesi anahtarı eksik.")
        return
    
    st.markdown(f"### {title}")
    
    if ctx is None:
        st.info("Bu patern/aile için henüz detaylı hikâye oluşturulamadı. Snapshot verileri bulunamadı.")
        return
    
    # Example selector
    if len(ctx.examples) > 1:
        example_labels = []
        for i, ex in enumerate(ctx.examples):
            label_type = ["En İyi", "Ortanca", "Zayıf"][min(i, 2)]
            date_str = ex.event_time.strftime('%d.%m.%Y')
            gain_str = f"+%{ex.future_max_gain_pct*100:.1f}"
            example_labels.append(f"{label_type} Örnek – {date_str} – {gain_str}")
        
        selector_key = f"example_selector_{symbol}_{key_suffix}" if key_suffix else f"example_selector_{symbol}"
        selected_label = st.selectbox("Örnek seç:", example_labels, key=selector_key)
        selected_idx = example_labels.index(selected_label)
    else:
        selected_idx = 0
    
    selected_example = ctx.examples[selected_idx]
    
    # Layout: Chart (left) + Narrative (right)
    cols = st.columns([2, 1])
    
    with cols[0]:
        st.markdown("#### 📊 Grafik")
        
        if pattern_key:
            render_pattern_example_chart(
                symbol=symbol,
                example=selected_example,
                timeframe=pattern_key.timeframe
            )
        elif rally_family_key:
            render_rally_family_example_chart(
                symbol=symbol,
                example=selected_example,
                base_timeframe=rally_family_key.base_timeframe
            )
    
    with cols[1]:
        st.markdown("#### 📖 Hikâye")
        
        if isinstance(ctx, PatternStoryContext):
            story_text = build_pattern_story_tr(ctx)
        else:
            story_text = build_rally_family_story_tr(ctx)
        
        st.markdown(story_text)
