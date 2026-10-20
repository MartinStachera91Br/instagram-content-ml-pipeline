"""
Extractor GPT-4o — 28 features via OpenAI API (batched).

Uma unica chamada por post: envia frames extraidos + caption + prompt batched,
recebe JSON com todas as features aplicaveis.

Para Reels: envia 3 frames (primeiro, meio, ultimo) + caption.
Para Carrosseis/Imagens: envia a primeira imagem + caption.
"""

import base64
import json
import subprocess
import tempfile
import os
from pathlib import Path

import openai

from scripts.config import OPENAI_API_KEY, FEATURES_REF
from scripts.extractors.base import BaseExtractor

# Carregar features GPT-4o do JSON
_ref = json.load(open(FEATURES_REF, encoding="utf-8"))
_GPT4O_FEATURES = [
    f for c in _ref["categories"]
    for f in c["features"]
    if f["model"] == "GPT-4o"
]

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = openai.OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _extract_frames(video_path: str, n_frames: int = 3) -> list[str]:
    """
    Extrai N frames do video via FFmpeg. Retorna lista de paths temporarios.
    Frames: primeiro, meio, ultimo.
    """
    # Obter duracao
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json", video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    dur = float(json.loads(result.stdout)["format"]["duration"])

    timestamps = [0.5, dur / 2, max(dur - 1, 0.5)]
    if n_frames == 1:
        timestamps = [0.5]

    tmp_dir = tempfile.mkdtemp(prefix="genna_frames_")
    paths = []

    for i, ts in enumerate(timestamps):
        out = os.path.join(tmp_dir, f"frame_{i}.jpg")
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-ss", str(ts),
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            out,
        ]
        subprocess.run(cmd, capture_output=True, timeout=15)
        if os.path.exists(out):
            paths.append(out)

    return paths


def _image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _build_prompt(post: dict, features: list[dict]) -> str:
    """Monta o prompt batched para GPT-4o."""
    caption = post.get("Caption", "") or ""
    media_type = post.get("media_type", "video")
    content_type = "Reel (video)" if media_type == "video" else "Carousel/Image"

    frame_desc = ("3 frames: first, middle, and last" if media_type == "video"
                  else "the first image/slide")

    lines = [
        f"You are analyzing an Instagram {content_type} post for a data science study.",
        f"You are given {frame_desc} from the content.",
        f"Extract ALL of the following features.",
        f"Return ONLY valid JSON with the exact feature names as keys.",
        f"Do NOT include any explanation, markdown, or extra text — just the raw JSON object.",
        f"",
        f"Caption: {caption[:1500]}",
        f"",
        f"Features to extract:",
    ]

    for f in features:
        prompt = f["prompt"]
        prompt = prompt.replace("{caption_text}", caption[:500])
        vals = f["possible_values"][:200] if f["possible_values"] else ""
        lines.append(f"")
        lines.append(f"- \"{f['name']}\": {prompt}")
        lines.append(f"  Values: {vals}")

    lines.append(f"")
    lines.append(f"Return JSON with exactly {len(features)} keys.")

    return "\n".join(lines)


def _applicable_features(media_type: str) -> list[dict]:
    type_code = "R" if media_type == "video" else "C"
    return [f for f in _GPT4O_FEATURES if type_code in f["applies_to"]]


class GPT4oExtractor(BaseExtractor):
    NAME = "gpt4o"
    FEATURES = [f["name"] for f in _GPT4O_FEATURES]

    def _extract_one(self, post: dict) -> dict:
        media_type = post.get("media_type", "")
        primary = post.get("primary_filepath", "")

        applicable = _applicable_features(media_type)
        if not applicable:
            return {f["name"]: None for f in _GPT4O_FEATURES}

        prompt = _build_prompt(post, applicable)
        client = _get_client()

        # Preparar imagens
        frame_paths = []
        try:
            if media_type == "video":
                frame_paths = _extract_frames(primary, n_frames=3)
            else:
                frame_paths = [primary]

            # Montar mensagem com imagens
            content = []
            for fp in frame_paths:
                b64 = _image_to_base64(fp)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"},
                })
            content.append({"type": "text", "text": prompt})

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                temperature=0.1,
                max_tokens=4096,
            )

            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                print(f"[gpt4o] JSON parse error for ts={post['timestamp']}: {text[:200]}")
                parsed = {}

        finally:
            # Limpar frames temporarios (nao apagar originais de carrosseis)
            if media_type == "video":
                for fp in frame_paths:
                    try:
                        os.remove(fp)
                    except OSError:
                        pass
                # Remover dir temporario
                if frame_paths:
                    try:
                        os.rmdir(os.path.dirname(frame_paths[0]))
                    except OSError:
                        pass

        # Resultado
        result = {}
        applicable_names = {f["name"] for f in applicable}
        for f in _GPT4O_FEATURES:
            if f["name"] in applicable_names:
                result[f["name"]] = parsed.get(f["name"])
            else:
                result[f["name"]] = None

        return result
