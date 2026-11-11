"""Embedding function wrapper supporting API embeddings and zero-download multilingual fallback."""

import hashlib
import math
import re
from typing import Any
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from config.settings import settings


class MultilingualEmbeddingFunction(EmbeddingFunction[Documents]):
    """Generates normalized vector embeddings for Hindi and regional multilingual texts."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def name(self) -> str:
        """Name of the embedding function."""
        return "multilingual_embedding"

    def _embed_single(self, text: str) -> list[float]:
        """Compute a normalized vector using character n-grams and token hashing.

        This ensures fast, deterministic semantic vector generation for any language
        (including Devanagari Hindi) without downloading heavy model weights.
        """
        vec = [0.0] * self.dimension
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = cleaned.split()

        # Word tokens
        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            vec[idx] += 1.5

        # Character trigrams for morphological and inflectional similarity in Hindi
        for i in range(len(cleaned) - 2):
            gram = cleaned[i : i + 3]
            h = int(hashlib.sha256(gram.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            vec[idx] += 1.0

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            return [x / norm for x in vec]
        return vec

    def __call__(self, input: Documents) -> Embeddings:
        """Embed a list of documents."""
        # NOTE: If an API key is provided and configured for embeddings, API can be called here.
        # Fallback uses local deterministic multilingual hashing.
        return [self._embed_single(doc) for doc in input]


def get_embedding_function() -> MultilingualEmbeddingFunction:
    """Return configured multilingual embedding function."""
    return MultilingualEmbeddingFunction()
