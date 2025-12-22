# MAC ONY Contract Report

- Generated: 2025-12-22T06:25:08+03:00
- Repo: /Users/alisaglam/TezaverMac

## 1) Key filesystem artifacts (approved/candidates/bundles)

### Latest approved manifests
```
.tezaver_matrix/approved/BTCUSDT_15m_1766258510/manifest.json
```

### Latest candidate manifests
```
.tezaver_matrix/candidates/BTCUSDT_15m_1766258510/manifest.json
```

### Matrix candidate bundle manifest (if exists)
```
out/matrix_candidates/BTCUSDT/15m/bundle_v1/manifest.json
```

## 2) Sample manifest contents (truncated)

### .tezaver_matrix/approved/BTCUSDT_15m_1766258510/manifest.json
```json
{
  "candidate_id": "BTCUSDT_15m_1766258510",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "build_ts": 1766258510,
  "builder": "mac_agent",
  "signals": [],
  "params": {
    "entry": "breakout"
  },
  "approved_at": 1766258609,
  "status": "APPROVED"
}
```

### .tezaver_matrix/candidates/BTCUSDT_15m_1766258510/manifest.json
```json
{
  "candidate_id": "BTCUSDT_15m_1766258510",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "build_ts": 1766258510,
  "builder": "mac_agent",
  "signals": [],
  "params": {
    "entry": "breakout"
  }
}
```

### out/matrix_candidates/BTCUSDT/15m/bundle_v1/manifest.json
```json
{
  "bundle_id": "BTCUSDT_15m_bundle_20251221_074154",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "bundle_version": "1.1.1",
  "build_ts": "2025-12-21T07:41:54.363377",
  "engine_min_version": "0.1.0",
  "data_fingerprint": "7566d4ccd49cc73a0ea3dd48027f7abcf5b80b283beb8762383dd9a8b6ecc3be",
  "config_signature": "2cddf44a96ec24f52c565b7330b4ea7849044304d011664e59169f7bd543771d",
  "story_count": 5,
  "sources": [
    "/Users/alisaglam/TezaverMac/library/fast15_rallies/BTCUSDT/fast15_rallies.parquet",
    "/Users/alisaglam/TezaverMac/library/patterns/BTCUSDT/snapshots_labeled_1h.parquet",
    "/Users/alisaglam/TezaverMac/coin_cells/BTCUSDT/data/history_15m.parquet",
    "/Users/alisaglam/TezaverMac/data/coin_profiles/BTCUSDT/levels_1h.json",
    "/Users/alisaglam/TezaverMac/data/coin_profiles/BTCUSDT/regime_profile.json",
    "/Users/alisaglam/TezaverMac/data/coin_profiles/BTCUSDT/shock_profile.json",
    "/Users/alisaglam/TezaverMac/data/coin_profiles/BTCUSDT/pattern_stats.json",
    "/Users/alisaglam/TezaverMac/data/coin_profiles/BTCUSDT/rally_families.json"
  ],
  "join_coverage": 0.6,
  "join_total_attempts": 5,
  "join_matched_count": 3,
  "fallback_used_count": 1,
  "trigger_resolve_rate": 0.8,
  "join_unmatched_count": 2
}
```


## 3) Code targets

### Target files
```
src/tezaver/ui/chart_area.py
src/tezaver/sniper/sniper_annotations.py
src/tezaver/rally/rally_grade_cards.py
src/tezaver/rally/rally_grading.py
src/tezaver/mac/export/story_builder.py
src/tezaver/sniper/sniper_story_builder.py
src/tezaver/ui/pattern_story_view.py
src/tezaver/rally/rally_pattern_encoder.py
src/tezaver/outcomes/rally_labeler.py
src/tezaver/rally/fast15_rally_scanner.py
src/tezaver/rally/time_labs_scanner.py
```

## 4) Keyword hits (to locate ONY schema + auto-snap)

### src/tezaver/ui/chart_area.py
```
```

### src/tezaver/sniper/sniper_annotations.py
```
```

### src/tezaver/rally/rally_grade_cards.py
```
```


## 5) Auto-extract suspected ONY/auto-snap functions (heuristic)

### Extracted defs/classes that likely matter

#### src/tezaver/ui/chart_area.py

- def **load_features_data** (near L125)
```python
def load_features_data(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """Load features parquet for RSI/MACD indicators."""
    from tezaver.snapshots.snapshot_engine import load_features
    try:
        df = load_features(symbol, timeframe)
        if 'timestamp' in df.columns:
            df['open_time'] = pd.to_datetime(df['timestamp'])
        elif 'open_time' not in df.columns:
            df['open_time'] = pd.to_datetime(df.index)
        return df
    except:
        return None


def build_coin_chart_figure(
    focus: ChartFocus,
    window_before: int,
    window_after: int,
    indicator_settings: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[go.Figure], Optional[pd.Series], Optional[Dict]]:
    """
    Verilen focus için TradingView tarzı 4 panelli grafik oluşturur.
    Panel 1: Fiyat + EMA'lar
    Panel 2: Hacim
    Panel 3: MACD
```

- def **render_sniper_studio_chart** (near L1674)
```python
def render_sniper_studio_chart(
    symbol: str,
    timeframe: str,
    event_time: pd.Timestamp,
    bars_to_peak: int,
    entry_offset: int,
    window_before: int = 50,
    window_after: int = 30,
    exit_offset: Optional[int] = None
) -> None:
    """
    Renders 4-panel chart for Sniper Studio with Entry & optional Exit markers.
    """
    try:
        # Load History
        df_history = load_history_data(symbol, timeframe)
        
        if df_history is None or df_history.empty:
            st.warning(f"{symbol} {timeframe} veri yok.")
            return

        # Load Features
        df_features = load_features_data(symbol, timeframe)

        # Merge features logic
```

#### src/tezaver/sniper/sniper_annotations.py

- class **SniperAnnotation** (near L22)
```python
class SniperAnnotation:
    """A single sniper entry annotation for a rally pattern."""
    symbol: str
    timeframe: str
    event_id: str          # rally / pattern ID
    entry_bar_offset: int  # rally penceresi içindeki bar offset'i (0 = ilk bar)
    note: str = ""
    created_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    
    # Optional fields
    exit_bar_offset: Optional[int] = None
    tags: Optional[List[str]] = None
    
    # V2 Workflow fields
    status: SniperStatus = "PENDING"
    label: SniperLabel = "UNCERTAIN"

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "SniperAnnotation":
        """Parse from dict with backward compatibility."""
        return SniperAnnotation(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            event_id=str(data["event_id"]),
            entry_bar_offset=int(data["entry_bar_offset"]),
```

- class **SniperAnnotationRepository** (near L60)
```python
class SniperAnnotationRepository:
    """
    Coin/timeframe bazlı sniper annotation depolama.
    
    Storage path: data/sniper/{symbol}/{timeframe}/sniper_annotations_v1.json
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        if base_dir is None:
            base_dir = Path("data/sniper")
        self.base_dir = base_dir

    def _file_path(self, symbol: str, timeframe: str) -> Path:
        return (
            self.base_dir
            / symbol.upper()
            / timeframe
            / "sniper_annotations_v1.json"
        )

    def load_all(self, symbol: str, timeframe: str) -> List[SniperAnnotation]:
        """Load all annotations for a symbol/timeframe."""
        path = self._file_path(symbol, timeframe)
        if not path.exists():
            return []
```

#### src/tezaver/rally/rally_grade_cards.py

- def **compute_btc_15m_silver_story_v1** (near L263)
```python
def compute_btc_15m_silver_story_v1() -> Dict[str, Any]:
    """
    Compute 'story' card for BTCUSDT 15m Silver grade 
    (future_max_gain_pct ∈ [10%, 20%)).

    Static snapshot:
      - 15m RSI / Volume / ATR / Quality / Gain / Bars to peak
      - MACD phase, rally shape, 1h/4h/1d regime distributions

    Returns:
      Dict with has_enough_samples, static_snapshot_15m, mtf_snapshot, relations
    """
    import json as _json

    df = _load_btc_15m_rally_dataset()

    if df is None or df.empty:
        return {
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "grade": "Silver",
            "has_enough_samples": False,
            "reason": "dataset_empty",
        }

```

- def **load_btc_15m_silver_story_v1** (near L430)
```python
def load_btc_15m_silver_story_v1(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load story from JSON. Returns None if file doesn't exist."""
    import json as _json
    
    if path is None:
        path = Path("data/coin_profiles/BTCUSDT/15m/grade_story_silver_v1.json")

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return _json.load(f)


# =============================================================================
# SILVER STRATEGY CARD (v1/v2-ML)
# =============================================================================

ML_ENTRY_INSIGHTS_PATH = Path("data/ai_insights/BTCUSDT/15m/entry_feature_insights_v1.json")
SL_RECOMMENDATION_PATH = Path("data/ai_insights/BTCUSDT/15m/silver_sl_recommendation_v1.json")


def _maybe_override_sl_from_recommendation(
    symbol: str,
    timeframe: str,
```

- def **_load_entry_feature_insights_v1** (near L484)
```python
def _load_entry_feature_insights_v1(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load BTC 15m entry feature insights from JSON."""
    import json as _json
    
    if path is None:
        path = ML_ENTRY_INSIGHTS_PATH

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return _json.load(f)


def _get_feature_insight(
    insights: Dict[str, Any],
    feature_name: str,
) -> Optional[Dict[str, Any]]:
    """Get single feature insight from the report."""
    feats = insights.get("features", [])
    for item in feats:
        if item.get("feature") == feature_name and item.get("available", False):
            return item
    return None

```

- def **_build_silver_ml_filters_from_insights** (near L510)
```python
def _build_silver_ml_filters_from_insights(
    insights: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build ML-based filters from entry feature insights.
    
    Features used:
      - feat_rsi_gap_1d
      - feat_atr_pct_15m
      - feat_rsi_1h
    """
    ml_filters: Dict[str, Any] = {}

    # 1) 1D RSI Gap (RSI - EMA)
    item_gap = _get_feature_insight(insights, "feat_rsi_gap_1d")
    if item_gap is not None:
        g = item_gap.get("good_stats", {})
        g_p25 = g.get("p25")
        g_p75 = g.get("p75")
        if g_p25 is not None and g_p75 is not None:
            gap_min = float(g_p25)
            gap_max = float(g_p75)
            # Good entries prefer RSI below EMA
            if gap_max > 0.0:
                gap_max = 0.0
```

- def **build_btc_15m_silver_strategy_card_v1** (near L585)
```python
def build_btc_15m_silver_strategy_card_v1() -> Dict[str, Any]:
    """
    Build a data-driven strategy card from Silver Grade story.
    Now includes ML-based filters from entry feature insights (v2).

    Source: grade_story_silver_v1.json + entry_feature_insights_v1.json
    Output: Strategy card with filters and ML filters
    """
    import math
    
    story = load_btc_15m_silver_story_v1()
    if story is None or not story.get("has_enough_samples", False):
        return {
            "profile_id": "BTC15M_SILVER_STRATEGY_V1",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "ok": False,
            "reason": "story_missing_or_not_enough_samples",
            "source_story_path": "data/coin_profiles/BTCUSDT/15m/grade_story_silver_v1.json",
        }

    static_15m = story.get("static_snapshot_15m", {})
    relations = story.get("relations", {})

    rsi_stats = static_15m.get("rsi_15m") or {}
```

- def **build_silver_strategy_card_v1** (near L847)
```python
def build_silver_strategy_card_v1(symbol: str, timeframe: str) -> Dict[str, Any]:
    """
    Build Silver Strategy Card for any timeframe.
    Uses story stats to derive entry filters and TP/SL/Horizon.
    """
    import math
    
    story = compute_silver_story_v1(symbol, timeframe)
    
    if not story.get("has_enough_samples", False):
        return {
            "profile_id": f"BTC{timeframe.upper()}_SILVER_STRATEGY_V1",
            "symbol": symbol,
            "timeframe": timeframe,
            "ok": False,
            "reason": story.get("reason", "story_not_ready"),
        }
    
    cols = _get_tf_column_names(timeframe)
    static_key = f"static_snapshot_{timeframe}"
    static = story.get(static_key, {})
    
    # Extract stats
    rsi_stats = static.get(cols["rsi"]) or {}
    vol_stats = static.get(cols["volume_rel"]) or {}
```

#### src/tezaver/sniper/sniper_story_builder.py

- def **build_sniper_entry_dataset_for_symbol_timeframe** (near L88)
```python
def build_sniper_entry_dataset_for_symbol_timeframe(
    symbol: str,
    timeframe: str = "15m",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Build sniper entry dataset from annotations + patterns + full replay.
    
    Steps:
    1. Load sniper annotations
    2. Load Silver pattern dataset
    3. Load full replay bar dataset
    4. For each annotation, find entry bar and extract features
    5. Return DataFrame + meta dict
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Timeframe (e.g., "15m").
        
    Returns:
        Tuple of (DataFrame, meta dict).
        
    Raises:
        RuntimeError: If no annotations found or no entries resolved.
    """
    symbol = symbol.upper()
```

- def **save_sniper_entry_dataset_for_symbol_timeframe** (near L328)
```python
def save_sniper_entry_dataset_for_symbol_timeframe(
    symbol: str,
    timeframe: str = "15m",
) -> Path:
    """
    Build and save sniper entry dataset to parquet + meta JSON.
    
    Args:
        symbol: Trading symbol.
        timeframe: Timeframe.
        
    Returns:
        Path to saved parquet file.
    """
    df, meta = build_sniper_entry_dataset_for_symbol_timeframe(symbol, timeframe)

    base_dir = Path("data/ai_datasets") / symbol.upper() / timeframe
    base_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = base_dir / "sniper_entries_v1.parquet"
    meta_path = base_dir / "sniper_entries_v1_meta.json"

    df.to_parquet(parquet_path, index=False)

    with meta_path.open("w", encoding="utf-8") as f:
```

- def **build_sniper_entry_datasets_for_all_silver_15m_symbols** (near L362)
```python
def build_sniper_entry_datasets_for_all_silver_15m_symbols() -> Dict[str, Path]:
    """
    Build sniper entry datasets for all Silver 15m symbols.
    
    Returns:
        Dict mapping symbol to saved parquet path.
    """
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    results: Dict[str, Path] = {}
    
    for sym in symbols:
        try:
            path = save_sniper_entry_dataset_for_symbol_timeframe(sym, "15m")
            results[sym] = path
        except RuntimeError as e:
            print(f"[SKIP] {sym}: {e}")
        except FileNotFoundError as e:
            print(f"[SKIP] {sym}: {e}")
        except Exception as e:
            print(f"[ERROR] {sym}: {e}")
    
    return results
```

## 6) Next: what we will lock as contracts

- **ApprovedRallyBundle v1**: approved_entry/approved_exit + snap_reason + snap_distance + grade + trace (engine_version/data_fingerprint/config_signature).
- **StoryPack v1**: scenes/frames that explain formation process (buildup→ignition→expansion→exhaustion) + measurable "ahenk/eğim/ruh" proxies.
- **PatternSignature v1**: deterministic encoding used by pattern library (families/stats).

