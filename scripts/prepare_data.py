"""
Fase 1 — Preparação de Dados.

Funções para parsear arquivos de mídia, CSV de métricas,
cruzar via timestamp e agrupar carrosséis.

Uso:
    from scripts.prepare_data import parse_filenames, parse_metrics, join_files_metrics
"""

import re
import numpy as np
import pandas as pd

from scripts.config import (
    POST_STORAGE_DIR,
    METRICS_CSV,
    FILENAME_PATTERN,
    ALL_MEDIA_EXTENSIONS,
    INSTAGRAM_PROFILE,
)

# Tolerancia maxima (em segundos) para fuzzy matching de timestamps.
# O CSV e o nome do arquivo podem discordar em ate ~1-2 minutos.
TIMESTAMP_TOLERANCE = 120

# ---------------------------------------------------------------------------
# Etapa B1 — Parsear nomes dos arquivos
# ---------------------------------------------------------------------------

_filename_regex = re.compile(FILENAME_PATTERN)


def parse_filenames() -> pd.DataFrame:
    """
    Lê todos os arquivos de mídia em Post Storage e extrai metadados do nome.

    Retorna DataFrame com colunas:
        filename, username, timestamp, post_id, user_id, extension, filepath
    """
    records = []

    for filepath in POST_STORAGE_DIR.iterdir():
        if filepath.suffix.lower() not in ALL_MEDIA_EXTENSIONS:
            continue

        match = _filename_regex.match(filepath.name)
        if match:
            data = match.groupdict()
            data["timestamp"] = int(data["timestamp"])
            data["filename"] = filepath.name
            data["filepath"] = str(filepath)
            records.append(data)
        else:
            print(f"[WARN] Nome não reconhecido: {filepath.name}")

    df = pd.DataFrame(records)

    if df.empty:
        return df

    col_order = ["filename", "username", "timestamp", "post_id", "user_id", "extension", "filepath"]
    df = df[col_order].sort_values("timestamp").reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# Etapa B2 — Parsear CSV de métricas
# ---------------------------------------------------------------------------

def _parse_instagram_date(date_str: str) -> int:
    """
    Converte 'Wed Mar 25 2026 11:51:12 GMT-0300 (Horário Padrão de Brasília)'
    para Unix timestamp (int).

    Remove o texto entre parênteses e parseia o resto com o offset UTC.
    """
    clean = re.sub(r"\s*\(.*\)\s*$", "", date_str)
    # "Wed Mar 25 2026 11:51:12 GMT-0300"  →  separar o offset
    clean = clean.replace("GMT", "").strip()
    # "Wed Mar 25 2026 11:51:12 -0300"
    dt = pd.to_datetime(clean, format="%a %b %d %Y %H:%M:%S %z")
    return int(dt.timestamp())


def parse_metrics() -> pd.DataFrame:
    """
    Lê o CSV de métricas e adiciona coluna 'timestamp' (Unix) parseada da coluna Date.

    Retorna DataFrame com 22 colunas originais + coluna 'timestamp'.
    """
    df = pd.read_csv(METRICS_CSV)

    df["timestamp"] = df["Date"].apply(_parse_instagram_date)

    df = df.sort_values("timestamp").reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# Etapa B3 — Join arquivos + métricas
# ---------------------------------------------------------------------------

def _fuzzy_match_timestamp(
    csv_ts: int,
    file_timestamps: np.ndarray,
    tolerance: int = TIMESTAMP_TOLERANCE,
) -> int | None:
    """
    Encontra o timestamp de arquivo mais proximo do timestamp do CSV,
    dentro da tolerancia. Retorna None se nenhum estiver perto o suficiente.
    """
    diffs = np.abs(file_timestamps - csv_ts)
    min_idx = diffs.argmin()
    if diffs[min_idx] <= tolerance:
        return int(file_timestamps[min_idx])
    return None


def join_files_metrics(
    df_files: pd.DataFrame,
    df_metrics: pd.DataFrame,
    profile: str = INSTAGRAM_PROFILE,
    tolerance: int = TIMESTAMP_TOLERANCE,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Cruza arquivos de midia com metricas via timestamp (com fuzzy matching).

    Estrategia em 2 passos:
      1. Match exato por timestamp
      2. Para os que sobraram, fuzzy match dentro da tolerancia (+-120s)

    Posts no CSV sem arquivo correspondente sao mantidos separados
    (normal no dia-a-dia: post publicado mas ainda nao baixado).

    Retorna tupla com 3 DataFrames:
        - df_joined: registros com match (arquivos + metricas)
        - df_metrics_no_file: linhas do CSV sem arquivo (ainda nao baixado)
        - df_files_no_metric: arquivos sem metrica (fora do periodo do CSV)
    """
    df_profile = df_files[df_files["username"] == profile].copy()
    file_ts_array = df_profile["timestamp"].unique()

    # Passo 1: match exato
    exact_match = set(df_metrics["timestamp"].unique()) & set(file_ts_array)

    # Passo 2: fuzzy match para os que sobraram
    fuzzy_map = {}  # csv_ts -> file_ts
    unmatched_csv_ts = set(df_metrics["timestamp"].unique()) - exact_match

    for csv_ts in unmatched_csv_ts:
        file_ts = _fuzzy_match_timestamp(csv_ts, file_ts_array, tolerance)
        if file_ts is not None:
            fuzzy_map[csv_ts] = file_ts

    # Aplicar fuzzy: criar coluna de join nos metrics
    df_metrics = df_metrics.copy()
    df_metrics["_join_ts"] = df_metrics["timestamp"].map(
        lambda ts: fuzzy_map.get(ts, ts)
    )

    # Join usando _join_ts (metrics) com timestamp (files)
    df_joined = df_profile.merge(
        df_metrics, left_on="timestamp", right_on="_join_ts", how="inner",
        suffixes=("_file", "_csv"),
    )
    df_joined.drop(columns=["_join_ts"], inplace=True)

    # Renomear: manter timestamp do arquivo como coluna principal
    if "timestamp_file" in df_joined.columns:
        df_joined["timestamp"] = df_joined["timestamp_file"]
        df_joined["timestamp_csv"] = df_joined["timestamp_csv"]
        df_joined.drop(columns=["timestamp_file"], inplace=True)

    # Identificar nao-matcheados
    matched_csv_ts = exact_match | set(fuzzy_map.keys())
    all_matched_file_ts = exact_match | set(fuzzy_map.values())

    df_metrics_no_file = df_metrics[~df_metrics["timestamp"].isin(matched_csv_ts)].copy()
    df_metrics_no_file.drop(columns=["_join_ts"], inplace=True)

    df_files_no_metric = df_profile[~df_profile["timestamp"].isin(all_matched_file_ts)].copy()

    # Relatorio
    print(f"\n--- Resultado do Join ---")
    print(f"Perfil '{profile}': {len(df_profile)} arquivos ({df_profile['timestamp'].nunique()} timestamps)")
    print(f"CSV: {len(df_metrics)} registros ({df_metrics['timestamp'].nunique()} timestamps)")
    print(f"Match exato: {len(exact_match)} timestamps")
    print(f"Match fuzzy (+-{tolerance}s): {len(fuzzy_map)} timestamps")
    if fuzzy_map:
        for csv_ts, file_ts in fuzzy_map.items():
            print(f"  csv={csv_ts} -> file={file_ts} (diff={file_ts - csv_ts:+d}s)")
    total_matched = len(exact_match) + len(fuzzy_map)
    print(f"Total matched: {total_matched}/{df_metrics['timestamp'].nunique()} timestamps")
    print(f"CSV sem arquivo: {len(df_metrics_no_file)} (posts ainda nao baixados)")
    print(f"Arquivos sem CSV: {df_files_no_metric['timestamp'].nunique()} timestamps (fora do periodo)")

    return df_joined, df_metrics_no_file, df_files_no_metric


# ---------------------------------------------------------------------------
# Etapa B5 — Agrupar carrosséis
# ---------------------------------------------------------------------------

# Colunas de metrica que vem do CSV (nao devem ser agregadas, apenas mantidas)
_METRIC_COLS = [
    "Caption", "Post Type", "Date", "Reach", "Likes Rate", "Shares Rate",
    "Reels Avg Watch Time", "Views Rate", "Interactions Rate", "Views",
    "Likes", "Comments", "Saved", "Shares", "Interactions", "Following",
    "Reels Video View Total Time", "Profile Activity", "Profile Visits",
    "Replies", "Saved Rate", "Comments Rate",
]


def group_carousels(df_joined: pd.DataFrame) -> pd.DataFrame:
    """
    Consolida multiplos arquivos por timestamp em um unico registro por post.

    Para cada post gera:
      - file_count: numero de arquivos (1 para Reels, N para carrosseis)
      - filepaths: lista de caminhos dos arquivos
      - media_type: 'video' se tem .mp4, 'image' se so imagens, 'mixed' se ambos
      - primary_filepath: caminho do arquivo principal (o .mp4, ou o primeiro .jpg)

    Colunas de metricas sao mantidas (uma copia por post, ja que sao iguais
    para todos os arquivos do mesmo timestamp).
    """
    grouped = []

    for ts, group in df_joined.groupby("timestamp"):
        row = {}
        row["timestamp"] = ts

        filepaths = group["filepath"].tolist()
        extensions = set(group["extension"].str.lower())

        row["file_count"] = len(group)
        row["filepaths"] = filepaths

        if "mp4" in extensions:
            row["media_type"] = "video"
            mp4_rows = group[group["extension"].str.lower() == "mp4"]
            row["primary_filepath"] = mp4_rows["filepath"].iloc[0]
        else:
            row["media_type"] = "image"
            row["primary_filepath"] = filepaths[0]

        # Manter colunas de metricas (iguais em todas as linhas do grupo)
        first = group.iloc[0]
        for col in _METRIC_COLS:
            if col in first.index:
                row[col] = first[col]

        if "timestamp_csv" in first.index:
            row["timestamp_csv"] = first["timestamp_csv"]

        grouped.append(row)

    df_posts = pd.DataFrame(grouped).sort_values("timestamp").reset_index(drop=True)

    n_video = (df_posts["media_type"] == "video").sum()
    n_image = (df_posts["media_type"] == "image").sum()
    print(f"\n--- Agrupamento de Carrosseis ---")
    print(f"Posts unicos: {len(df_posts)}")
    print(f"  Video (Reels): {n_video}")
    print(f"  Image (Carrosseis): {n_image}")
    print(f"  Slides por carrossel: min={df_posts[df_posts['media_type']=='image']['file_count'].min()}, "
          f"max={df_posts[df_posts['media_type']=='image']['file_count'].max()}")

    return df_posts


# ---------------------------------------------------------------------------
# Etapa B6 — Salvar checkpoint da Fase 1
# ---------------------------------------------------------------------------

def save_posts_base(df_posts: pd.DataFrame) -> None:
    """
    Salva df_posts como parquet em data/processed/posts_base.parquet.
    Cria o diretorio se nao existir.
    """
    from scripts.config import POSTS_BASE_PARQUET, PROCESSED_DIR

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df_posts.to_parquet(POSTS_BASE_PARQUET, index=False)
    size_kb = POSTS_BASE_PARQUET.stat().st_size / 1024
    print(f"\nSalvo: {POSTS_BASE_PARQUET}")
    print(f"  {len(df_posts)} posts, {len(df_posts.columns)} colunas, {size_kb:.1f} KB")


def load_posts_base() -> pd.DataFrame:
    """Carrega o checkpoint da Fase 1 (posts_base.parquet)."""
    from scripts.config import POSTS_BASE_PARQUET

    if not POSTS_BASE_PARQUET.exists():
        raise FileNotFoundError(
            f"{POSTS_BASE_PARQUET} nao encontrado. Rode a Fase 1 primeiro."
        )
    return pd.read_parquet(POSTS_BASE_PARQUET)


# ---------------------------------------------------------------------------
# Execução direta para teste
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("ETAPA B1 — Parse de arquivos")
    print("=" * 60)
    df_files = parse_filenames()
    print(f"Arquivos parseados: {len(df_files)}")
    print(f"Usernames: {df_files['username'].unique().tolist()}")
    print(f"Timestamps únicos: {df_files['timestamp'].nunique()}")
    print(f"Extensões: {df_files['extension'].unique().tolist()}")

    print("\n" + "=" * 60)
    print("ETAPA B2 -- Parse de metricas")
    print("=" * 60)
    df_metrics = parse_metrics()
    print(f"Registros no CSV: {len(df_metrics)}")
    print(f"Post Types: {df_metrics['Post Type'].unique().tolist()}")
    print(f"Timestamps unicos: {df_metrics['timestamp'].nunique()}")
    print(f"Periodo: {df_metrics['Date'].iloc[0][:20]}  ->  {df_metrics['Date'].iloc[-1][:20]}")

    print("\n" + "=" * 60)
    print("ETAPA B3 -- Join arquivos + metricas")
    print("=" * 60)
    df_joined, df_no_file, df_no_metric = join_files_metrics(df_files, df_metrics)

    if len(df_no_file) > 0:
        print(f"\nCSV sem arquivo ({len(df_no_file)} registros):")
        for _, row in df_no_file.iterrows():
            print(f"  ts={row['timestamp']}  date={row['Date'][:30]}  type={row['Post Type']}")

    if len(df_no_metric) > 0:
        print(f"\nArquivos sem CSV: {len(df_no_metric)} timestamps (posts anteriores ao periodo do CSV)")

    print("\n" + "=" * 60)
    print("ETAPA B5 -- Agrupar carrosseis")
    print("=" * 60)
    df_posts = group_carousels(df_joined)
    print(f"\nColunas finais ({len(df_posts.columns)}):")
    print(f"  {list(df_posts.columns)}")
    print(f"\nAmostra (3 primeiros posts):")
    for _, p in df_posts.head(3).iterrows():
        print(f"  ts={p['timestamp']}  type={p['Post Type']:15}  media={p['media_type']:5}  files={p['file_count']}")

    print("\n" + "=" * 60)
    print("ETAPA B6 -- Salvar checkpoint")
    print("=" * 60)
    save_posts_base(df_posts)

    # Verificacao: recarregar e comparar
    df_reload = load_posts_base()
    assert len(df_reload) == len(df_posts), "Tamanho diverge!"
    assert list(df_reload.columns) == list(df_posts.columns), "Colunas divergem!"
    print("Verificacao: reload OK (tamanho e colunas batem)")
