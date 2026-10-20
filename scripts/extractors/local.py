"""
Extractor local (gratuito) — 7 features extraidas sem API.

Features:
     1. video_duration_sec    [R]      — FFprobe
     3. aspect_ratio          [R;C;I]  — FFprobe / Pillow
    12. face_presence          [R;C;I]  — OpenCV Haar Cascade
    57. caption_length_chars   [R;C;I]  — len()
    58. hashtag_count          [R;C;I]  — regex
    61. emoji_density          [R;C;I]  — regex unicode ranges
    62. account_mentions_count [R;C;I]  — regex
"""

import os
import re
import subprocess
import json as _json
import tempfile

import cv2
import numpy as np
from PIL import Image

from scripts.extractors.base import BaseExtractor

# Regex para emojis (Unicode emoji ranges)
_EMOJI_RE = re.compile(
    "[\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"   # symbols & pictographs
    "\U0001F680-\U0001F6FF"   # transport & map
    "\U0001F1E0-\U0001F1FF"   # flags
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"   # supplemental symbols
    "\U0001FA00-\U0001FA6F"   # chess symbols
    "\U0001FA70-\U0001FAFF"   # symbols extended-A
    "\U00002600-\U000026FF"   # misc symbols
    "\U0000FE00-\U0000FE0F"   # variation selectors
    "\U0000200D"              # ZWJ
    "\U00000023\U0000FE0F\U000020E3"  # keycap #
    "]+",
    flags=re.UNICODE,
)

# OpenCV nao lida bem com unicode nos paths (Windows com acentos).
# Workaround: ler o arquivo como bytes e carregar via FileStorage.
def _load_cascade() -> cv2.CascadeClassifier:
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    fs = cv2.FileStorage(cascade_path, cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        import shutil, tempfile
        tmp = tempfile.mkdtemp()
        dst = shutil.copy(cascade_path, tmp)
        cascade = cv2.CascadeClassifier(dst)
        if cascade.empty():
            raise RuntimeError(f"Nao conseguiu carregar cascade de: {cascade_path}")
        return cascade
    fs.release()
    return cv2.CascadeClassifier(cascade_path)


_FACE_CASCADE = _load_cascade()


def _ffprobe_video_info(filepath: str) -> dict:
    """Extrai duration, width, height de um video via FFprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-show_entries", "format=duration",
        "-of", "json",
        filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    data = _json.loads(result.stdout)

    width, height, duration = None, None, None

    if data.get("streams"):
        stream = data["streams"][0]
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))
        duration = stream.get("duration")

    if duration is None and data.get("format"):
        duration = data["format"].get("duration")

    if duration is not None:
        duration = float(duration)

    return {"width": width, "height": height, "duration": duration}


def _classify_aspect_ratio(width: int, height: int) -> str:
    """Classifica aspect ratio com tolerancia de 5%."""
    if not width or not height:
        return "other"

    ratio = width / height
    checks = [
        (0.5625, "vertical_9x16"),
        (0.8, "vertical_4x5"),
        (1.0, "square_1x1"),
        (1.778, "horizontal_16x9"),
    ]
    for target, label in checks:
        if abs(ratio - target) / target <= 0.05:
            return label

    if ratio > 1.0:
        return "horizontal_other"
    return "other"


def _imread_unicode(path: str) -> np.ndarray | None:
    """cv2.imread que funciona com paths unicode no Windows."""
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    return img


def _detect_faces_from_array(img: np.ndarray) -> int:
    """Conta rostos usando Haar Cascade a partir de array numpy."""
    if img is None:
        return 0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return len(faces)


def _extract_first_frame(video_path: str) -> np.ndarray | None:
    """Extrai primeiro frame de um video como array numpy."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        # Fallback: FFmpeg para extrair frame quando VideoCapture falha com unicode
        tmp = os.path.join(tempfile.gettempdir(), "_genna_frame0.jpg")
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", video_path,
            "-frames:v", "1",
            tmp,
        ]
        subprocess.run(cmd, capture_output=True, timeout=15)
        if os.path.exists(tmp):
            img = cv2.imread(tmp)
            os.remove(tmp)
            return img
        return None
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


def _count_emojis(text: str) -> int:
    """Conta emojis individuais no texto."""
    matches = _EMOJI_RE.findall(text)
    return sum(len(m) for m in matches)


def _classify_emoji_density(count: int) -> str:
    if count == 0:
        return "none"
    elif count <= 3:
        return "low"
    elif count <= 10:
        return "medium"
    elif count <= 20:
        return "high"
    return "extreme"


class LocalExtractor(BaseExtractor):
    NAME = "local"
    FEATURES = [
        "video_duration_sec",
        "aspect_ratio",
        "face_presence",
        "caption_length_chars",
        "hashtag_count",
        "emoji_density",
        "account_mentions_count",
    ]

    def _extract_one(self, post: dict) -> dict:
        media_type = post.get("media_type", "")
        primary = post.get("primary_filepath", "")
        caption = post.get("Caption", "") or ""

        result = {}

        # --- video_duration_sec (R only) ---
        if media_type == "video":
            info = _ffprobe_video_info(primary)
            result["video_duration_sec"] = int(info["duration"]) if info["duration"] else None
            result["aspect_ratio"] = _classify_aspect_ratio(info["width"], info["height"])

            frame = _extract_first_frame(primary)
            n_faces = _detect_faces_from_array(frame)
        else:
            result["video_duration_sec"] = None

            try:
                img = Image.open(primary)
                w, h = img.size
                result["aspect_ratio"] = _classify_aspect_ratio(w, h)
            except Exception:
                result["aspect_ratio"] = None

            img_cv = _imread_unicode(primary)
            n_faces = _detect_faces_from_array(img_cv)

        if n_faces == 0:
            result["face_presence"] = "no_face"
        elif n_faces == 1:
            result["face_presence"] = "single_face"
        else:
            result["face_presence"] = "multiple_faces"

        # --- Caption features (R; C; I) ---
        result["caption_length_chars"] = len(caption)
        result["hashtag_count"] = len(re.findall(r"#\w+", caption))
        result["account_mentions_count"] = len(re.findall(r"@\w+", caption))

        emoji_count = _count_emojis(caption)
        result["emoji_density"] = _classify_emoji_density(emoji_count)

        return result
