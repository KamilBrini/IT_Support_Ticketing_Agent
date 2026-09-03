"""Retrieve top-k policy context chunks from ChromaDB."""

from __future__ import annotations

import os
from pathlib import Path

import chromadb

from src.rag.embeddings import build_embedding_function

COLLECTION_NAME = "it_policy_docs"
DEFAULT_CHROMA_PATH = Path("./data/chroma")

# Chunks with a query distance above this are treated as "not actually about
# this question" and dropped, so an out-of-scope question (e.g. "policy for
# lunar mining on Mars") returns no context and the agent escalates instead
# of grounding an answer in whichever policy doc happened to be least
# dissimilar. Calibrated against data/policies/*.md with the default local
# embedding model: real matches score ~0.6-0.7, off-topic queries score 1.5+.
MAX_RELEVANT_DISTANCE = 1.2


def retrieve_context(query: str, k: int = 3) -> list[str]:
    """Query it_policy_docs and return top-k matching chunk texts."""
    if not query.strip():
        return []

    k = max(1, k)
    chroma_path = Path(os.getenv("CHROMA_DB_PATH", str(DEFAULT_CHROMA_PATH)))
    client = chromadb.PersistentClient(path=str(chroma_path))

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=build_embedding_function(),
    )

    result = collection.query(query_texts=[query], n_results=k, include=["documents", "distances"])
    docs = result.get("documents", [])
    distances = result.get("distances", [])
    if not docs:
        return []

    first_query_docs = docs[0] if docs else []
    first_query_distances = distances[0] if distances else []

    relevant: list[str] = []
    for doc, distance in zip(first_query_docs, first_query_distances):
        if isinstance(doc, str) and distance <= MAX_RELEVANT_DISTANCE:
            relevant.append(doc)
    return relevant
