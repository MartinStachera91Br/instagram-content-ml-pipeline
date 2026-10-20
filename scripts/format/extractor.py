"""
Phase 2 — Format Feature Extraction.

For each post: sends key frames + transcript + caption to an AI model,
using the confirmed format_features_reference.json as the extraction schema.

Caches results at data/format_features_cache/{timestamp}.json.
Mirrors the general pipeline's BaseExtractor pattern but uses a dynamic
feature list loaded from the reference JSON.
"""

import base64
import json
import re
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import whisper
from google import genai
from google.genai import types
from tqdm import tqdm

from scripts.config import (
    FORMAT_FEATURES_REF,
    FORMAT_FEATURES_CACHE_DIR,
    GOOGLE_API_KEY,
    POSTS_BASE_PARQUET,
)

NUM_KEY_FRAMES = 4
MAX_RETRIES = 2
RETRY_DELAY = 5

_whisper_model = None
_gemini_client = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        print("[format-extractor] Loading Whisper model...")
        _whisper_model = whisper.load_model("base")
    return _whisper_model


def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
    return _gemini_client


def _load_feature_schema() -> tuple[list[dict], list[str]]:
    """Load confirmed format features and return (features_list, feature_names)."""
    if not FORMAT_FEATURES_REF.exists():
        raise FileNotFoundError(
            f"Format features reference not found: {FORMAT_FEATURES_REF}\n"
            "Run 'python -m scripts.format.pipeline confirm' first."
        )
    data = json.loads(FORMAT_FEATURES_REF.read_text(encoding="utf-8"))
    features = data.get("features", [])
    names = [f["name"] for f in features]
    return features, names


def _extract_key_frames_bytes(video_path: str, n_frames: int = NUM_KEY_FRAMES) -> list[bytes]:
    """Extract n evenly-spaced frames from a video as JPEG bytes."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total < n_frames:
        n_frames = max(1, total)

    indices = np.linspace(0, total - 1, n_frames, dtype=int)
    frames = []

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        h, w = frame.shape[:2]
        max_dim = 512
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        frames.append(buf.tobytes())

    cap.release()
    return frames


def _transcribe(video_path: str) -> str:
    """Get Whisper transcript for a video file."""
    model = _get_whisper()
    try:
        result = model.transcribe(video_path, fp16=False)
        return result.get("text", "").strip()
    except Exception as e:
        print(f"  [WARN] Whisper failed: {e}")
        return ""


def _parse_json_robust(raw: str) -> dict:
    """Try multiple strategies to extract a JSON dict from AI response text."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r"\{[\s\S]*\}", raw)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    if raw.lstrip().startswith("{") and "}" not in raw:
        patched = raw.rstrip().rstrip(",") + "\n}"
        try:
            return json.loads(patched)
        except json.JSONDecodeError:
            pass

    lines = raw.strip().split("\n")
    for i in range(len(lines) - 1, 0, -1):
        attempt = "\n".join(lines[:i]).rstrip().rstrip(",") + "\n}"
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue

    print(f"  [WARN] Could not parse JSON from response ({len(raw)} chars)")
    return {}


def _build_extraction_prompt(features: list[dict], caption: str, transcript: str) -> str:
    """Build the prompt that tells the model which features to extract."""
    features_desc = []
    for f in features:
        vals = f.get("possible_values", [])
        if isinstance(vals, list):
            vals_str = ", ".join(
                v.get("value", str(v)) if isinstance(v, dict) else str(v)
                for v in vals
            )
        else:
            vals_str = str(vals)

        features_desc.append(
            f"- {f['name']} ({f.get('type', 'categorical')}): {f['description']}. "
            f"Values: [{vals_str}]"
        )

    return (
        "You are analyzing a social media video post. Extract the following format-specific "
        "features based on the video frames, transcript, and caption provided.\n\n"
        "FEATURES TO EXTRACT:\n"
        + "\n".join(features_desc)
        + "\n\n"
        f"CAPTION:\n{caption or '(no caption)'}\n\n"
        f"TRANSCRIPT:\n{transcript or '(no transcript)'}\n\n"
        "Return a JSON object with each feature name as key and the extracted value. "
        "Use exactly the value strings from the allowed values list. "
        "For numeric features, return a number. For boolean, return true/false. "
        "Return ONLY valid JSON, no markdown fences."
    )


def _extract_one_post(
    post: dict,
    features: list[dict],
    feature_names: list[str],
) -> dict:
    """Extract format features for a single post using Gemini Flash."""
    media_type = post.get("media_type", "video")
    filepath = post.get("primary_filepath", "")
    caption = post.get("caption", post.get("Caption", "")) or ""

    transcript = ""
    frame_bytes_list = []

    if media_type == "video" and filepath and Path(filepath).exists():
        transcript = _transcribe(filepath)
        frame_bytes_list = _extract_key_frames_bytes(filepath)

    prompt_text = _build_extraction_prompt(features, caption, transcript)

    contents = [prompt_text]
    for fb in frame_bytes_list:
        contents.append(types.Part.from_bytes(data=fb, mime_type="image/jpeg"))

    client = _get_gemini()

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    max_output_tokens=4096,
                    temperature=0.2,
                ),
            )
            break
        except Exception as e:
            if attempt < MAX_RETRIES and ("503" in str(e) or "UNAVAILABLE" in str(e)):
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            raise

    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
    raw = re.sub(r"\n?\s*```\s*$", "", raw)

    result = _parse_json_robust(raw)

    return {name: result.get(name) for name in feature_names}


# =========================================================================
# Cache management
# =========================================================================

def _cache_path(timestamp: int) -> Path:
    return FORMAT_FEATURES_CACHE_DIR / f"{timestamp}.json"


def _load_cache(timestamp: int) -> dict:
    path = _cache_path(timestamp)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_cache(timestamp: int, features: dict) -> None:
    existing = _load_cache(timestamp)
    existing.update(features)
    FORMAT_FEATURES_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(timestamp).write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _has_cached(timestamp: int, feature_names: list[str]) -> bool:
    cached = _load_cache(timestamp)
    return all(f in cached for f in feature_names)


# =========================================================================
# Main extraction loop
# =========================================================================

def run_format_extraction(force: bool = False):
    """Extract format features for all posts."""
    features, feature_names = _load_feature_schema()
    print(f"[format-extractor] {len(features)} features to extract: {feature_names}")

    if not POSTS_BASE_PARQUET.exists():
        raise FileNotFoundError(
            f"Posts base not found: {POSTS_BASE_PARQUET}\n"
            "Run the general pipeline Phase 1 first."
        )

    df_posts = pd.read_parquet(POSTS_BASE_PARQUET)
    print(f"[format-extractor] {len(df_posts)} posts to process")

    FORMAT_FEATURES_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    extracted = 0
    skipped = 0
    errors = 0

    for _, row in tqdm(df_posts.iterrows(), total=len(df_posts), desc="Format extraction"):
        ts = row["timestamp"]

        if not force and _has_cached(ts, feature_names):
            skipped += 1
            continue

        try:
            result = _extract_one_post(row.to_dict(), features, feature_names)
            _save_cache(ts, result)
            extracted += 1
        except Exception as e:
            print(f"\n  [ERROR] ts={ts}: {e}")
            null_result = {name: None for name in feature_names}
            _save_cache(ts, null_result)
            errors += 1

    print(f"\n[format-extractor] Done: {extracted} extracted, {skipped} cached, {errors} errors")
