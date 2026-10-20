"""
Classe base para todos os extractors de features.

Cada extractor herda de BaseExtractor e implementa `_extract_one()`.
A classe base cuida de cache, logging e iteracao sobre posts.

Uso:
    class LocalExtractor(BaseExtractor):
        NAME = "local"
        FEATURES = ["video_duration_sec", "aspect_ratio", ...]

        def _extract_one(self, post: dict) -> dict:
            return {"video_duration_sec": 30, "aspect_ratio": "vertical_9x16", ...}
"""

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from scripts.config import FEATURES_CACHE_DIR


class BaseExtractor(ABC):
    # Subclasses devem definir estas constantes
    NAME: str = ""
    FEATURES: list[str] = []

    def __init__(self, cache_dir: Path = FEATURES_CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Cache: um JSON por post (timestamp), com features de todos extractors
    # ------------------------------------------------------------------

    def _cache_path(self, timestamp: int) -> Path:
        return self.cache_dir / f"{timestamp}.json"

    def _load_cache(self, timestamp: int) -> dict:
        path = self._cache_path(timestamp)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_cache(self, timestamp: int, features: dict) -> None:
        existing = self._load_cache(timestamp)
        existing.update(features)
        with open(self._cache_path(timestamp), "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    def _has_cached(self, timestamp: int) -> bool:
        """Retorna True se TODAS as features deste extractor ja estao em cache."""
        cached = self._load_cache(timestamp)
        return all(f in cached for f in self.FEATURES)

    # ------------------------------------------------------------------
    # Interface principal
    # ------------------------------------------------------------------

    @abstractmethod
    def _extract_one(self, post: dict) -> dict:
        """
        Extrai features de um unico post.

        Args:
            post: dict com campos do DataFrame (timestamp, filepaths,
                  primary_filepath, media_type, Caption, Post Type, etc.)

        Returns:
            dict com feature_name -> value para cada feature deste extractor.
            Features nao aplicaveis ao tipo de post devem retornar None.
        """
        ...

    def extract(self, df_posts: pd.DataFrame, force: bool = False) -> pd.DataFrame:
        """
        Extrai features para todos os posts, com cache e barra de progresso.

        Args:
            df_posts: DataFrame de posts (output de group_carousels)
            force: se True, ignora cache e re-extrai tudo

        Returns:
            DataFrame com timestamp + colunas de features deste extractor
        """
        results = []
        skipped = 0

        desc = f"[{self.NAME}] Extracting {len(self.FEATURES)} features"
        for _, post in tqdm(df_posts.iterrows(), total=len(df_posts), desc=desc):
            ts = post["timestamp"]

            if not force and self._has_cached(ts):
                cached = self._load_cache(ts)
                row = {f: cached.get(f) for f in self.FEATURES}
                row["timestamp"] = ts
                results.append(row)
                skipped += 1
                continue

            try:
                features = self._extract_one(post.to_dict())
                self._save_cache(ts, features)
            except Exception as e:
                print(f"\n[{self.NAME}] ERRO no post ts={ts}: {e}")
                features = {f: None for f in self.FEATURES}

            features["timestamp"] = ts
            results.append(features)

        df_result = pd.DataFrame(results)

        extracted = len(df_posts) - skipped
        print(f"[{self.NAME}] Concluido: {extracted} extraidos, {skipped} do cache")

        return df_result
