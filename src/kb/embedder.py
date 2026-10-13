"""Embeddings for norms (passage) and queries (query). Model: intfloat/multilingual-e5-large.

Prefixes are mandatory (constitution, Technical Constraints): mixing prefixes or models
invalidates the index. Therefore only two methods with fixed prefixes are exposed,
and there is no raw `encode`.
The model is loaded lazily on first use; `HF_HUB_OFFLINE=1` forbids network downloads.
"""

from __future__ import annotations

import threading

from src.config import Settings

PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


class E5Embedder:
    def __init__(self, model_name: str | None = None, model: object | None = None):
        self._model_name = model_name or Settings().embed_model
        self._model = model
        # A torch model must not be called from several threads at once: concurrent encode crashes
        # with a segfault (exit code 139). Loading and encode calls run under one lock.
        self._lock = threading.RLock()

    def _get_model(self):
        # Several analysis threads may request the model at once: it is loaded once under the lock.
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._model_name)
            return self._model

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        prefixed = [PASSAGE_PREFIX + text for text in texts]
        with self._lock:
            vectors = self._get_model().encode(
                prefixed, normalize_embeddings=True, show_progress_bar=False
            )
        return [list(map(float, vector)) for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        with self._lock:
            vector = self._get_model().encode(
                [QUERY_PREFIX + text],
                normalize_embeddings=True,
                show_progress_bar=False,
            )[0]
        return list(map(float, vector))
