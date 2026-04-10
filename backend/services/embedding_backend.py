import logging
import math
import re
from hashlib import blake2b
from collections.abc import Iterable

from config import get_settings

logger = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"\w+")


class LocalFallbackEmbedder:
    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def encode(self, texts: str | Iterable[str]) -> list[list[float]]:
        if isinstance(texts, str):
            items = [texts]
        else:
            items = list(texts)
        return [self._encode_text(text) for text in items]

    def _encode_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in TOKEN_PATTERN.findall(text.lower()):
            token_hash = blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(token_hash, "big") % self.dimension
            vector[index] += 1.0

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return vector
        return [value / magnitude for value in vector]


def load_embedding_model():
    settings = get_settings()
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(settings.embedding_model, local_files_only=True)
    except Exception as exc:
        logger.warning(
            "Embedding model '%s' unavailable locally; using hash-based fallback embeddings. Root error: %s: %s",
            settings.embedding_model,
            exc.__class__.__name__,
            exc,
        )
        return LocalFallbackEmbedder()
