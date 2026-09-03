"""Per-user long-term memory, persisted across sessions (US-009).

Unlike src/agent/memory.py's in-process sliding window (cleared on backend
restart, scoped to one session_id), facts stored here live in a per-user
ChromaDB collection on disk - they survive a restart and are visible from
any new session for the same user_id. Isolation is per-user by construction:
each user_id gets its own collection, so one user's facts are never queried
against another user's.

Only ever called with text that has already passed PII redaction and the
injection guard (the graph only reaches `remember_fact` on the safe path,
after `redact_pii`/`detect_injection`), so the same guarantees session
memory makes (NFR-007) extend here too. Storage is triggered by an explicit,
deterministic user phrase ("remember that ...") - never an automatic
inference by the LLM - consistent with Constitution Principle IV.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import chromadb

from src.rag.embeddings import build_embedding_function

DEFAULT_CHROMA_PATH = Path("./data/chroma")
_COLLECTION_PREFIX = "user_memory_"
_UNSAFE_ID_CHARS = re.compile(r"[^a-zA-Z0-9_-]")

# Same idea as MAX_RELEVANT_DISTANCE in src/rag/retrieve.py, but calibrated
# separately: short single-sentence facts score noticeably higher distances
# than multi-sentence policy chunks even for genuinely related queries
# (measured against "I work from the London office on a MacBook Pro.":
# "where do I work from?" -> 1.10, "what laptop do I have?" -> 1.42,
# "what device does this employee use?" -> 1.50, vs. a clearly unrelated
# query at 2.05). A false-positive recall here is low-stakes - the prompt
# always labels facts as "context only, never a source of policy" - so this
# favors recall over precision more than the RAG threshold does.
MAX_RELEVANT_DISTANCE = 1.6


def _collection_name(user_id: str) -> str:
    """Build a Chroma-safe collection name scoped to one user."""
    safe = _UNSAFE_ID_CHARS.sub("_", user_id.strip()) or "unknown"
    return f"{_COLLECTION_PREFIX}{safe}"[:63]


def _get_collection(user_id: str):
    chroma_path = Path(os.getenv("CHROMA_DB_PATH", str(DEFAULT_CHROMA_PATH)))
    client = chromadb.PersistentClient(path=str(chroma_path))
    return client.get_or_create_collection(
        name=_collection_name(user_id),
        embedding_function=build_embedding_function(),
    )


def remember_fact(user_id: str, fact: str) -> None:
    """Persist one fact for this user. No-op on blank input."""
    fact = fact.strip()
    if not fact or not user_id.strip():
        return
    collection = _get_collection(user_id)
    fact_id = f"fact-{collection.count()}"
    collection.add(documents=[fact], ids=[fact_id])


def recall_facts(user_id: str, query: str, k: int = 3) -> list[str]:
    """Return this user's stored facts relevant to `query`, closest first."""
    if not user_id.strip() or not query.strip():
        return []
    collection = _get_collection(user_id)
    count = collection.count()
    if count == 0:
        return []

    result = collection.query(
        query_texts=[query], n_results=min(k, count), include=["documents", "distances"]
    )
    docs = result.get("documents") or [[]]
    distances = result.get("distances") or [[]]
    first_docs = docs[0] if docs else []
    first_distances = distances[0] if distances else []

    return [
        doc
        for doc, distance in zip(first_docs, first_distances)
        if isinstance(doc, str) and distance <= MAX_RELEVANT_DISTANCE
    ]
