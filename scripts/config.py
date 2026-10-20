"""
Configuração central do projeto Genna Content Machine.

Todos os caminhos, constantes e variáveis de ambiente são definidos aqui.
Qualquer script do projeto deve importar deste módulo.

Uso:
    from scripts.config import POST_STORAGE_DIR, METRICS_CSV, FEATURES_REF
"""

from pathlib import Path
from dotenv import load_dotenv
import os

# ---------------------------------------------------------------------------
# Raiz do projeto (pasta "máquina de conteúdo")
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Carregar .env (se existir)
# ---------------------------------------------------------------------------
_env_path = PROJECT_ROOT / ".env"
load_dotenv(_env_path)

# ---------------------------------------------------------------------------
# API Keys (só usadas nos Blocos D+)
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ---------------------------------------------------------------------------
# Diretórios principais
# ---------------------------------------------------------------------------
POST_STORAGE_DIR = PROJECT_ROOT / "Post Storage"
METRICS_DIR = PROJECT_ROOT / "Metrics"
DATA_DIR = PROJECT_ROOT / "data"
FEATURES_CACHE_DIR = DATA_DIR / "general_features_cache"
PROCESSED_DIR = DATA_DIR / "processed"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"

# ---------------------------------------------------------------------------
# Arquivos específicos
# ---------------------------------------------------------------------------
METRICS_CSV = METRICS_DIR / "genna_export.csv"
FEATURES_REF = PROJECT_ROOT / "general_features_reference.json"

# Checkpoints de dados (gerados pelo pipeline)
POSTS_BASE_PARQUET = PROCESSED_DIR / "posts_base.parquet"
DATASET_PARQUET = PROCESSED_DIR / "general_dataset.parquet"

# ---------------------------------------------------------------------------
# Format Analysis Pipeline
# ---------------------------------------------------------------------------
FORMAT_DEFINITION_MD = PROJECT_ROOT / "format_definition.md"
FORMAT_FEATURES_REVIEW_MD = PROJECT_ROOT / "format_features_review.md"
FORMAT_FEATURES_REF = PROJECT_ROOT / "format_features_reference.json"
FORMAT_FEATURES_CACHE_DIR = DATA_DIR / "format_features_cache"
FORMAT_DATASET_PARQUET = PROCESSED_DIR / "format_dataset.parquet"

# ---------------------------------------------------------------------------
# Padrão de nome dos arquivos de mídia
# Formato: {username}_{unix_timestamp}_{post_id}_{user_id}.{ext}
# Exemplo: profile_1774402267_<POST_ID>_<USER_ID>.mp4
# ---------------------------------------------------------------------------
FILENAME_PATTERN = r"^(?P<username>[^_]+(?:\.[^_]+)*)_(?P<timestamp>\d+)_(?P<post_id>\d+)_(?P<user_id>\d+)\.(?P<extension>\w+)$"

# ---------------------------------------------------------------------------
# Perfil alvo
# ---------------------------------------------------------------------------
INSTAGRAM_PROFILE = os.getenv("INSTAGRAM_PROFILE", "your_profile")

# ---------------------------------------------------------------------------
# Extensões de mídia reconhecidas
# ---------------------------------------------------------------------------
VIDEO_EXTENSIONS = {".mp4"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".webp", ".png"}
ALL_MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS
