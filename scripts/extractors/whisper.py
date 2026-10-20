"""
Extractor Whisper (gratuito, local) — 2 features de audio.

Features:
    35. speech_language     [R]  — ISO 639-1 code do idioma falado
    36. speech_pacing_wpm   [R]  — palavras por minuto

Requer FFmpeg instalado. O modelo Whisper (~1.5GB) e baixado no primeiro uso.
"""

import whisper

from scripts.extractors.base import BaseExtractor

# Carrega o modelo uma unica vez (lazy load)
_model = None


def _get_model():
    global _model
    if _model is None:
        print("[whisper] Carregando modelo 'base' (primeira vez pode demorar)...")
        _model = whisper.load_model("base")
    return _model


class WhisperExtractor(BaseExtractor):
    NAME = "whisper"
    FEATURES = [
        "speech_language",
        "speech_pacing_wpm",
    ]

    def _extract_one(self, post: dict) -> dict:
        media_type = post.get("media_type", "")

        if media_type != "video":
            return {"speech_language": None, "speech_pacing_wpm": None}

        primary = post.get("primary_filepath", "")
        model = _get_model()

        result_whisper = model.transcribe(primary, fp16=False)

        language = result_whisper.get("language", "none")
        text = result_whisper.get("text", "").strip()
        segments = result_whisper.get("segments", [])

        if not text or not segments:
            return {"speech_language": "none", "speech_pacing_wpm": 0}

        # Calcular WPM: total de palavras / duracao da fala em minutos
        words = text.split()
        total_words = len(words)

        first_start = segments[0]["start"]
        last_end = segments[-1]["end"]
        speech_duration_min = (last_end - first_start) / 60.0

        if speech_duration_min > 0:
            wpm = round(total_words / speech_duration_min)
        else:
            wpm = 0

        return {
            "speech_language": language,
            "speech_pacing_wpm": wpm,
        }
