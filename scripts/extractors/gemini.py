"""
Extractor Gemini Flash — 23 features via Google AI API (batched).

Uma unica chamada por post: envia video/imagem + prompt batched,
recebe JSON com todas as features aplicaveis.
"""

import json
import time
from pathlib import Path

from google import genai
from google.genai import types

from scripts.config import GOOGLE_API_KEY, FEATURES_REF
from scripts.extractors.base import BaseExtractor

# Carregar features do Gemini do JSON de referencia
_ref = json.load(open(FEATURES_REF, encoding="utf-8"))
_GEMINI_FEATURES = [
    f for c in _ref["categories"]
    for f in c["features"]
    if f["model"] == "Gemini Flash"
]

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GOOGLE_API_KEY)
    return _client


def _build_prompt(post: dict, features: list[dict]) -> str:
    """Monta o prompt batched com todas as features aplicaveis."""
    caption = post.get("Caption", "") or ""
    media_type = post.get("media_type", "video")
    content_type = "Reel (video)" if media_type == "video" else "Carousel/Image"

    # Substituir placeholders nos prompts individuais
    # Whisper transcript vem do cache se disponivel
    transcript = ""
    cache_path = Path(post.get("_cache_dir", "")) / f"{post['timestamp']}.json"
    if cache_path.exists():
        cached = json.load(open(cache_path, encoding="utf-8"))
        if cached.get("speech_language") and cached.get("speech_language") != "none":
            transcript = "(transcript not available as raw text — analyze the audio directly)"

    first_line = caption.split("\n")[0][:150] if caption else ""

    lines = [
        f"You are analyzing an Instagram {content_type} post for a data science study.",
        f"Extract ALL of the following features from the content.",
        f"Return ONLY valid JSON with the exact feature names as keys.",
        f"Do NOT include any explanation or markdown — just the raw JSON object.",
        f"",
        f"Caption: {caption[:1500]}",
        f"Caption first line: {first_line}",
        f"",
        f"Features to extract:",
    ]

    for f in features:
        prompt = f["prompt"]
        prompt = prompt.replace("{caption_text}", caption[:500])
        prompt = prompt.replace("{whisper_transcript}", transcript)
        prompt = prompt.replace("{ocr_text}", "(analyze from the visual content)")
        prompt = prompt.replace("{caption_first_line}", first_line)

        vals = f["possible_values"][:200] if f["possible_values"] else ""
        lines.append(f"")
        lines.append(f"- \"{f['name']}\": {prompt}")
        lines.append(f"  Possible values: {vals}")

    lines.append(f"")
    lines.append(f"Return JSON object with exactly these {len(features)} keys. No extra text.")

    return "\n".join(lines)


def _applicable_features(media_type: str) -> list[dict]:
    """Filtra features aplicaveis ao tipo de midia."""
    type_code = "R" if media_type == "video" else "C"
    return [f for f in _GEMINI_FEATURES if type_code in f["applies_to"]]


class GeminiExtractor(BaseExtractor):
    NAME = "gemini"
    FEATURES = [f["name"] for f in _GEMINI_FEATURES]

    def _extract_one(self, post: dict) -> dict:
        media_type = post.get("media_type", "")
        primary = post.get("primary_filepath", "")
        post["_cache_dir"] = str(self.cache_dir)

        applicable = _applicable_features(media_type)
        if not applicable:
            return {f["name"]: None for f in _GEMINI_FEATURES}

        prompt = _build_prompt(post, applicable)
        client = _get_client()

        # Upload do arquivo de midia
        file_path = Path(primary)
        uploaded = client.files.upload(file=file_path)

        # Aguardar processamento (videos podem demorar)
        while uploaded.state == "PROCESSING":
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded, prompt],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4096,
            ),
        )

        # Parsear JSON da resposta
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            print(f"[gemini] JSON parse error for ts={post['timestamp']}: {text[:200]}")
            parsed = {}

        # Montar resultado com todas as features (None para nao-aplicaveis)
        result = {}
        applicable_names = {f["name"] for f in applicable}
        for f in _GEMINI_FEATURES:
            if f["name"] in applicable_names:
                result[f["name"]] = parsed.get(f["name"])
            else:
                result[f["name"]] = None

        # Limpar arquivo temporario do Gemini
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass

        return result
