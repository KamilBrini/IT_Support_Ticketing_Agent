"""Shared embedding-function selection for every ChromaDB collection in this app."""

from __future__ import annotations

import os

from chromadb.utils import embedding_functions


def build_embedding_function() -> embedding_functions.EmbeddingFunction:
    """Use OpenAI embeddings when a key is configured, else the same local
    offline model everywhere else in this app uses. Every collection (policy
    docs, per-user long-term memory, ...) must use the same function, or
    query vectors won't line up with stored vectors."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name="text-embedding-3-small",
        )

    return embedding_functions.DefaultEmbeddingFunction()
