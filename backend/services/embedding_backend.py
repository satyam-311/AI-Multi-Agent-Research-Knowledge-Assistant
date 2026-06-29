# embedding_backend.py
# Embedding model loader for the MARKA vector retrieval layer.
# Attempts to load the configured sentence-transformer model from the local
# HuggingFace cache. Falls back to a deterministic hash-based embedder
# that maintains the same vector dimensionality so ChromaDB remains operable
# even when the model is unavailable.

import logging
import math
import re
# blake2b is used by LocalFallbackEmbedder for fast, deterministic token hashing
from hashlib import blake2b
from collections.abc import Iterable

# Application settings provide the embedding model name
from backend.config import get_settings

logger = logging.getLogger(__name__)

# Pre-compiled pattern to extract word tokens; avoids re-compiling on every encode call
TOKEN_PATTERN = re.compile(r"\w+")


class LocalFallbackEmbedder:
    """
    Deterministic hash-based text embedder used when sentence-transformers is unavailable.

    Produces 384-dimensional L2-normalized vectors by:
    1. Tokenizing the input text into word tokens.
    2. Hashing each token with BLAKE2b to a bucket index in [0, dimension).
    3. Incrementing that bucket by 1.0 for each occurrence.
    4. L2-normalizing the result so cosine similarity comparisons remain valid.

    This approach preserves vocabulary structure (the same word always maps to the
    same index) and produces the same dimensionality as the real model (384), so
    ChromaDB queries still return results. Retrieval quality is degraded compared
    to the semantic model, but the application remains functional.

    Attributes:
        dimension (int): Vector dimensionality; must match the real model's output.
    """

    def __init__(self, dimension: int = 384) -> None:
        # 384 matches all-MiniLM-L6-v2's output size so ChromaDB collections
        # created with this fallback remain compatible with the real model
        self.dimension = dimension

    def encode(self, texts: str | Iterable[str]) -> list[list[float]]:
        """
        Encode one or more text strings into L2-normalized vectors.

        Args:
            texts (str | Iterable[str]): A single string or iterable of strings to encode.
                Matches the sentence-transformers SentenceTransformer.encode interface.

        Returns:
            list[list[float]]: A list of float vectors, one per input text.
        """
        if isinstance(texts, str):
            items = [texts]
        else:
            items = list(texts)
        return [self._encode_text(text) for text in items]

    def _encode_text(self, text: str) -> list[float]:
        """
        Encode a single text string into a 384-dimensional L2-normalized vector.

        Args:
            text (str): Input text to encode.

        Returns:
            list[float]: L2-normalized float vector of length self.dimension.
        """
        vector = [0.0] * self.dimension
        for token in TOKEN_PATTERN.findall(text.lower()):
            # BLAKE2b produces a stable 8-byte digest; modulo maps it to a bucket index
            token_hash = blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(token_hash, "big") % self.dimension
            vector[index] += 1.0

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            # Return the zero vector unchanged; this occurs for empty or punctuation-only text
            return vector
        # L2-normalize so cosine similarity between query and chunk vectors is well-defined
        return [value / magnitude for value in vector]


def load_embedding_model():
    """
    Load the configured sentence-transformer model from the local HuggingFace cache.

    Uses local_files_only=True to avoid unexpected network calls during inference.
    If the model is not cached locally or cannot be loaded for any reason, logs a
    warning and returns a LocalFallbackEmbedder instead of raising an exception.

    The caller (EmbeddingAgent, RetrievalAgent) should use the returned object's
    .encode() method, which is compatible with both the real model and the fallback.

    Returns:
        SentenceTransformer | LocalFallbackEmbedder: The loaded model if available,
        otherwise a hash-based fallback embedder with the same interface.
    """
    settings = get_settings()
    try:
        from sentence_transformers import SentenceTransformer

        # local_files_only=True prevents the model from downloading at request time,
        # which would cause high latency or failures in air-gapped environments
        return SentenceTransformer(settings.embedding_model, local_files_only=True)
    except Exception as exc:
        logger.warning(
            "Embedding model '%s' unavailable locally; using hash-based fallback embeddings. Root error: %s: %s",
            settings.embedding_model,
            exc.__class__.__name__,
            exc,
        )
        return LocalFallbackEmbedder()
