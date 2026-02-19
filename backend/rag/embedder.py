from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any, Iterable, List

from .config import config

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sentence_transformers import SentenceTransformer

_model_lock = threading.Lock()
_model: Any | None = None


def _load_sentence_transformer_class():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError("sentence-transformers is not installed") from exc
    return SentenceTransformer


def get_model() -> "SentenceTransformer":
    global _model
    if _model is not None:
        return _model

    with _model_lock:
        if _model is None:
            SentenceTransformer = _load_sentence_transformer_class()
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
