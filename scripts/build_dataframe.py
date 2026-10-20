"""
Fase 3 — Montagem e limpeza do DataFrame Final.

Etapa E1: junta posts_base.parquet (Fase 1) com features extraidas (Fase 2).
Etapa E2: validacao, limpeza de tipos, padronizacao de colunas.

Uso:
    python -m scripts.build_dataframe
"""

import json
import re
import pandas as pd
import numpy as np

from scripts.config import (
    FEATURES_CACHE_DIR,
    POSTS_BASE_PARQUET,
    DATASET_PARQUET,
    PROCESSED_DIR,
)

FEATURE_NAMES = [
    "video_duration_sec", "carousel_slide_count", "aspect_ratio",
    "cuts_per_minute", "text_overlay_presence", "dominant_color_palette",
    "lighting_type", "camera_movement_style", "hook_visual_technique",
    "visual_format_type", "transition_style", "face_presence",
    "image_quality_score", "zoom_effect_used", "thumbnail_composition",
    "audio_hook_type", "text_hook_on_screen", "curiosity_gap_level",
    "pattern_interrupt_type", "opening_emotion_conveyed",
    "first_frame_scroll_stop_score", "hook_delivery_speed",
    "direct_viewer_address", "bait_and_reveal_structure",
    "opening_subject_framing",
    "people_count", "primary_person_age_range", "eye_contact_with_camera",
    "dominant_facial_expression", "body_language_energy",
    "talent_role_in_content", "appearance_style",
    "creator_camera_presence_score",
    "audio_source_type", "speech_language", "speech_pacing_wpm",
    "voice_tone_energy", "background_music_mood", "music_beat_sync",
    "voice_to_music_balance", "audio_caption_availability",
    "content_category", "narrative_structure", "value_proposition_type",
    "cta_type", "educational_density", "controversy_level",
    "content_originality", "emotional_arc", "target_audience_intent",
    "information_pacing",
    "skin_exposure_level", "hook_sensuality_level",
    "suggestive_body_language", "innuendo_in_text",
    "overall_provocation_score",
    "caption_length_chars", "hashtag_count", "caption_first_line_hook",
    "caption_tone", "emoji_density", "account_mentions_count",
]


def load_features_cache() -> pd.DataFrame:
    """
    Le todos os JSONs de data/features_cache/ e retorna um DataFrame
    com timestamp + 62 colunas de features.
    """
    records = []

    for json_path in sorted(FEATURES_CACHE_DIR.glob("*.json")):
        ts = int(json_path.stem)
        with open(json_path, "r", encoding="utf-8") as f:
            features = json.load(f)
        features["timestamp"] = ts
        records.append(features)

    df = pd.DataFrame(records)

    present = [f for f in FEATURE_NAMES if f in df.columns]
    missing = [f for f in FEATURE_NAMES if f not in df.columns]

    if missing:
        print(f"[WARN] {len(missing)} features ausentes no cache: {missing}")

    df = df[["timestamp"] + present]

    print(f"Features cache carregado: {len(df)} timestamps, {len(present)} features")
    return df


def build_dataset() -> pd.DataFrame:
    """
    Junta posts_base (metricas + metadados) com features extraidas.
    Retorna o DataFrame unificado.
    """
    if not POSTS_BASE_PARQUET.exists():
        raise FileNotFoundError(
            f"{POSTS_BASE_PARQUET} nao encontrado. Rode 'python -m scripts.prepare_data' primeiro."
        )

    df_posts = pd.read_parquet(POSTS_BASE_PARQUET)
    print(f"Posts base: {len(df_posts)} posts, {len(df_posts.columns)} colunas")

    df_features = load_features_cache()

    df = df_posts.merge(df_features, on="timestamp", how="left")

    matched = df[FEATURE_NAMES[0]].notna().sum() if FEATURE_NAMES[0] in df.columns else 0
    unmatched = len(df) - matched
    print(f"\nMerge resultado:")
    print(f"  Posts com features: {matched}")
    print(f"  Posts sem features: {unmatched}")

    id_cols = ["timestamp", "timestamp_csv", "Date", "Post Type", "media_type",
               "file_count", "primary_filepath", "filepaths"]
    metric_cols = ["Reach", "Views", "Likes", "Comments", "Saved", "Shares",
                   "Interactions", "Following", "Likes Rate", "Shares Rate",
                   "Views Rate", "Interactions Rate", "Saved Rate", "Comments Rate",
                   "Reels Avg Watch Time", "Reels Video View Total Time",
                   "Profile Activity", "Profile Visits", "Replies"]
    text_cols = ["Caption"]
    feature_cols = [f for f in FEATURE_NAMES if f in df.columns]

    col_order = (
        [c for c in id_cols if c in df.columns]
        + [c for c in metric_cols if c in df.columns]
        + [c for c in text_cols if c in df.columns]
        + feature_cols
    )
    extra = [c for c in df.columns if c not in col_order]
    col_order += extra

    df = df[col_order]

    return df


# =========================================================================
# Etapa E2 — Validacao e limpeza
# =========================================================================

_COLUMN_RENAME = {
    "Post Type": "post_type",
    "Date": "date_raw",
    "Reach": "reach",
    "Views": "views",
    "Likes": "likes",
    "Comments": "comments",
    "Saved": "saved",
    "Shares": "shares",
    "Interactions": "interactions",
    "Following": "following",
    "Likes Rate": "likes_rate",
    "Shares Rate": "shares_rate",
    "Views Rate": "views_rate",
    "Interactions Rate": "interactions_rate",
    "Saved Rate": "saved_rate",
    "Comments Rate": "comments_rate",
    "Reels Avg Watch Time": "avg_watch_time_ms",
    "Reels Video View Total Time": "total_view_time_ms",
    "Profile Activity": "profile_activity",
    "Profile Visits": "profile_visits",
    "Replies": "replies",
    "Caption": "caption",
}

REEL_ONLY_FEATURES = {
    "video_duration_sec", "cuts_per_minute", "camera_movement_style",
    "hook_visual_technique", "visual_format_type", "transition_style",
    "zoom_effect_used", "audio_hook_type", "hook_delivery_speed",
    "talent_role_in_content", "creator_camera_presence_score",
    "audio_source_type", "speech_language", "speech_pacing_wpm",
    "voice_tone_energy", "background_music_mood", "music_beat_sync",
    "voice_to_music_balance", "audio_caption_availability",
    "narrative_structure", "emotional_arc", "information_pacing",
    "bait_and_reveal_structure",
}

CAROUSEL_ONLY_FEATURES = {"carousel_slide_count"}

REEL_ONLY_METRICS = {"avg_watch_time_ms", "total_view_time_ms"}
CAROUSEL_ONLY_METRICS = {"following", "profile_activity", "profile_visits"}


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Etapa E2: validacao e limpeza do DataFrame.

    1. Renomeia colunas para snake_case
    2. Cria coluna date (datetime) e avg_watch_time_sec
    3. Remove colunas 100% null
    4. Valida ranges de features numericas
    5. Classifica nulls (esperados vs inesperados)
    """
    print("\n--- E2: Validacao e Limpeza ---")
    changes = []

    # 1. Renomear colunas
    df = df.rename(columns=_COLUMN_RENAME)
    changes.append(f"Colunas renomeadas para snake_case ({len(_COLUMN_RENAME)} cols)")

    # 2. Criar date (datetime) a partir de date_raw
    def _parse_date(s):
        clean = re.sub(r"\s*\(.*\)\s*$", "", s).replace("GMT", "").strip()
        return pd.to_datetime(clean, format="%a %b %d %Y %H:%M:%S %z", utc=True)

    df["date"] = df["date_raw"].apply(_parse_date)
    df["date_br"] = df["date"].dt.tz_convert("America/Sao_Paulo")
    changes.append("Coluna 'date' (datetime UTC) e 'date_br' (BRT) criadas")

    # 3. Converter avg_watch_time de ms para seconds
    if "avg_watch_time_ms" in df.columns:
        df["avg_watch_time_sec"] = (df["avg_watch_time_ms"] / 1000).round(1)
        changes.append("avg_watch_time_sec criada (ms -> s)")

    # 4. Remover colunas 100% null
    all_null = [c for c in df.columns if df[c].isnull().all()]
    if all_null:
        df = df.drop(columns=all_null)
        changes.append(f"Colunas 100%% null removidas: {all_null}")

    # 5. Validar ranges de features numericas
    range_checks = {
        "image_quality_score": (1, 10),
        "curiosity_gap_level": (0, 5),
        "first_frame_scroll_stop_score": (1, 10),
        "creator_camera_presence_score": (0, 10),
        "educational_density": (0, 5),
        "controversy_level": (0, 5),
        "overall_provocation_score": (0, 10),
        "speech_pacing_wpm": (0, 400),
        "video_duration_sec": (1, 5400),
        "cuts_per_minute": (0, 100),
        "caption_length_chars": (0, 2200),
        "hashtag_count": (0, 30),
        "account_mentions_count": (0, 50),
        "carousel_slide_count": (2, 20),
    }
    violations = []
    for feat, (lo, hi) in range_checks.items():
        if feat not in df.columns:
            continue
        vals = df[feat].dropna()
        oob = vals[(vals < lo) | (vals > hi)]
        if len(oob) > 0:
            violations.append(f"  {feat}: {len(oob)} fora de [{lo}, {hi}] "
                              f"(vals: {sorted(oob.unique().tolist())})")
    if violations:
        changes.append("Valores fora de range encontrados:")
        changes.extend(violations)
    else:
        changes.append("Ranges de features numericas OK")

    # 6. Classificar nulls
    total_nulls = 0
    expected_nulls = 0
    unexpected_nulls = 0

    feature_cols = [f for f in FEATURE_NAMES if f in df.columns]
    for feat in feature_cols:
        null_mask = df[feat].isnull()
        n_null = null_mask.sum()
        if n_null == 0:
            continue
        total_nulls += n_null

        is_reel = df["post_type"] == "REEL"
        is_carousel = df["post_type"] == "FEED_CAROUSEL"

        if feat in REEL_ONLY_FEATURES:
            exp = (null_mask & is_carousel).sum()
        elif feat in CAROUSEL_ONLY_FEATURES:
            exp = (null_mask & is_reel).sum()
        else:
            exp = 0

        expected_nulls += exp
        unexpected_nulls += (n_null - exp)

    changes.append(f"Nulls em features: {total_nulls} total "
                   f"({expected_nulls} esperados por tipo de post, "
                   f"{unexpected_nulls} inesperados/extracao falhou)")

    # 7. Ordenar colunas
    id_cols = ["timestamp", "timestamp_csv", "date", "date_br", "date_raw",
               "post_type", "media_type", "file_count", "primary_filepath", "filepaths"]
    metric_cols = ["reach", "views", "likes", "comments", "saved", "shares",
                   "interactions", "likes_rate", "shares_rate", "views_rate",
                   "interactions_rate", "saved_rate", "comments_rate",
                   "avg_watch_time_ms", "avg_watch_time_sec", "total_view_time_ms",
                   "profile_activity", "profile_visits", "following"]
    text_cols = ["caption"]

    col_order = (
        [c for c in id_cols if c in df.columns]
        + [c for c in metric_cols if c in df.columns]
        + [c for c in text_cols if c in df.columns]
        + [f for f in feature_cols if f in df.columns]
    )
    extra = [c for c in df.columns if c not in col_order]
    col_order += extra
    df = df[col_order]

    df = df.sort_values("timestamp").reset_index(drop=True)

    for c in changes:
        print(f"  {c}")

    return df


# =========================================================================
# Salvar e resumir
# =========================================================================

def save_dataset(df: pd.DataFrame) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DATASET_PARQUET, index=False)
    size_kb = DATASET_PARQUET.stat().st_size / 1024
    print(f"\nSalvo: {DATASET_PARQUET}")
    print(f"  {len(df)} posts, {len(df.columns)} colunas, {size_kb:.1f} KB")


def print_summary(df: pd.DataFrame) -> None:
    print(f"\n{'='*60}")
    print(f"RESUMO DO DATASET FINAL")
    print(f"{'='*60}")
    print(f"Dimensoes: {df.shape[0]} posts x {df.shape[1]} colunas")

    date_col = "date_br" if "date_br" in df.columns else "date_raw"
    if date_col == "date_br":
        print(f"Periodo: {df[date_col].min().strftime('%Y-%m-%d')} -> "
              f"{df[date_col].max().strftime('%Y-%m-%d')}")
    else:
        print(f"Periodo: {df[date_col].iloc[0][:20]}  ->  {df[date_col].iloc[-1][:20]}")

    pt_col = "post_type" if "post_type" in df.columns else "Post Type"
    print(f"Post Types: {df[pt_col].value_counts().to_dict()}")
    print(f"Media Types: {df['media_type'].value_counts().to_dict()}")

    feature_cols = [f for f in FEATURE_NAMES if f in df.columns]
    null_pct = df[feature_cols].isnull().mean() * 100
    high_null = null_pct[null_pct > 50]
    if len(high_null) > 0:
        print(f"\nFeatures com >50% null ({len(high_null)}):")
        for feat, pct in high_null.sort_values(ascending=False).items():
            print(f"  {feat}: {pct:.0f}% null")

    print(f"\nNulls totais por tipo de coluna:")
    metric_in_df = [c for c in ["reach", "views", "likes", "Reach", "Views", "Likes"] if c in df.columns]
    if metric_in_df:
        print(f"  Metricas: {df[metric_in_df].isnull().sum().sum()} nulls")
    print(f"  Features: {df[feature_cols].isnull().sum().sum()} nulls "
          f"({df[feature_cols].isnull().sum().sum() / (len(df) * len(feature_cols)) * 100:.1f}%)")

    numeric_features = df[feature_cols].select_dtypes(include=[np.number]).columns.tolist()
    if numeric_features:
        print(f"\nFeatures numericas ({len(numeric_features)}):")
        print(df[numeric_features].describe().round(1).to_string())

    print(f"\nColunas ({len(df.columns)}):")
    for i, c in enumerate(df.columns):
        dtype = df[c].dtype
        nn = df[c].notna().sum()
        print(f"  {i+1:2d}. {c:45s} {str(dtype):12s} ({nn}/{len(df)} non-null)")

    csv_path = PROCESSED_DIR / "general_dataset.csv"
    export = df.drop(columns=["filepaths"], errors="ignore")
    for col in export.select_dtypes(include=["datetimetz"]).columns:
        export[col] = export[col].astype(str)
    export.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\nCSV tambem salvo: {csv_path} ({csv_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    print("=" * 60)
    print("ETAPA E1 — Montagem do DataFrame")
    print("=" * 60)
    df = build_dataset()

    print("\n" + "=" * 60)
    print("ETAPA E2 — Validacao e Limpeza")
    print("=" * 60)
    df = clean_dataset(df)

    save_dataset(df)
    print_summary(df)
