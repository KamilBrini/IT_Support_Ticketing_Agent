"""Tests for the shared ChromaDB client (src/rag/chroma_client.py).

Regression coverage for a real bug found during a live demo dry run: every
call previously created its own `chromadb.PersistentClient`, and under
concurrent requests (each /chat call touches ChromaDB twice - RAG retrieval
and long-term-memory recall) that raced internally, intermittently causing
"Could not connect to tenant default_tenant" and similar errors that got
silently swallowed by retrieve_from_rag's fail-safe try/except, wrongly
escalating perfectly answerable golden questions.
"""

from __future__ import annotations

import concurrent.futures as cf

from src.rag.chroma_client import get_client
from src.rag.retrieve import retrieve_context


def test_get_client_returns_the_same_instance() -> None:
    assert get_client() is get_client()


def test_concurrent_retrieval_does_not_error() -> None:
    """Stress test mirroring Promptfoo's concurrency:4 against /chat."""
    query = "What does company VPN policy require for remote access and MFA?"

    def _call(_: int) -> int:
        return len(retrieve_context(query, k=3))

    with cf.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(_call, range(12)))

    assert all(count > 0 for count in results)
