"""
Tezaver ML Entry Classifier Experiments v1
==========================================

Simple RandomForest classifier for label_is_good_entry_v1.
Purpose: Identify which features correlate with good entries.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Dict, Any
import json

import numpy as np
import pandas as pd


DATA_PATH = Path("data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet")


def _load_btc_15m_pattern_dataset() -> pd.DataFrame:
    """Load the pattern dataset."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Pattern dataset not found at {DATA_PATH}")
    return pd.read_parquet(DATA_PATH)


def _select_features_and_label(
    df: pd.DataFrame,
    label_col: str = "label_is_good_entry_v1",
) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    """Select feature columns and label."""
    # Feature columns: feat_ prefix
    feature_cols = [c for c in df.columns if c.startswith("feat_")]
    if not feature_cols:
        raise ValueError("No feature columns starting with 'feat_' found in dataset.")

    if label_col not in df.columns:
        raise ValueError(f"Label column '{label_col}' not found in dataset.")

    X = df[feature_cols].copy()
    y = df[label_col].astype(int)

    # Handle NaN and inf values
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    return X, y, feature_cols


def run_btc_15m_entry_classifier_experiment(
    label_col: str = "label_is_good_entry_v1",
    test_size: float = 0.3,
    random_state: int = 42,
) -> Dict[str, Any]:
    """
    Run a simple RandomForest classifier experiment on BTC 15m pattern dataset.

    Purpose: Identify which features are most important for predicting good entries.
    
    Returns dict with results for programmatic use.
    """
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report, accuracy_score
    except ImportError:
        print("[ERROR] scikit-learn not installed. Run: pip install scikit-learn")
        return {"ok": False, "reason": "sklearn_not_installed"}

    df = _load_btc_15m_pattern_dataset()
    X, y, feature_cols = _select_features_and_label(df, label_col=label_col)

    positive_count = int(y.sum())
    total_count = int(y.shape[0])

    print(f"[INFO] Dataset size: {total_count} rows")
    print(f"[INFO] Positive count for '{label_col}': {positive_count}")

    if positive_count < 2:
        print("[WARN] Too few positive samples for a meaningful classifier.")
        return {
            "ok": False,
            "reason": "too_few_positive_samples",
            "positive_count": positive_count,
            "total_count": total_count,
        }

    # Train/test split (stratified)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    clf = RandomForestClassifier(
        n_estimators=200,
        random_state=random_state,
        class_weight="balanced",
        max_depth=None,
        min_samples_leaf=1,
    )

    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    
    print("\n=== Classification Report ===")
    print(classification_report(y_test, y_pred, digits=3))

    # Feature importances
    importances = clf.feature_importances_
    fi = sorted(zip(feature_cols, importances), key=lambda t: t[1], reverse=True)

    print("\n=== Top 20 Feature Importances ===")
    for name, score in fi[:20]:
        print(f"{name:35s}  {score:.4f}")

    # Build result dict
    top_features = [{"feature": name, "importance": float(score)} for name, score in fi[:20]]
    
    result = {
        "ok": True,
        "label_col": label_col,
        "total_count": total_count,
        "positive_count": positive_count,
        "test_accuracy": float(accuracy),
        "top_features": top_features,
    }

    return result


def save_feature_importance_report(
    output_path: Path = None,
    label_col: str = "label_is_good_entry_v1",
) -> Path:
    """
    Run classifier and save feature importance report to JSON.
    """
    if output_path is None:
        output_path = Path("data/ai_datasets/BTCUSDT/15m/feature_importance_v1.json")
    
    result = run_btc_15m_entry_classifier_experiment(label_col=label_col)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n[INFO] Feature importance report saved to: {output_path}")
    return output_path


if __name__ == "__main__":
    # Run default experiment
    print("=" * 60)
    print("BTC 15m Entry Classifier Experiment v1")
    print("=" * 60)
    
    result = run_btc_15m_entry_classifier_experiment()
    
    if result.get("ok"):
        print(f"\n[SUMMARY] Accuracy: {result['test_accuracy']:.3f}")
        print(f"[SUMMARY] Top 3 features:")
        for feat in result["top_features"][:3]:
            print(f"  - {feat['feature']}: {feat['importance']:.4f}")
