"""
Fase 2 — Orquestrador de extracoes de features.

Roda os extractors na ordem correta (gratis primeiro, pagos depois)
e salva resultados no cache.
"""

import time
import pandas as pd

from scripts.prepare_data import load_posts_base
from scripts.extractors.local import LocalExtractor
from scripts.extractors.whisper import WhisperExtractor
from scripts.extractors.mixed import MixedExtractor
from scripts.extractors.metadata import MetadataExtractor
from scripts.extractors.gemini import GeminiExtractor
from scripts.extractors.gpt4o import GPT4oExtractor


def run_free_extractors(force: bool = False) -> dict[str, pd.DataFrame]:
    """Roda os 3 extractors gratuitos (local, whisper, mixed)."""
    return _run_extractors(
        [LocalExtractor(), WhisperExtractor(), MixedExtractor()],
        force=force,
    )


def run_paid_extractors(force: bool = False) -> dict[str, pd.DataFrame]:
    """Roda os 3 extractors pagos (metadata, gemini, gpt4o)."""
    return _run_extractors(
        [MetadataExtractor(), GeminiExtractor(), GPT4oExtractor()],
        force=force,
    )


def run_all_extractors(force: bool = False) -> dict[str, pd.DataFrame]:
    """Roda todos os 6 extractors na ordem correta."""
    return _run_extractors(
        [
            LocalExtractor(),
            WhisperExtractor(),
            MixedExtractor(),
            MetadataExtractor(),
            GeminiExtractor(),
            GPT4oExtractor(),
        ],
        force=force,
    )


def _run_extractors(extractors: list, force: bool = False) -> dict[str, pd.DataFrame]:
    df_posts = load_posts_base()
    print(f"Posts carregados: {len(df_posts)} ({(df_posts['media_type']=='video').sum()} video, "
          f"{(df_posts['media_type']=='image').sum()} image)\n")

    results = {}
    start = time.time()

    for ext in extractors:
        print(f"\n{'='*50}")
        t0 = time.time()
        df_feat = ext.extract(df_posts, force=force)
        elapsed = time.time() - t0
        results[ext.NAME] = df_feat
        print(f"Tempo: {elapsed:.1f}s")

    total = time.time() - start
    print(f"\n{'='*50}")
    print(f"TOTAL: {total:.0f}s ({total/60:.1f} min)")
    print(f"Features no cache: {sum(len(df.columns)-1 for df in results.values())} "
          f"({sum(len(df) for df in results.values())} registros)")

    return results


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "paid"
    if mode == "free":
        run_free_extractors()
    elif mode == "paid":
        run_paid_extractors()
    elif mode == "all":
        run_all_extractors()
    else:
        print(f"Uso: python -m scripts.pipeline [free|paid|all]")
