"""Tests for ChromaDB-backed policy retrieval (src/rag/retrieve.py).

These run against the real local ChromaDB index at CHROMA_DB_PATH (local,
offline embedding model - no network call, no API key needed), matching how
the app actually queries it. If the index hasn't been built yet (fresh
checkout, before `python -m src.rag.ingest` has run), these are skipped
rather than failed, since ingestion is a documented one-time setup step,
not something a unit test should perform as a side effect.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.rag.retrieve import MAX_RELEVANT_DISTANCE, retrieve_context

_CHROMA_PATH = Path(os.getenv("CHROMA_DB_PATH", "./data/chroma"))

pytestmark = pytest.mark.skipif(
    not _CHROMA_PATH.exists(),
    reason="ChromaDB index not built yet - run `python -m src.rag.ingest` first",
)


def test_retrieve_context_empty_query_returns_nothing() -> None:
    assert retrieve_context("", k=3) == []
    assert retrieve_context("   ", k=3) == []


def test_retrieve_context_relevant_query_returns_matches() -> None:
    results = retrieve_context("VPN MFA remote access", k=3)
    assert len(results) > 0
    assert any("vpn" in chunk.lower() for chunk in results)


def test_retrieve_context_respects_k() -> None:
    results = retrieve_context("password account lockout policy", k=1)
    assert len(results) <= 1


def test_retrieve_context_off_topic_query_is_filtered_out() -> None:
    # Calibrated in retrieve.py: off-topic queries score well above
    # MAX_RELEVANT_DISTANCE against this policy corpus, so nothing should
    # be returned rather than the nearest-but-wrong chunk.
    results = retrieve_context("official company policy for lunar mining operations on Mars", k=3)
    assert results == []


def test_max_relevant_distance_is_a_real_threshold() -> None:
    assert 0 < MAX_RELEVANT_DISTANCE < 2
