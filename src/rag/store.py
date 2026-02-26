"""
Vector store with metadata filter support (Chroma).

One collection for travel Knowledge Objects; metadata = price_tier, location, type, etc.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Lazy imports so chroma/embedding deps are optional until RAG is used
_collection = None

DEFAULT_PERSIST_DIR = "data/chroma"


def _get_embedding_function():
    from langchain_openai import OpenAIEmbeddings
    return OpenAIEmbeddings(model="text-embedding-3-small")


def get_store(persist_directory: str | Path | None = None):
    """Return Chroma vector store for travel Knowledge Objects."""
    global _collection
    if _collection is None:
        from langchain_chroma import Chroma
        persist = str(persist_directory) if persist_directory else os.environ.get("CHROMA_PERSIST_DIR", DEFAULT_PERSIST_DIR)
        _collection = Chroma(
            collection_name="promptroam_travel",
            embedding_function=_get_embedding_function(),
            persist_directory=persist,
        )
    return _collection


def add_knowledge_objects(store, documents: list[tuple[str, dict[str, Any]]]) -> None:
    """Add (page_content, metadata) pairs to the store. No fixed-size chunking."""
    from langchain_core.documents import Document
    docs = [Document(page_content=text, metadata=meta) for text, meta in documents]
    store.add_documents(docs)


def query_with_metadata(
    store,
    query: str,
    *,
    filter_metadata: dict[str, Any] | None = None,
    k: int = 5,
) -> list[tuple[Any, float]]:
    """
    Semantic search with optional metadata filter (applied at query time).
    Returns list of (Document, score). Scores retained for threshold gating (no RRF).
    """
    kwargs: dict[str, Any] = {"k": k}
    if filter_metadata:
        kwargs["filter"] = filter_metadata
    results = store.similarity_search_with_score(query, **kwargs)
    return results
