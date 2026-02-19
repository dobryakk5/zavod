"""RAG helpers for knowledge-base semantic indexing and search."""

from __future__ import annotations

from typing import Any


def index_document(*args: Any, **kwargs: Any):
    from .ingestion import index_document as _index_document

    return _index_document(*args, **kwargs)


def reindex_kb_documents(*args: Any, **kwargs: Any):
    from .ingestion import reindex_kb_documents as _reindex_kb_documents

    return _reindex_kb_documents(*args, **kwargs)


def semantic_search_kb(*args: Any, **kwargs: Any):
    from .retrieval import semantic_search_kb as _semantic_search_kb

    return _semantic_search_kb(*args, **kwargs)

__all__ = ["index_document", "reindex_kb_documents", "semantic_search_kb"]
