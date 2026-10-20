"""
Extractor Metadata — 1 feature.

Features:
    2. carousel_slide_count  [C]  — numero de slides do carrossel

Extraido do campo file_count do DataFrame (contagem de arquivos por timestamp).
"""

from scripts.extractors.base import BaseExtractor


class MetadataExtractor(BaseExtractor):
    NAME = "metadata"
    FEATURES = ["carousel_slide_count"]

    def _extract_one(self, post: dict) -> dict:
        media_type = post.get("media_type", "")

        if media_type == "image":
            return {"carousel_slide_count": post.get("file_count", 0)}

        return {"carousel_slide_count": None}
