"""
Extractor Mixed — 1 feature de edicao de video.

Features:
    4. cuts_per_minute  [R]  — cortes por minuto (scene detection + FFprobe)

Usa OpenCV para detectar mudancas bruscas entre frames consecutivos.
Abordagem: calcula diferenca de histogramas entre frames amostrados.
"""

import subprocess
import json as _json

import cv2
import numpy as np

from scripts.extractors.base import BaseExtractor


def _get_duration(filepath: str) -> float | None:
    """Obtem duracao do video em segundos via FFprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    data = _json.loads(result.stdout)
    dur = data.get("format", {}).get("duration")
    return float(dur) if dur else None


def _count_scene_changes(filepath: str, threshold: float = 0.4) -> int:
    """
    Conta mudancas de cena comparando histogramas de frames consecutivos.

    threshold: sensibilidade (0-1). Menor = mais sensivel.
    0.4 funciona bem para cortes tipicos de Reels.
    """
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        cap.release()
        return 0

    # Amostrar ~4 frames por segundo (suficiente para detectar cortes)
    sample_interval = max(1, int(fps / 4))

    prev_hist = None
    cuts = 0
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % sample_interval == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
            cv2.normalize(hist, hist)

            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
                if diff > threshold:
                    cuts += 1

            prev_hist = hist

        frame_idx += 1

    cap.release()
    return cuts


class MixedExtractor(BaseExtractor):
    NAME = "mixed"
    FEATURES = ["cuts_per_minute"]

    def _extract_one(self, post: dict) -> dict:
        media_type = post.get("media_type", "")

        if media_type != "video":
            return {"cuts_per_minute": None}

        primary = post.get("primary_filepath", "")

        duration = _get_duration(primary)
        if not duration or duration <= 0:
            return {"cuts_per_minute": None}

        cuts = _count_scene_changes(primary)
        duration_min = duration / 60.0
        cpm = round(cuts / duration_min, 1) if duration_min > 0 else 0.0

        return {"cuts_per_minute": cpm}
