"""
Phase 1 — Feature Discovery.

Reads the format definition, samples 25 posts stratified by Reach,
assembles content packages (caption + transcript + key frames),
and asks a high-quality AI model to propose format-specific features.

Outputs format_features_review.md for human review.
"""

import base64
import json
import re
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import whisper
from openai import OpenAI

from scripts.config import (
    FORMAT_DEFINITION_MD,
    FORMAT_FEATURES_REVIEW_MD,
    DATASET_PARQUET,
    POSTS_BASE_PARQUET,
    OPENAI_API_KEY,
    FEATURES_REF,
)

NUM_SAMPLE_POSTS = 15
NUM_BINS = 5
POSTS_PER_BIN = 3
NUM_KEY_FRAMES = 2

_whisper_model = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        print("[discover] Loading Whisper model...")
        _whisper_model = whisper.load_model("base")
    return _whisper_model


def _extract_key_frames(video_path: str, n_frames: int = NUM_KEY_FRAMES) -> list[str]:
    """Extract n evenly-spaced frames from a video, return as base64 JPEG strings."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"  [WARN] Could not open video: {video_path}")
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames < n_frames:
        n_frames = max(1, total_frames)

    indices = np.linspace(0, total_frames - 1, n_frames, dtype=int)
    frames_b64 = []

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
        frames_b64.append(base64.b64encode(buf).decode("utf-8"))

    cap.release()
    return frames_b64


def _transcribe(video_path: str) -> str:
    """Get Whisper transcript for a video file."""
    model = _get_whisper()
    try:
        result = model.transcribe(video_path, fp16=False)
        return result.get("text", "").strip()
    except Exception as e:
        print(f"  [WARN] Whisper failed for {video_path}: {e}")
        return ""


def select_stratified_sample(df: pd.DataFrame) -> pd.DataFrame:
    """
    Select 25 posts stratified by Reach: 5 bins x 5 posts each.
    Falls back to random sampling if a bin has fewer than 5 posts.
    """
    df = df.dropna(subset=["reach"]).copy()
    df["_reach_bin"] = pd.qcut(df["reach"], q=NUM_BINS, labels=False, duplicates="drop")

    samples = []
    for bin_idx in sorted(df["_reach_bin"].unique()):
        bin_df = df[df["_reach_bin"] == bin_idx]
        n = min(POSTS_PER_BIN, len(bin_df))
        samples.append(bin_df.sample(n=n, random_state=42))

    result = pd.concat(samples).drop(columns=["_reach_bin"])
    print(f"[discover] Stratified sample: {len(result)} posts across {NUM_BINS} performance bins")
    return result


def build_content_packages(sample_df: pd.DataFrame) -> list[dict]:
    """
    For each sample post, assemble: caption, transcript, key frame images.
    Returns list of dicts ready for the AI prompt.
    """
    packages = []
    for i, (_, row) in enumerate(sample_df.iterrows()):
        ts = row["timestamp"]
        caption = row.get("caption", "") or ""
        reach = row.get("reach", 0)
        media_type = row.get("media_type", "video")
        filepath = row.get("primary_filepath", "")

        print(f"  [{i+1}/{len(sample_df)}] ts={ts} reach={reach} media={media_type}")

        transcript = ""
        frames_b64 = []

        if media_type == "video" and filepath and Path(filepath).exists():
            transcript = _transcribe(filepath)
            frames_b64 = _extract_key_frames(filepath)

        packages.append({
            "index": i + 1,
            "timestamp": ts,
            "reach": reach,
            "caption": caption[:400],
            "transcript": transcript[:600],
            "frames_b64": frames_b64[:2],
            "media_type": media_type,
        })

    return packages


def _build_discovery_prompt(format_definition: str, packages: list[dict]) -> list[dict]:
    """Build the OpenAI messages array for the discovery call."""
    posts_text = []
    image_contents = []

    for pkg in packages:
        post_desc = (
            f"--- Post {pkg['index']} (Reach: {pkg['reach']}) ---\n"
            f"Caption: {pkg['caption']}\n"
            f"Transcript: {pkg['transcript'] or '(no transcript)'}\n"
        )
        posts_text.append(post_desc)

        for j, b64 in enumerate(pkg["frames_b64"]):
            image_contents.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                    "detail": "low",
                },
            })

    system_msg = (
        "You are an expert data scientist specializing in social media content analysis. "
        "You will receive a content format definition and 15 sample posts spanning the full "
        "performance spectrum (worst to best by Reach). Your job is to propose 15-25 features "
        "that are SPECIFIC to this content format.\n\n"
        "CRITICAL RULES:\n"
        "- Do NOT propose general video features (we already track 62 of those: duration, cuts, "
        "face presence, lighting, camera movement, audio type, etc.)\n"
        "- Focus on what distinguishes a GREAT post in this specific format from a mediocre one\n"
        "- Each feature must be extractable by AI from video frames + transcript + caption\n"
        "- Return valid JSON only, no markdown fences"
    )

    user_text = (
        f"## Content Format Definition\n\n{format_definition}\n\n"
        f"## Sample Posts (15 posts, sorted worst to best by Reach)\n\n"
        + "\n".join(posts_text) +
        "\n\n## Your Task\n\n"
        "Propose 15-25 features SPECIFIC to this content format. For each feature provide:\n"
        "- name (snake_case, descriptive)\n"
        "- description (1-2 sentences)\n"
        "- type: 'categorical' or 'numeric' or 'boolean' or 'multi-select'\n"
        "- possible_values: list of category strings (for categorical/multi-select), "
        "or {min, max, scale_description} for numeric, or ['true','false'] for boolean\n"
        "- why_it_matters: 1 sentence on why this feature might predict performance\n\n"
        "Return a JSON object: {\"features\": [{...}, ...]}"
    )

    user_content = [{"type": "text", "text": user_text}] + image_contents

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_content},
    ]


def call_discovery_model(format_definition: str, packages: list[dict]) -> list[dict]:
    """Send the discovery prompt to GPT-4o and parse the JSON response."""
    client = OpenAI(api_key=OPENAI_API_KEY)
    messages = _build_discovery_prompt(format_definition, packages)

    print("[discover] Calling GPT-4o for feature discovery...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=4096,
        temperature=0.7,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)
    features = data.get("features", data if isinstance(data, list) else [])
    print(f"[discover] Model proposed {len(features)} features")
    return features


def generate_review_markdown(features: list[dict]) -> str:
    """Convert the AI-proposed features into the human-reviewable Markdown format."""
    lines = [
        "# Format Features -- Review",
        "> Edit freely: rename features, rewrite descriptions, add/remove",
        "> categories, delete entire sections.",
        "> When done, run: python -m scripts.format.pipeline confirm",
        "",
        "---",
        "",
    ]

    for i, feat in enumerate(features, 1):
        name = feat.get("name", f"feature_{i}")
        desc = feat.get("description", "")
        ftype = feat.get("type", "categorical")
        values = feat.get("possible_values", [])
        why = feat.get("why_it_matters", "")

        lines.append(f"## {i}. {name}")
        lines.append(f"**Description:** {desc}")
        lines.append(f"**Type:** {ftype}")
        lines.append("")

        if ftype == "numeric" and isinstance(values, dict):
            lines.append("**Scale:**")
            lo = values.get("min", 1)
            hi = values.get("max", 5)
            scale_desc = values.get("scale_description", "")
            lines.append(f"- `{lo}` -- Minimum")
            lines.append(f"- `{hi}` -- Maximum")
            if scale_desc:
                lines.append(f"- {scale_desc}")
        elif isinstance(values, list):
            label = "Categories:" if ftype in ("categorical", "multi-select") else "Values:"
            lines.append(f"**{label}**")
            for val in values:
                if isinstance(val, dict):
                    v = val.get("value", val.get("name", str(val)))
                    d = val.get("description", "")
                    lines.append(f"- `{v}` -- {d}")
                else:
                    lines.append(f"- `{val}`")
        else:
            lines.append(f"**Possible values:** {values}")

        if why:
            lines.append("")
            lines.append(f"*Why it matters:* {why}")

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def run_discovery():
    """Main entry point: run the full discovery pipeline."""
    if not FORMAT_DEFINITION_MD.exists():
        raise FileNotFoundError(
            f"Format definition not found: {FORMAT_DEFINITION_MD}\n"
            "Create this file first describing your content format."
        )

    format_def = FORMAT_DEFINITION_MD.read_text(encoding="utf-8")
    print(f"[discover] Loaded format definition ({len(format_def)} chars)")

    if not DATASET_PARQUET.exists():
        raise FileNotFoundError(
            f"General dataset not found: {DATASET_PARQUET}\n"
            "Run the general pipeline first."
        )

    df = pd.read_parquet(DATASET_PARQUET)
    print(f"[discover] Loaded dataset: {len(df)} posts")

    if "reach" not in df.columns and "Reach" in df.columns:
        df = df.rename(columns={"Reach": "reach"})

    sample_df = select_stratified_sample(df)

    print("[discover] Building content packages (transcript + frames)...")
    packages = build_content_packages(sample_df)

    features = call_discovery_model(format_def, packages)

    review_md = generate_review_markdown(features)
    FORMAT_FEATURES_REVIEW_MD.write_text(review_md, encoding="utf-8")
    print(f"\n[discover] Review file written: {FORMAT_FEATURES_REVIEW_MD}")
    print(f"[discover] {len(features)} features proposed.")
    print(f"\nNext step: review and edit {FORMAT_FEATURES_REVIEW_MD.name}")
    print("Then run: python -m scripts.format.pipeline confirm")

    return features
