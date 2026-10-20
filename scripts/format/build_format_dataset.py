"""
Phase 3 — Build the combined format dataset.

Loads general_dataset.parquet and merges with format features from
data/format_features_cache/*.json. Outputs format_dataset.parquet
containing all general + format features in a single DataFrame.

Usage:
    python -m scripts.format.build_format_dataset
"""

import json

import pandas as pd

from scripts.config import (
    DATASET_PARQUET,
    FORMAT_FEATURES_CACHE_DIR,
    FORMAT_FEATURES_REF,
    FORMAT_DATASET_PARQUET,
    PROCESSED_DIR,
)


def load_format_features_cache() -> pd.DataFrame:
    """Load all format feature JSONs from cache into a DataFrame."""
    if not FORMAT_FEATURES_CACHE_DIR.exists():
        raise FileNotFoundError(
            f"Format features cache not found: {FORMAT_FEATURES_CACHE_DIR}\n"
            "Run 'python -m scripts.format.pipeline extract' first."
        )

    records = []
    for json_path in sorted(FORMAT_FEATURES_CACHE_DIR.glob("*.json")):
        ts = int(json_path.stem)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        data["timestamp"] = ts
        records.append(data)

    if not records:
        raise ValueError(f"No cached format features found in {FORMAT_FEATURES_CACHE_DIR}")

    df = pd.DataFrame(records)
    print(f"[format-dataset] Loaded {len(df)} cached format features")
    return df


def load_feature_names() -> list[str]:
    """Load the list of confirmed format feature names from the reference JSON."""
    if not FORMAT_FEATURES_REF.exists():
        raise FileNotFoundError(
            f"Format features reference not found: {FORMAT_FEATURES_REF}\n"
            "Run 'python -m scripts.format.pipeline confirm' first."
        )
    data = json.loads(FORMAT_FEATURES_REF.read_text(encoding="utf-8"))
    return [f["name"] for f in data.get("features", [])]


def build_format_dataset() -> pd.DataFrame:
    """
    Merge general dataset with format features.
    Returns the combined DataFrame.
    """
    if not DATASET_PARQUET.exists():
        raise FileNotFoundError(
            f"General dataset not found: {DATASET_PARQUET}\n"
            "Run the general pipeline first."
        )

    df_general = pd.read_parquet(DATASET_PARQUET)
    print(f"[format-dataset] General dataset: {len(df_general)} posts, {len(df_general.columns)} cols")

    df_format = load_format_features_cache()
    feature_names = load_feature_names()

    present = [f for f in feature_names if f in df_format.columns]
    missing = [f for f in feature_names if f not in df_format.columns]
    if missing:
        print(f"[format-dataset] WARN: {len(missing)} features missing from cache: {missing}")

    keep_cols = ["timestamp"] + present
    df_format = df_format[[c for c in keep_cols if c in df_format.columns]]

    df = df_general.merge(df_format, on="timestamp", how="left")

    matched = df[present[0]].notna().sum() if present else 0
    unmatched = len(df) - matched
    print(f"[format-dataset] Merge: {matched} posts with format features, {unmatched} without")

    return df


def save_format_dataset(df: pd.DataFrame) -> None:
    """Save the combined dataset as parquet."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(FORMAT_DATASET_PARQUET, index=False)
    size_kb = FORMAT_DATASET_PARQUET.stat().st_size / 1024
    print(f"\n[format-dataset] Saved: {FORMAT_DATASET_PARQUET}")
    print(f"  {len(df)} posts, {len(df.columns)} columns, {size_kb:.1f} KB")


if __name__ == "__main__":
    print("=" * 60)
    print("FORMAT ANALYSIS — Phase 3: Build Combined Dataset")
    print("=" * 60)

    df = build_format_dataset()
    save_format_dataset(df)

    print(f"\nDataset ready for analysis in notebooks/format/")
