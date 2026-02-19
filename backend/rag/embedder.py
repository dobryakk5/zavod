from __future__ import annotations

import logging
import threading
from typing import Iterable, List

from .config import config

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional runtime dependency
    SentenceTransformer = None  # type: ignore[assignment]

_model_lock = threading.Lock()
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is not None:
        return _model

    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not installed")

    with _model_lock:
        if _model is None:
            logger.info("Loading E5 embedding model from %s", config.e5_model_path)
            _model = SentenceTransformer(
                config.e5_model_path,
                tokenizer_kwargs={"fix_mistral_regex": True},
            )
    return _model


def _encode(texts: Iterable[str]) -> List[List[float]]:
    data = list(texts)
    if not data:
        return []
    vectors = get_model().encode(data, normalize_embeddings=True)
    return vectors.tolist()


def embed_passages(texts: list[str]) -> List[List[float]]:
    prefixed = [f"passage: {text}" for text in texts]
    return _encode(prefixed)


def embed_query(text: str) -> List[float]:
    encoded = _encode([f"query: {text}"])
    if not encoded:
        return []
    return encoded[0]
